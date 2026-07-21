"""Tests for the KB-driven clinic profile and the timezone-aware slot engine.

No Supabase, no LLM: the profile is a pure function of the KB markdown and the
slot engine is a pure function of (profile, busy, now, range). The KB-SWAP test
is the load-bearing one: a completely different company's KB must rebuild the
profile with no code change.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.clinic_profile import (
    DEFAULT_SLOT_DURATION_MIN,
    DEFAULT_TIMEZONE,
    build_clinic_profile,
    get_clinic_profile,
)
from app.medical_center_kb import get_raw_markdown
from app.slot_engine import Slot, generate_slots, next_slots

# 2026-07-20 is a Monday; 21 Tue, 22 Wed, 23 Thu, 24 Fri, 25 Sat, 26 Sun.
_ALMATY = ZoneInfo("Asia/Almaty")


def _midnight(y: int, m: int, d: int, tz: ZoneInfo = _ALMATY) -> datetime:
    return datetime(y, m, d, 0, 0, tzinfo=tz)


# ---------------------------------------------------------------------------
# Profile parsing from the real MedNova KB
# ---------------------------------------------------------------------------

def test_profile_parses_real_mednova_kb() -> None:
    profile = build_clinic_profile(get_raw_markdown())
    assert profile.name == "MedNova Clinic"
    assert profile.timezone == "Asia/Almaty"
    assert profile.slot_duration_min == 30
    assert profile.is_default is False
    # 13 named doctors with schedules, 13 distinct specialties.
    assert len(profile.doctors) == 13
    assert len(profile.specialties) == 13


def test_profile_reads_clinic_working_hours_not_the_default_template() -> None:
    # Regression: "Контакты и режим работы:" header must not shadow the real
    # "- Режим работы: Пн–Пт 08:00–20:00, Сб 09:00–17:00, Вс 10:00–15:00." line.
    profile = build_clinic_profile(get_raw_markdown())
    by_day = {tuple(sorted(b.weekdays)): (b.start, b.end) for b in profile.working_hours}
    assert by_day[(0, 1, 2, 3, 4)] == ("08:00", "20:00")
    assert by_day[(5,)] == ("09:00", "17:00")
    assert by_day[(6,)] == ("10:00", "15:00")


def test_profile_doctor_schedule_matches_kb() -> None:
    profile = build_clinic_profile(get_raw_markdown())
    # Ольга Панченко — офтальмолог, Приём: Вт/Чт 09:00–16:00.
    panchenko = profile.doctor_by_id("ольга_панченко")
    assert panchenko is not None
    assert panchenko.specialty_id == "офтальмолог"
    assert panchenko.works_on(1) and panchenko.works_on(3)  # Tue, Thu
    assert not panchenko.works_on(0)  # not Monday
    # Руслан Ким — кардиолог, Вт/Чт 14:00–20:00 + Сб 10:00–14:00 (two blocks).
    kim = profile.doctor_by_id("руслан_ким")
    assert len(kim.blocks) == 2


# ---------------------------------------------------------------------------
# Slot engine: working hours, off-days, past time, timezone, duration
# ---------------------------------------------------------------------------

def test_slots_fill_the_working_block_by_duration() -> None:
    profile = build_clinic_profile(get_raw_markdown())
    now = _midnight(2026, 7, 21)  # Tuesday, whole day ahead
    slots = generate_slots(
        profile, specialty_id="офтальмолог",
        date_from=date(2026, 7, 21), date_to=date(2026, 7, 21), now=now,
    )
    # 09:00–16:00 in 30-min steps, last start where start+30 <= 16:00 → 15:30.
    assert [s.start.strftime("%H:%M") for s in slots[:2]] == ["09:00", "09:30"]
    assert slots[-1].start.strftime("%H:%M") == "15:30"
    assert len(slots) == 14


def test_no_slots_on_a_doctors_off_day() -> None:
    profile = build_clinic_profile(get_raw_markdown())
    now = _midnight(2026, 7, 22)  # Wednesday — Панченко does not work Wed
    assert generate_slots(
        profile, doctor_id="ольга_панченко",
        date_from=date(2026, 7, 22), date_to=date(2026, 7, 22), now=now,
    ) == []


def test_past_slots_are_excluded_in_clinic_timezone() -> None:
    profile = build_clinic_profile(get_raw_markdown())
    now = datetime(2026, 7, 21, 12, 0, tzinfo=_ALMATY)  # Tue 12:00 local
    slots = generate_slots(
        profile, specialty_id="офтальмолог",
        date_from=date(2026, 7, 21), date_to=date(2026, 7, 21), now=now,
    )
    assert slots and slots[0].start.strftime("%H:%M") == "12:30"
    assert all(s.start > now for s in slots)


def test_now_given_in_utc_is_respected_against_clinic_local_time() -> None:
    # 08:00 UTC == 13:00 Almaty (UTC+5): slots before 13:00 local must be gone.
    profile = build_clinic_profile(get_raw_markdown())
    now_utc = datetime(2026, 7, 21, 8, 0, tzinfo=ZoneInfo("UTC"))
    slots = generate_slots(
        profile, specialty_id="офтальмолог",
        date_from=date(2026, 7, 21), date_to=date(2026, 7, 21), now=now_utc,
    )
    # 13:00 local == now exactly, and a slot starting "now" is not bookable, so
    # the soonest is 13:30.
    assert slots[0].start.strftime("%H:%M") == "13:30"


def test_specialty_filter_aggregates_all_doctors_of_that_specialty() -> None:
    # One engine, two filters: specialty = aggregate over its doctors.
    profile = build_clinic_profile(get_raw_markdown())
    now = _midnight(2026, 7, 21)
    by_specialty = generate_slots(
        profile, specialty_id="офтальмолог",
        date_from=date(2026, 7, 21), date_to=date(2026, 7, 23), now=now,
    )
    assert {s.doctor_id for s in by_specialty} == {"ольга_панченко"}
    # Doctor filter is a strict subset of the specialty aggregate.
    by_doctor = generate_slots(
        profile, doctor_id="ольга_панченко",
        date_from=date(2026, 7, 21), date_to=date(2026, 7, 23), now=now,
    )
    assert by_doctor == by_specialty


def test_busy_slots_are_excluded_by_instant_even_across_timezones() -> None:
    profile = build_clinic_profile(get_raw_markdown())
    now = _midnight(2026, 7, 21)
    free = generate_slots(
        profile, doctor_id="ольга_панченко",
        date_from=date(2026, 7, 21), date_to=date(2026, 7, 21), now=now,
    )
    taken = free[0].start  # 09:00 Almaty
    # Provide the busy instant in UTC — must still match the Almaty slot.
    busy = {("ольга_панченко", taken.astimezone(ZoneInfo("UTC")))}
    remaining = generate_slots(
        profile, doctor_id="ольга_панченко",
        date_from=date(2026, 7, 21), date_to=date(2026, 7, 21), now=now, busy=busy,
    )
    assert len(remaining) == len(free) - 1
    assert all(s.start != taken for s in remaining)


def test_relative_label_words_then_dotted_date() -> None:
    profile = build_clinic_profile(get_raw_markdown())
    today = date(2026, 7, 21)
    slot = Slot("d", "Имя", "s", datetime(2026, 7, 21, 10, 0, tzinfo=_ALMATY), 30)
    assert slot.relative_label(today) == "сегодня 10:00"
    tomorrow = Slot("d", "Имя", "s", datetime(2026, 7, 22, 10, 0, tzinfo=_ALMATY), 30)
    assert tomorrow.relative_label(today) == "завтра 10:00"
    far = Slot("d", "Имя", "s", datetime(2026, 7, 30, 9, 0, tzinfo=_ALMATY), 30)
    assert far.relative_label(today) == "30.07 09:00"


def test_next_slots_returns_the_soonest_limited() -> None:
    profile = build_clinic_profile(get_raw_markdown())
    now = datetime(2026, 7, 21, 10, 15, tzinfo=_ALMATY)  # Tue mid-morning
    soonest = next_slots(profile, specialty_id="офтальмолог", now=now, limit=3)
    assert len(soonest) == 3
    assert [s.start.strftime("%H:%M") for s in soonest] == ["10:30", "11:00", "11:30"]


# ---------------------------------------------------------------------------
# KB-SWAP: a completely different company rebuilds the profile, no code change
# ---------------------------------------------------------------------------

_SWAPPED_KB = """# LinguaPro — база знаний демо

Онлайн-школа иностранных языков (демо-данные).

## Контакты
- Часовой пояс: Europe/Moscow
- Длительность приёма: 45
- Режим работы: Пн–Сб 10:00–19:00.

## Преподаватели и расписание

- Джон Смит — преподаватель IELTS, старший методист (полное имя Джон Роберт Смит), стаж 9 лет. Приём: Пн/Ср/Пт 10:00–16:00. Языки: английский.

- Мария Ли — преподаватель разговорного английского (полное имя Мария Ивановна Ли), стаж 6 лет. Приём: Вт/Чт 12:00–18:00, Сб 10:00–14:00. Языки: английский, китайский.
"""


def test_kb_swap_rebuilds_profile_for_a_different_company_no_code_change() -> None:
    profile = build_clinic_profile(_SWAPPED_KB)
    # Name, timezone, slot duration, working hours: all from the swapped KB.
    assert profile.name == "LinguaPro"
    assert profile.timezone == "Europe/Moscow"
    assert profile.slot_duration_min == 45
    assert profile.is_default is False
    # Specialties are the swapped professions, not any clinic specialty.
    specialty_names = {s.name for s in profile.specialties}
    assert specialty_names == {"преподаватель IELTS", "преподаватель разговорного английского"}
    assert not any("офтальмолог" in n for n in specialty_names)
    # Doctors (teachers) and their schedules come from the swapped KB.
    smith = profile.doctor_by_id("джон_смит")
    assert smith is not None and smith.works_on(0) and smith.works_on(2)  # Пн/Ср
    assert not smith.works_on(1)  # not Tuesday


def test_kb_swap_slots_use_the_new_companys_timezone_and_schedule() -> None:
    profile = build_clinic_profile(_SWAPPED_KB)
    moscow = ZoneInfo("Europe/Moscow")
    now = datetime(2026, 7, 20, 0, 0, tzinfo=moscow)  # Monday
    slots = generate_slots(
        profile, doctor_id="джон_смит",
        date_from=date(2026, 7, 20), date_to=date(2026, 7, 20), now=now,
    )
    # Джон Смит: Пн 10:00–16:00, 45-минутные слоты; таймзона Москвы.
    assert slots[0].start.tzinfo.key == "Europe/Moscow"
    assert slots[0].start.strftime("%H:%M") == "10:00"
    assert slots[1].start.strftime("%H:%M") == "10:45"
    assert slots[-1].start.strftime("%H:%M") == "15:15"  # 15:15+45=16:00 <= 16:00


# ---------------------------------------------------------------------------
# Degradation: a KB with no parseable doctors -> default template, no crash
# ---------------------------------------------------------------------------

def test_degrades_to_default_template_when_no_doctors_parse() -> None:
    profile = build_clinic_profile("# Пустая контора\n\nНичего полезного тут нет.")
    assert profile.is_default is True
    assert profile.timezone == DEFAULT_TIMEZONE
    assert profile.slot_duration_min == DEFAULT_SLOT_DURATION_MIN
    # A generic bookable resource exists, so the engine still produces slots.
    assert profile.doctors and profile.specialties
    now = _midnight(2026, 7, 20)  # Monday
    slots = generate_slots(
        profile, date_from=date(2026, 7, 20), date_to=date(2026, 7, 20), now=now,
    )
    assert slots  # Пн-Сб 09:00-18:00 default template works


def test_default_template_has_no_saturday_off_by_default_but_no_sunday() -> None:
    profile = build_clinic_profile("garbage without a schedule")
    now_sun = _midnight(2026, 7, 26)  # Sunday
    assert generate_slots(
        profile, date_from=date(2026, 7, 26), date_to=date(2026, 7, 26), now=now_sun,
    ) == []


# ---------------------------------------------------------------------------
# Cache keyed by KB content
# ---------------------------------------------------------------------------

def test_get_clinic_profile_caches_by_kb_content() -> None:
    a = get_clinic_profile(_SWAPPED_KB)
    b = get_clinic_profile(_SWAPPED_KB)
    assert a is b  # same text -> cached instance
    c = get_clinic_profile(_SWAPPED_KB + "\n<!-- edit -->")
    assert c is not a  # changed text -> rebuilt
