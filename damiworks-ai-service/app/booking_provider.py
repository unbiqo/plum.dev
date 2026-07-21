"""Booking provider: the seam between the demo and a real CRM.

``BookingProvider`` is the interface the bot talks to (list slots, hold, confirm,
reset). ``DemoBookingProvider`` is the demo implementation backed by an
``AppointmentStore``. Two stores exist:

- ``InMemoryAppointmentStore`` — tests and the no-Supabase fallback. Enforces the
  same active-slot uniqueness invariant as the DB, so the double-booking test is
  meaningful without a live database.
- ``SupabaseAppointmentStore`` — the real demo_appointments table (see
  sql/demo_appointments.sql). Maps a unique-violation into ``SlotTakenError``.

A real CRM (Altegio/1С/Bitrix24) is a different ``BookingProvider`` implementation
over the same interface; entity mapping is documented in AGENTS.md
(specialty→service category, doctor→staff, slot→schedule, appointment→booking).

Slots are dated and timezone-aware (from the clinic profile). Nothing about a
specific clinic is hardcoded — the provider reads the current ClinicProfile.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from zoneinfo import ZoneInfo

from .clinic_profile import ClinicProfile, get_clinic_profile
from .slot_engine import Slot, generate_slots

logger = logging.getLogger(__name__)

# A soft hold lives this long before the slot is free again.
HOLD_TTL = timedelta(minutes=5)
_ACTIVE_STATUSES = ("hold", "confirmed")


def profile_tz(profile: ClinicProfile) -> ZoneInfo:
    return ZoneInfo(profile.timezone)


def slots_to_labels(slots: list[Slot], today: date) -> list[str]:
    """Render provider slots to the "завтра 10:00" labels the writer speaks and
    booking_guardrail parses — the bridge that lets the deterministic guardrail
    validate a real-provider turn without changing the writer prompts.

    De-duplicated: two doctors free at the same relative time produce one label
    (the guardrail cares about the offered day+time, not which doctor)."""
    seen: list[str] = []
    for slot in slots:
        label = slot.relative_label(today)
        if label not in seen:
            seen.append(label)
    return seen


class SlotTakenError(Exception):
    """The (doctor, start) slot already has an active hold/confirmed booking."""


class StoreUnavailableError(Exception):
    """The backing store could not be reached (e.g. demo_appointments missing)."""


@dataclass
class Appointment:
    id: str
    instance_id: str
    specialty_id: str
    doctor_id: str
    doctor_name: str
    start: datetime  # tz-aware
    status: str
    patient_name: str | None
    contact: str | None
    hold_expires_at: datetime | None
    created_at: datetime

    def to_lead_dict(self) -> dict[str, object]:
        """The 'готовая заявка' shape the bot forms after a confirmed booking."""
        return {
            "appointment_id": self.id,
            "specialty_id": self.specialty_id,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor_name,
            "start_ts": self.start.isoformat(),
            "status": self.status,
            "patient_name": self.patient_name,
            "contact": self.contact,
        }


# ---------------------------------------------------------------------------
# Storage abstraction
# ---------------------------------------------------------------------------
class AppointmentStore(ABC):
    """Persistence for demo appointments. Deliberately narrow."""

    @abstractmethod
    def active_between(
        self, instance_id: str, *, start_from: datetime, start_to: datetime, now: datetime
    ) -> list[Appointment]:
        """Confirmed rows + holds that have NOT expired, in [start_from, start_to)."""

    @abstractmethod
    def insert(self, appt: Appointment) -> Appointment:
        """Insert a row. Raise SlotTakenError if an active row already occupies
        (instance_id, doctor_id, start)."""

    @abstractmethod
    def set_status(self, instance_id: str, appointment_id: str, *, from_status: str, to_status: str) -> Appointment | None:
        """Move a row's status; returns the row if it was in ``from_status``, else None."""

    @abstractmethod
    def sweep_expired_holds(self, instance_id: str, now: datetime) -> int:
        """Cancel holds whose expiry has passed. Returns how many were cancelled."""

    @abstractmethod
    def clear_instance(self, instance_id: str) -> int:
        """Delete every appointment for an instance (demo reset)."""


class InMemoryAppointmentStore(AppointmentStore):
    """In-process store. Enforces the active-slot uniqueness invariant."""

    def __init__(self) -> None:
        self._rows: dict[str, Appointment] = {}

    def _active_conflict(self, appt: Appointment, now: datetime) -> bool:
        for row in self._rows.values():
            if row.instance_id != appt.instance_id:
                continue
            if row.doctor_id != appt.doctor_id or row.start != appt.start:
                continue
            if row.status == "confirmed":
                return True
            if row.status == "hold" and (row.hold_expires_at is None or row.hold_expires_at > now):
                return True
        return False

    def active_between(self, instance_id, *, start_from, start_to, now):
        out: list[Appointment] = []
        for row in self._rows.values():
            if row.instance_id != instance_id:
                continue
            if not (start_from <= row.start < start_to):
                continue
            if row.status == "confirmed":
                out.append(row)
            elif row.status == "hold" and (row.hold_expires_at is None or row.hold_expires_at > now):
                out.append(row)
        return out

    def insert(self, appt):
        # The uniqueness check uses hold_expires_at as "now" reference via the
        # created row; callers sweep first, so an expired hold won't be present.
        now = appt.created_at
        if self._active_conflict(appt, now):
            raise SlotTakenError(f"{appt.doctor_id} @ {appt.start.isoformat()} is taken")
        self._rows[appt.id] = appt
        return appt

    def set_status(self, instance_id, appointment_id, *, from_status, to_status):
        row = self._rows.get(appointment_id)
        if row is None or row.instance_id != instance_id or row.status != from_status:
            return None
        row.status = to_status
        if to_status == "confirmed":
            row.hold_expires_at = None
        return row

    def sweep_expired_holds(self, instance_id, now):
        count = 0
        for row in self._rows.values():
            if (
                row.instance_id == instance_id
                and row.status == "hold"
                and row.hold_expires_at is not None
                and row.hold_expires_at <= now
            ):
                row.status = "cancelled"
                count += 1
        return count

    def clear_instance(self, instance_id):
        ids = [rid for rid, row in self._rows.items() if row.instance_id == instance_id]
        for rid in ids:
            del self._rows[rid]
        return len(ids)


# ---------------------------------------------------------------------------
# Provider interface + demo implementation
# ---------------------------------------------------------------------------
class BookingProvider(ABC):
    @abstractmethod
    def get_slots(
        self,
        instance_id: str,
        *,
        date_from: date,
        date_to: date,
        specialty_id: str | None = None,
        doctor_id: str | None = None,
    ) -> list[Slot]:
        ...

    @abstractmethod
    def suggest_doctors(
        self, instance_id: str, specialty_id: str, *, limit_per_doctor: int = 2
    ) -> list[tuple[str, str, list[Slot]]]:
        ...

    @abstractmethod
    def hold_slot(
        self, instance_id: str, *, doctor_id: str, start: datetime,
        patient_name: str | None = None, contact: str | None = None,
    ) -> Appointment:
        ...

    @abstractmethod
    def confirm_appointment(self, instance_id: str, appointment_id: str) -> Appointment | None:
        ...

    @abstractmethod
    def book_slot(
        self, instance_id: str, *, doctor_id: str, start: datetime,
        patient_name: str | None = None, contact: str | None = None,
    ) -> Appointment:
        ...

    @abstractmethod
    def reset(self, instance_id: str) -> int:
        ...


class DemoBookingProvider(BookingProvider):
    def __init__(
        self,
        store: AppointmentStore | None = None,
        *,
        profile_loader=get_clinic_profile,
        clock=lambda: datetime.now(timezone.utc),
    ) -> None:
        self._store = store or InMemoryAppointmentStore()
        self._profile_loader = profile_loader
        self._clock = clock

    def _profile(self, kb_markdown: str | None = None) -> ClinicProfile:
        return self._profile_loader(kb_markdown)

    def _busy(
        self, instance_id: str, *, date_from: date, date_to: date, profile: ClinicProfile
    ) -> set[tuple[str, datetime]]:
        now = self._clock()
        self._store.sweep_expired_holds(instance_id, now)
        # Query a hair past date_to so the whole final day is covered.
        start_from = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=1)
        start_to = datetime.combine(date_to, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=2)
        active = self._store.active_between(
            instance_id, start_from=start_from, start_to=start_to, now=now
        )
        return {(a.doctor_id, a.start) for a in active}

    def get_slots(
        self, instance_id, *, date_from, date_to, specialty_id=None, doctor_id=None,
    ):
        profile = self._profile()
        busy = self._busy(instance_id, date_from=date_from, date_to=date_to, profile=profile)
        return generate_slots(
            profile, date_from=date_from, date_to=date_to, now=self._clock(),
            busy=busy, specialty_id=specialty_id, doctor_id=doctor_id,
        )

    def suggest_doctors(self, instance_id, specialty_id, *, limit_per_doctor=2):
        """For "нужен офтальмолог": each doctor of the specialty with their
        soonest few free windows. Returns [(doctor_id, doctor_name, [Slot])]."""
        profile = self._profile()
        now = self._clock()
        today = now.astimezone(profile_tz(profile)).date()
        busy = self._busy(
            instance_id, date_from=today, date_to=today + timedelta(days=14), profile=profile
        )
        out: list[tuple[str, str, list[Slot]]] = []
        for doctor in profile.doctors_for_specialty(specialty_id):
            windows = generate_slots(
                profile, date_from=today, date_to=today + timedelta(days=14),
                now=now, busy=busy, doctor_id=doctor.id,
            )[:limit_per_doctor]
            if windows:
                out.append((doctor.id, doctor.name, windows))
        return out

    def hold_slot(self, instance_id, *, doctor_id, start, patient_name=None, contact=None):
        profile = self._profile()
        doctor = profile.doctor_by_id(doctor_id)
        if doctor is None:
            raise SlotTakenError(f"unknown doctor {doctor_id}")
        # The slot must actually be offered right now (schedule + not past + free).
        offered = self.get_slots(
            instance_id, date_from=start.astimezone(profile_tz(profile)).date(),
            date_to=start.astimezone(profile_tz(profile)).date(), doctor_id=doctor_id,
        )
        if not any(s.start == start for s in offered):
            raise SlotTakenError(f"{doctor_id} @ {start.isoformat()} is not an available slot")
        now = self._clock()
        appt = Appointment(
            id=str(uuid.uuid4()), instance_id=instance_id,
            specialty_id=doctor.specialty_id, doctor_id=doctor_id, doctor_name=doctor.name,
            start=start, status="hold", patient_name=patient_name, contact=contact,
            hold_expires_at=now + HOLD_TTL, created_at=now,
        )
        return self._store.insert(appt)

    def confirm_appointment(self, instance_id, appointment_id):
        return self._store.set_status(
            instance_id, appointment_id, from_status="hold", to_status="confirmed"
        )

    def book_slot(self, instance_id, *, doctor_id, start, patient_name=None, contact=None):
        """Hold + confirm in one call (the common 'I have everything' path)."""
        appt = self.hold_slot(
            instance_id, doctor_id=doctor_id, start=start,
            patient_name=patient_name, contact=contact,
        )
        confirmed = self.confirm_appointment(instance_id, appt.id)
        return confirmed or appt

    def reset(self, instance_id):
        return self._store.clear_instance(instance_id)


# ---------------------------------------------------------------------------
# Supabase-backed store (real demo_appointments table)
# ---------------------------------------------------------------------------
def _parse_ts(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _row_to_appointment(row: dict) -> Appointment:
    return Appointment(
        id=str(row["id"]),
        instance_id=row["instance_id"],
        specialty_id=row.get("specialty_id") or "",
        doctor_id=row.get("doctor_id") or "",
        doctor_name=row.get("doctor_name") or "",
        start=_parse_ts(row.get("start_ts")) or datetime.now(timezone.utc),
        status=row.get("status") or "hold",
        patient_name=row.get("patient_name"),
        contact=row.get("contact"),
        hold_expires_at=_parse_ts(row.get("hold_expires_at")),
        created_at=_parse_ts(row.get("created_at")) or datetime.now(timezone.utc),
    )


def _is_unique_violation(exc: Exception) -> bool:
    text = str(exc)
    return "23505" in text or "duplicate key" in text or "active_slot_unique" in text


def _is_missing_table(exc: Exception) -> bool:
    text = str(exc)
    return "PGRST205" in text or "Could not find the table" in text or "demo_appointments" in text and "schema cache" in text


class SupabaseAppointmentStore(AppointmentStore):
    """Backed by the demo_appointments table. Maps a unique-violation to
    SlotTakenError; a missing table degrades reads to empty and raises
    StoreUnavailableError on writes so the bot can fall back gracefully."""

    _TABLE = "demo_appointments"

    def __init__(self, client) -> None:
        self._client = client

    def active_between(self, instance_id, *, start_from, start_to, now):
        try:
            resp = (
                self._client.table(self._TABLE)
                .select("*")
                .eq("instance_id", instance_id)
                .in_("status", list(_ACTIVE_STATUSES))
                .gte("start_ts", start_from.isoformat())
                .lt("start_ts", start_to.isoformat())
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            if _is_missing_table(exc):
                logger.warning("demo_appointments unavailable; treating all slots as free")
                return []
            logger.exception("demo_appointments read failed")
            return []
        out: list[Appointment] = []
        for row in resp.data or []:
            appt = _row_to_appointment(row)
            if appt.status == "hold" and appt.hold_expires_at is not None and appt.hold_expires_at <= now:
                continue  # expired hold: free
            out.append(appt)
        return out

    def insert(self, appt):
        payload = {
            "id": appt.id, "instance_id": appt.instance_id,
            "specialty_id": appt.specialty_id, "doctor_id": appt.doctor_id,
            "doctor_name": appt.doctor_name, "start_ts": appt.start.isoformat(),
            "status": appt.status, "patient_name": appt.patient_name,
            "contact": appt.contact,
            "hold_expires_at": appt.hold_expires_at.isoformat() if appt.hold_expires_at else None,
            "created_at": appt.created_at.isoformat(),
        }
        try:
            resp = self._client.table(self._TABLE).insert(payload).execute()
        except Exception as exc:  # noqa: BLE001
            if _is_unique_violation(exc):
                raise SlotTakenError(f"{appt.doctor_id} @ {appt.start.isoformat()} is taken") from exc
            if _is_missing_table(exc):
                raise StoreUnavailableError("demo_appointments table is missing") from exc
            raise
        data = list(resp.data or [])
        return _row_to_appointment(data[0]) if data else appt

    def set_status(self, instance_id, appointment_id, *, from_status, to_status):
        updates = {"status": to_status, "updated_at": datetime.now(timezone.utc).isoformat()}
        if to_status == "confirmed":
            updates["hold_expires_at"] = None
        try:
            resp = (
                self._client.table(self._TABLE)
                .update(updates)
                .eq("instance_id", instance_id)
                .eq("id", appointment_id)
                .eq("status", from_status)
                .execute()
            )
        except Exception:  # noqa: BLE001
            logger.exception("demo_appointments status update failed")
            return None
        data = list(resp.data or [])
        return _row_to_appointment(data[0]) if data else None

    def sweep_expired_holds(self, instance_id, now):
        try:
            resp = (
                self._client.table(self._TABLE)
                .update({"status": "cancelled", "updated_at": now.isoformat()})
                .eq("instance_id", instance_id)
                .eq("status", "hold")
                .lte("hold_expires_at", now.isoformat())
                .execute()
            )
        except Exception:  # noqa: BLE001
            return 0
        return len(list(resp.data or []))

    def clear_instance(self, instance_id):
        try:
            resp = (
                self._client.table(self._TABLE)
                .delete()
                .eq("instance_id", instance_id)
                .execute()
            )
        except Exception:  # noqa: BLE001
            logger.exception("demo_appointments clear failed")
            return 0
        return len(list(resp.data or []))
