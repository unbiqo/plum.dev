"""Deterministic, timezone-aware appointment slot engine.

One engine, two filters (the task's "оба фильтра из одного движка"):
- by specialty  -> aggregate over every doctor of that specialty;
- by doctor     -> that single doctor.

A slot exists when it is inside a doctor's KB working block, not already booked
(``busy``), and not in the past (relative to ``now`` in the clinic's timezone).

The engine is storage-agnostic: ``busy`` is injected, so this module has no
Supabase dependency and is a pure function of (profile, busy, now, range). The
DemoBookingProvider (app/booking_provider.py) supplies ``busy`` from the
demo_appointments table and renders the labels the writer/guardrail consume.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .clinic_profile import ClinicProfile, Doctor

# Relative-day vocabulary shared with the writer prompt and booking_guardrail.
_RELATIVE_DAYS = {0: "сегодня", 1: "завтра", 2: "послезавтра"}


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


@dataclass(frozen=True)
class Slot:
    doctor_id: str
    doctor_name: str
    specialty_id: str
    start: datetime  # tz-aware, clinic timezone
    duration_min: int

    def relative_label(self, today: date) -> str:
        """Writer/guardrail-facing label: "завтра 10:00" for near days, else a
        dotted date "23.07 10:00" for anything past послезавтра."""
        delta = (self.start.date() - today).days
        hhmm = self.start.strftime("%H:%M")
        day_word = _RELATIVE_DAYS.get(delta)
        if day_word:
            return f"{day_word} {hhmm}"
        return f"{self.start.strftime('%d.%m')} {hhmm}"


def _matching_doctors(
    profile: ClinicProfile,
    *,
    specialty_id: str | None,
    doctor_id: str | None,
) -> tuple[Doctor, ...]:
    if doctor_id is not None:
        doctor = profile.doctor_by_id(doctor_id)
        # A doctor_id constrained to a specialty must belong to it.
        if doctor is None or (specialty_id is not None and doctor.specialty_id != specialty_id):
            return ()
        return (doctor,)
    if specialty_id is not None:
        return profile.doctors_for_specialty(specialty_id)
    return profile.doctors


def generate_slots(
    profile: ClinicProfile,
    *,
    date_from: date,
    date_to: date,
    now: datetime,
    busy: set[tuple[str, datetime]] | None = None,
    specialty_id: str | None = None,
    doctor_id: str | None = None,
) -> list[Slot]:
    """Bookable slots in [date_from, date_to] (inclusive), sorted by start.

    ``now`` and every ``busy`` datetime must be tz-aware. Past slots and busy
    (doctor_id, start) pairs are excluded. Busy membership compares by instant,
    so a busy datetime stored in UTC still matches a clinic-tz slot start.
    """
    tz = ZoneInfo(profile.timezone)
    now_local = now.astimezone(tz)
    busy = busy or set()
    duration = profile.slot_duration_min
    doctors = _matching_doctors(profile, specialty_id=specialty_id, doctor_id=doctor_id)

    slots: list[Slot] = []
    day = date_from
    while day <= date_to:
        weekday = day.weekday()
        for doctor in doctors:
            for block in doctor.blocks:
                if weekday not in block.weekdays:
                    continue
                start_min, end_min = _to_minutes(block.start), _to_minutes(block.end)
                cursor = start_min
                while cursor + duration <= end_min:
                    start_dt = datetime.combine(
                        day, time(cursor // 60, cursor % 60), tzinfo=tz
                    )
                    cursor += duration
                    if start_dt <= now_local:
                        continue
                    if (doctor.id, start_dt) in busy:
                        continue
                    slots.append(
                        Slot(
                            doctor_id=doctor.id,
                            doctor_name=doctor.name,
                            specialty_id=doctor.specialty_id,
                            start=start_dt,
                            duration_min=duration,
                        )
                    )
        day += timedelta(days=1)

    slots.sort(key=lambda s: (s.start, s.doctor_id))
    return slots


def next_slots(
    profile: ClinicProfile,
    *,
    now: datetime,
    busy: set[tuple[str, datetime]] | None = None,
    specialty_id: str | None = None,
    doctor_id: str | None = None,
    days_ahead: int = 14,
    limit: int = 3,
) -> list[Slot]:
    """The soonest ``limit`` slots within ``days_ahead`` days — the common case
    the bot needs ("ближайшие окна")."""
    tz = ZoneInfo(profile.timezone)
    today = now.astimezone(tz).date()
    slots = generate_slots(
        profile,
        date_from=today,
        date_to=today + timedelta(days=days_ahead),
        now=now,
        busy=busy,
        specialty_id=specialty_id,
        doctor_id=doctor_id,
    )
    return slots[:limit]
