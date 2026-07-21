"""Normalized clinic profile, built from the tenant knowledge base.

The medical demo's knowledge base is a markdown document (today MedNova, tomorrow
any other company). NOTHING about a specific clinic is hardcoded here: the
profile — name, working hours, specialties and doctors with their schedules — is
parsed out of that markdown. Swap the KB text and the profile rebuilds itself
without a code change (see tests/test_clinic_profile.py::KB-SWAP).

The profile is the source of truth the booking slot engine (app/slot_engine.py)
runs on. It is intentionally storage-agnostic: no Supabase, no I/O here beyond
reading the demo markdown, so it stays a pure function of the KB text.

Degradation: a KB with no parseable doctors/schedule yields a default template
(Пн-Сб 09:00-18:00, 30-минутный слот, ``is_default=True``) with one generic
bookable resource, so the demo never crashes on an unfamiliar KB.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from threading import Lock

from .medical_center_kb import get_raw_markdown
from .medical_center_schedule import (
    ScheduleBlock,
    _BLOCK_RE,
    _DOCTOR_LINE_RE,
    _SCHEDULE_LINE_RE,
    _parse_schedule_text,
)

# Clinic-level defaults for anything the KB does not state explicitly.
DEFAULT_TIMEZONE = "Asia/Almaty"
DEFAULT_SLOT_DURATION_MIN = 30
# Default template working hours: Пн-Сб 09:00-18:00.
_DEFAULT_WORKING_BLOCK = ScheduleBlock(frozenset(range(0, 6)), "09:00", "18:00")

# Optional KB override lines (not present in MedNova today; here so a future
# tenant KB can set them without a code change).
_TIMEZONE_RE = re.compile(r"(?:Часовой пояс|Таймзона|Timezone)\s*:\s*([A-Za-z]+/[A-Za-z_]+)")
_SLOT_DURATION_RE = re.compile(r"(?:Длительность приёма|Длительность слота)[ \t]*:[ \t]*(\d{1,3})")
# "Режим работы: Пн–Пт 08:00–20:00, Сб 09:00–17:00, Вс 10:00–15:00."
# ``[ \t]*`` (not ``\s*``) after the colon so the value stays on the SAME line:
# a bare header like "Контакты и режим работы:\n- Адрес: ..." must not capture
# the next line.
_WORKING_HOURS_RE = re.compile(r"Режим работы[ \t]*:[ \t]*([^\n]+)", re.IGNORECASE)
# The H1 clinic name: "# MedNova Clinic — база знаний ...".
_CLINIC_NAME_RE = re.compile(r"^#\s+(.+?)(?:\s+[—–]\s+.*)?$", re.MULTILINE)


def _slugify(name: str) -> str:
    """Stable id from a specialty name. Cyrillic is kept — ids are internal keys,
    never shown to the user; only structural chars are normalized."""
    slug = re.sub(r"\s+", "_", name.strip().casefold())
    slug = re.sub(r"[^\w-]", "", slug, flags=re.UNICODE)
    return slug.strip("_") or "specialty"


@dataclass(frozen=True)
class Specialty:
    id: str
    name: str


@dataclass(frozen=True)
class Doctor:
    id: str
    name: str
    specialty_id: str
    blocks: tuple[ScheduleBlock, ...]

    def works_on(self, weekday: int) -> bool:
        return any(b.covers(weekday) for b in self.blocks)


@dataclass(frozen=True)
class ClinicProfile:
    name: str
    timezone: str
    slot_duration_min: int
    working_hours: tuple[ScheduleBlock, ...]
    specialties: tuple[Specialty, ...]
    doctors: tuple[Doctor, ...]
    is_default: bool = False

    def specialty_by_id(self, specialty_id: str) -> Specialty | None:
        return next((s for s in self.specialties if s.id == specialty_id), None)

    def doctor_by_id(self, doctor_id: str) -> Doctor | None:
        return next((d for d in self.doctors if d.id == doctor_id), None)

    def doctors_for_specialty(self, specialty_id: str) -> tuple[Doctor, ...]:
        return tuple(d for d in self.doctors if d.specialty_id == specialty_id)


def _parse_clinic_name(markdown: str) -> str:
    match = _CLINIC_NAME_RE.search(markdown)
    if match:
        # Strip a trailing "— описание" that the greedy split may have kept.
        return match.group(1).split(" — ")[0].split(" – ")[0].strip()
    return "Клиника"


def _parse_working_hours(markdown: str) -> tuple[ScheduleBlock, ...]:
    match = _WORKING_HOURS_RE.search(markdown)
    if not match:
        return ()
    return _parse_schedule_text(match.group(1))


def _specialty_name_from_doctor_rest(rest: str) -> str:
    """The specialty a doctor bullet declares, e.g. "офтальмолог".

    The bullet is "<специальность>, врач <категория> (полное имя ...), стаж ...".
    Drop the parenthetical first (Нурбек's "(полное имя ...)" sits before the
    first comma), then take the text up to the first comma.
    """
    without_parens = re.sub(r"\([^)]*\)", "", rest)
    return without_parens.split(",", 1)[0].strip()


def _parse_doctors(
    markdown: str,
) -> tuple[tuple[Doctor, ...], tuple[Specialty, ...]]:
    """Every doctor bullet with a parseable schedule, plus the specialties they
    cover. Specialties are derived from the KB text, not a hardcoded table, so a
    swapped KB (different professions entirely) still produces a valid profile.
    """
    doctors: list[Doctor] = []
    specialties: dict[str, Specialty] = {}
    seen_doctor_ids: set[str] = set()

    for first, last, rest in _DOCTOR_LINE_RE.findall(markdown):
        schedule_match = _SCHEDULE_LINE_RE.search(rest)
        if not schedule_match:
            continue
        blocks = _parse_schedule_text(schedule_match.group(1))
        if not blocks:
            continue
        specialty_name = _specialty_name_from_doctor_rest(rest)
        if not specialty_name:
            continue
        specialty_id = _slugify(specialty_name)
        specialties.setdefault(specialty_id, Specialty(specialty_id, specialty_name))

        name = f"{first} {last}"
        doctor_id = _slugify(name)
        # Guard against a duplicate name collision (keep the first).
        if doctor_id in seen_doctor_ids:
            continue
        seen_doctor_ids.add(doctor_id)
        doctors.append(Doctor(doctor_id, name, specialty_id, blocks))

    return tuple(doctors), tuple(specialties.values())


def _default_profile(name: str, working_hours: tuple[ScheduleBlock, ...]) -> ClinicProfile:
    """Degraded template used when the KB has no parseable doctors/schedule."""
    hours = working_hours or (_DEFAULT_WORKING_BLOCK,)
    specialty = Specialty("консультация", "консультация")
    # A single generic, unnamed bookable resource so the engine can still make
    # slots. No fabricated human name (label rendering handles an empty name).
    doctor = Doctor("specialist", "", specialty.id, hours)
    return ClinicProfile(
        name=name,
        timezone=DEFAULT_TIMEZONE,
        slot_duration_min=DEFAULT_SLOT_DURATION_MIN,
        working_hours=hours,
        specialties=(specialty,),
        doctors=(doctor,),
        is_default=True,
    )


def build_clinic_profile(kb_markdown: str) -> ClinicProfile:
    """Parse a tenant KB markdown into a normalized ClinicProfile (pure function)."""
    name = _parse_clinic_name(kb_markdown)
    working_hours = _parse_working_hours(kb_markdown)

    tz_match = _TIMEZONE_RE.search(kb_markdown)
    timezone = tz_match.group(1) if tz_match else DEFAULT_TIMEZONE
    dur_match = _SLOT_DURATION_RE.search(kb_markdown)
    slot_duration = int(dur_match.group(1)) if dur_match else DEFAULT_SLOT_DURATION_MIN

    doctors, specialties = _parse_doctors(kb_markdown)
    if not doctors:
        return _default_profile(name, working_hours)

    return ClinicProfile(
        name=name,
        timezone=timezone,
        slot_duration_min=slot_duration,
        working_hours=working_hours or (_DEFAULT_WORKING_BLOCK,),
        specialties=specialties,
        doctors=doctors,
        is_default=False,
    )


# ---------------------------------------------------------------------------
# Cache keyed by KB content hash: change the KB -> profile rebuilds, no code
# change. Bounded to the most recent KB text (one entry).
# ---------------------------------------------------------------------------
_CACHE_LOCK = Lock()
_CACHE: dict[str, ClinicProfile] = {}


def get_clinic_profile(kb_markdown: str | None = None) -> ClinicProfile:
    """The ClinicProfile for the given KB markdown (defaults to the current
    medical demo KB). Cached by a hash of the markdown text."""
    markdown = kb_markdown if kb_markdown is not None else get_raw_markdown()
    key = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            return cached
        profile = build_clinic_profile(markdown)
        _CACHE.clear()  # bound to the most recent KB only
        _CACHE[key] = profile
        return profile
