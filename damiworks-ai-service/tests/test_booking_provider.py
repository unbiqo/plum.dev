"""Tests for the demo booking provider: slots from the profile, soft-hold →
confirm, double-booking race protection, hold expiry, reset, the Supabase store
row/error mapping, and the booking_guardrail bridge on real provider slots.

In-memory store + injected clock — no live database, but the same active-slot
uniqueness invariant the DB enforces, so the double-booking test is real.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.booking_guardrail import SAFE_NO_SLOTS_ANSWER, enforce_slot_guardrail
from app.booking_provider import (
    HOLD_TTL,
    Appointment,
    DemoBookingProvider,
    InMemoryAppointmentStore,
    SlotTakenError,
    StoreUnavailableError,
    SupabaseAppointmentStore,
    slots_to_labels,
)
from app.clinic_profile import get_clinic_profile

_ALMATY = ZoneInfo("Asia/Almaty")
_INST = "damiworks_medical_center_demo"


class _Clock:
    """Mutable clock for hold-expiry tests."""

    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


def _provider(clock: _Clock) -> DemoBookingProvider:
    return DemoBookingProvider(InMemoryAppointmentStore(), clock=clock)


def _tue_morning() -> _Clock:
    # Tue 2026-07-21 08:00 Almaty (03:00 UTC).
    return _Clock(datetime(2026, 7, 21, 3, 0, tzinfo=timezone.utc))


# ---------------------------------------------------------------------------
# Slot listing & doctor suggestions
# ---------------------------------------------------------------------------

def test_suggest_doctors_returns_specialty_doctors_with_soonest_windows() -> None:
    prov = _provider(_tue_morning())
    suggestions = prov.suggest_doctors(_INST, "офтальмолог", limit_per_doctor=3)
    assert [name for _, name, _ in suggestions] == ["Ольга Панченко"]
    _, _, windows = suggestions[0]
    assert len(windows) == 3
    assert windows[0].start.strftime("%H:%M") == "09:00"


def test_get_slots_excludes_a_confirmed_booking() -> None:
    clock = _tue_morning()
    prov = _provider(clock)
    day = datetime(2026, 7, 21, tzinfo=_ALMATY).date()
    before = prov.get_slots(_INST, date_from=day, date_to=day, doctor_id="ольга_панченко")
    taken = before[0].start
    prov.book_slot(_INST, doctor_id="ольга_панченко", start=taken, patient_name="Дамир", contact="+7700")
    after = prov.get_slots(_INST, date_from=day, date_to=day, doctor_id="ольга_панченко")
    assert len(after) == len(before) - 1
    assert all(s.start != taken for s in after)


# ---------------------------------------------------------------------------
# Hold → confirm, and the 5-minute expiry
# ---------------------------------------------------------------------------

def test_hold_then_confirm_flow() -> None:
    clock = _tue_morning()
    prov = _provider(clock)
    day = datetime(2026, 7, 21, tzinfo=_ALMATY).date()
    slot = prov.get_slots(_INST, date_from=day, date_to=day, doctor_id="ольга_панченко")[0]

    held = prov.hold_slot(_INST, doctor_id="ольга_панченко", start=slot.start)
    assert held.status == "hold" and held.hold_expires_at is not None

    # While held, the slot is not offered and cannot be double-held.
    still = prov.get_slots(_INST, date_from=day, date_to=day, doctor_id="ольга_панченко")
    assert all(s.start != slot.start for s in still)

    confirmed = prov.confirm_appointment(_INST, held.id)
    assert confirmed is not None and confirmed.status == "confirmed"
    assert confirmed.hold_expires_at is None


def test_expired_hold_frees_the_slot_again() -> None:
    clock = _tue_morning()
    prov = _provider(clock)
    day = datetime(2026, 7, 21, tzinfo=_ALMATY).date()
    slot = prov.get_slots(_INST, date_from=day, date_to=day, doctor_id="ольга_панченко")[0]

    prov.hold_slot(_INST, doctor_id="ольга_панченко", start=slot.start)
    clock.advance(HOLD_TTL + timedelta(seconds=1))  # let the hold expire

    freed = prov.get_slots(_INST, date_from=day, date_to=day, doctor_id="ольга_панченко")
    assert any(s.start == slot.start for s in freed)
    # And it can be booked by someone else now.
    appt = prov.book_slot(_INST, doctor_id="ольга_панченко", start=slot.start, patient_name="Другой")
    assert appt.status == "confirmed"


# ---------------------------------------------------------------------------
# Double-booking race protection
# ---------------------------------------------------------------------------

def test_double_booking_the_same_slot_is_rejected() -> None:
    clock = _tue_morning()
    prov = _provider(clock)
    day = datetime(2026, 7, 21, tzinfo=_ALMATY).date()
    slot = prov.get_slots(_INST, date_from=day, date_to=day, doctor_id="ольга_панченко")[0]

    prov.book_slot(_INST, doctor_id="ольга_панченко", start=slot.start, patient_name="Первый")
    with pytest.raises(SlotTakenError):
        prov.book_slot(_INST, doctor_id="ольга_панченко", start=slot.start, patient_name="Второй")


def test_store_enforces_active_slot_uniqueness_directly() -> None:
    # The store is the last line of defense (mirrors the DB unique index).
    store = InMemoryAppointmentStore()
    now = datetime(2026, 7, 21, 3, 0, tzinfo=timezone.utc)
    start = datetime(2026, 7, 21, 9, 0, tzinfo=_ALMATY)

    def _appt(pid: str, status: str) -> Appointment:
        return Appointment(
            id=pid, instance_id=_INST, specialty_id="офтальмолог",
            doctor_id="ольга_панченко", doctor_name="Ольга Панченко", start=start,
            status=status, patient_name=None, contact=None,
            hold_expires_at=now + HOLD_TTL if status == "hold" else None, created_at=now,
        )

    store.insert(_appt("a", "confirmed"))
    with pytest.raises(SlotTakenError):
        store.insert(_appt("b", "hold"))


def test_hold_on_a_slot_outside_the_schedule_is_rejected() -> None:
    clock = _tue_morning()
    prov = _provider(clock)
    # Панченко works Tue 09:00-16:00; 21:00 is outside the schedule.
    bad = datetime(2026, 7, 21, 21, 0, tzinfo=_ALMATY)
    with pytest.raises(SlotTakenError):
        prov.hold_slot(_INST, doctor_id="ольга_панченко", start=bad)


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def test_reset_clears_only_that_instance() -> None:
    clock = _tue_morning()
    prov = _provider(clock)
    day = datetime(2026, 7, 21, tzinfo=_ALMATY).date()
    slot = prov.get_slots(_INST, date_from=day, date_to=day, doctor_id="ольга_панченко")[0]
    prov.book_slot(_INST, doctor_id="ольга_панченко", start=slot.start, patient_name="Дамир")
    prov.book_slot("other_instance", doctor_id="ольга_панченко", start=slot.start, patient_name="Кто-то")

    removed = prov.reset(_INST)
    assert removed == 1
    # The slot is free again for _INST, but other_instance still holds its own.
    freed = prov.get_slots(_INST, date_from=day, date_to=day, doctor_id="ольга_панченко")
    assert any(s.start == slot.start for s in freed)


# ---------------------------------------------------------------------------
# Supabase store: row mapping + error mapping (fake client, no live DB)
# ---------------------------------------------------------------------------

class _FakeQuery:
    def __init__(self, table: "_FakeTable", op: str) -> None:
        self._t = table
        self._op = op
        self._payload = None

    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def select(self, *_a):
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, *_a):
        return self

    def in_(self, *_a):
        return self

    def gte(self, *_a):
        return self

    def lt(self, *_a):
        return self

    def lte(self, *_a):
        return self

    def execute(self):
        if self._op == "insert":
            if self._t.raise_on_insert:
                raise self._t.raise_on_insert
            self._t.inserted.append(self._payload)
            return type("R", (), {"data": [self._payload]})()
        return type("R", (), {"data": self._t.rows})()


class _FakeTable:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.inserted: list[dict] = []
        self.raise_on_insert: Exception | None = None

    def __getattr__(self, name):
        return getattr(_FakeQuery(self, ""), name)


class _FakeClient:
    def __init__(self, table: _FakeTable) -> None:
        self._table = table

    def table(self, _name):
        return self._table


def _appt(status: str = "hold") -> Appointment:
    now = datetime(2026, 7, 21, 3, 0, tzinfo=timezone.utc)
    return Appointment(
        id="11111111-1111-1111-1111-111111111111", instance_id=_INST,
        specialty_id="офтальмолог", doctor_id="ольга_панченко",
        doctor_name="Ольга Панченко", start=datetime(2026, 7, 21, 9, 0, tzinfo=_ALMATY),
        status=status, patient_name="Дамир", contact="+7700",
        hold_expires_at=now + HOLD_TTL, created_at=now,
    )


def test_supabase_store_maps_unique_violation_to_slot_taken() -> None:
    table = _FakeTable()
    table.raise_on_insert = Exception('duplicate key value violates unique constraint "demo_appointments_active_slot_unique" (23505)')
    store = SupabaseAppointmentStore(_FakeClient(table))
    with pytest.raises(SlotTakenError):
        store.insert(_appt())


def test_supabase_store_maps_missing_table_to_unavailable() -> None:
    table = _FakeTable()
    table.raise_on_insert = Exception("Could not find the table 'public.demo_appointments' in the schema cache (PGRST205)")
    store = SupabaseAppointmentStore(_FakeClient(table))
    with pytest.raises(StoreUnavailableError):
        store.insert(_appt())


def test_supabase_store_reads_skip_expired_holds() -> None:
    now = datetime(2026, 7, 21, 4, 0, tzinfo=timezone.utc)  # after the hold expiry below
    table = _FakeTable()
    table.rows = [
        {
            "id": "a", "instance_id": _INST, "specialty_id": "офтальмолог",
            "doctor_id": "ольга_панченко", "doctor_name": "Ольга Панченко",
            "start_ts": "2026-07-21T09:00:00+05:00", "status": "hold",
            "hold_expires_at": "2026-07-21T03:05:00+00:00",  # expired by `now`
            "created_at": "2026-07-21T03:00:00+00:00",
        },
        {
            "id": "b", "instance_id": _INST, "specialty_id": "офтальмолог",
            "doctor_id": "ольга_панченко", "doctor_name": "Ольга Панченко",
            "start_ts": "2026-07-21T10:00:00+05:00", "status": "confirmed",
            "hold_expires_at": None, "created_at": "2026-07-21T03:00:00+00:00",
        },
    ]
    store = SupabaseAppointmentStore(_FakeClient(table))
    active = store.active_between(
        _INST,
        start_from=datetime(2026, 7, 21, tzinfo=timezone.utc),
        start_to=datetime(2026, 7, 22, tzinfo=timezone.utc),
        now=now,
    )
    # The expired hold is skipped; the confirmed booking remains.
    assert [a.id for a in active] == ["b"]


# ---------------------------------------------------------------------------
# booking_guardrail bridge on real provider slots
# ---------------------------------------------------------------------------

def test_booking_provider_flag_defaults_off_and_reads_env(monkeypatch) -> None:
    from app.config import get_settings

    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "x")
    monkeypatch.delenv("DEMO_BOOKING_PROVIDER_ENABLED", raising=False)
    assert get_settings().demo_booking_provider_enabled is False
    monkeypatch.setenv("DEMO_BOOKING_PROVIDER_ENABLED", "true")
    assert get_settings().demo_booking_provider_enabled is True


def test_guardrail_allows_a_real_provider_slot_and_replaces_an_invented_one() -> None:
    clock = _tue_morning()
    prov = _provider(clock)
    today = clock().astimezone(_ALMATY).date()
    day = datetime(2026, 7, 21, tzinfo=_ALMATY).date()
    slots = prov.get_slots(_INST, date_from=day, date_to=day, doctor_id="ольга_панченко")
    labels = slots_to_labels(slots, today)
    assert "сегодня 09:00" in labels

    # A slot the provider offered passes untouched.
    good = "Записала предварительно на сегодня 09:00, администратор подтвердит."
    out, replaced = enforce_slot_guardrail(answer=good, offered_slots=labels, booking_context=True)
    assert not replaced and out == good

    # A slot the provider never offered (Панченко is off Wednesday) is replaced.
    invented = "Записала вас на завтра 21:00 к офтальмологу."
    out2, replaced2 = enforce_slot_guardrail(answer=invented, offered_slots=labels, booking_context=True)
    assert replaced2 and out2 == SAFE_NO_SLOTS_ANSWER
