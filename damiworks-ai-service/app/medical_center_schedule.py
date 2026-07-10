"""Doctor working schedules for the Medical Center demo, parsed from the KB.

The KB already states every doctor's schedule ("Приём: Вт/Пт 09:00–14:00"), so
this module parses THAT rather than duplicating it in code: a KB edit can never
drift from the windows the booking flow offers.

Everything here is deterministic and zero-LLM. It answers three questions the
booking flow could not answer before:

- Which weekday did the user ask for ("давайте на вторник")?
- Does this specialty work that weekday, and between which hours?
- Which demo windows exist on that weekday (never any outside the schedule)?
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .medical_center_kb import get_full_kb_context
from .medical_center_slots import normalize_specialty

# Monday = 0, matching datetime.weekday().
_WEEKDAY_NAMES: tuple[tuple[int, str, str, str], ...] = (
    (0, "понедельник", "в понедельник", "по понедельникам"),
    (1, "вторник", "во вторник", "по вторникам"),
    (2, "среда", "в среду", "по средам"),
    (3, "четверг", "в четверг", "по четвергам"),
    (4, "пятница", "в пятницу", "по пятницам"),
    (5, "суббота", "в субботу", "по субботам"),
    (6, "воскресенье", "в воскресенье", "по воскресеньям"),
)
WEEKDAY_NOMINATIVE = {i: nom for i, nom, _acc, _plural in _WEEKDAY_NAMES}
WEEKDAY_ACCUSATIVE = {i: acc for i, _nom, acc, _plural in _WEEKDAY_NAMES}
WEEKDAY_PLURAL = {i: plural for i, _nom, _acc, plural in _WEEKDAY_NAMES}

# Stems that identify a weekday in free text, in any declension.
_WEEKDAY_STEMS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (0, ("понедельник",)),
    (1, ("вторник",)),
    (2, ("среду", "среда", "среды", "средам", "среде")),
    (3, ("четверг",)),
    (4, ("пятниц",)),
    (5, ("суббот",)),
    (6, ("воскресен",)),
)
# The KB's abbreviated day tokens, used inside "Приём: Вт/Пт 09:00–14:00" and
# ranges like "Пн–Пт".
_KB_DAY_ABBR: dict[str, int] = {
    "пн": 0, "вт": 1, "ср": 2, "чт": 3, "пт": 4, "сб": 5, "вс": 6,
}

# "Приём: Пн/Ср/Пт 09:00–15:00, Сб 10:00–14:00."
_SCHEDULE_LINE_RE = re.compile(r"Приём:\s*([^.]+?)\.", re.IGNORECASE)
_BLOCK_RE = re.compile(
    r"((?:Пн|Вт|Ср|Чт|Пт|Сб|Вс)(?:\s*[–\-/]\s*(?:Пн|Вт|Ср|Чт|Пт|Сб|Вс))*)\s*"
    r"(\d{1,2}:\d{2})\s*[–\-]\s*(\d{1,2}:\d{2})",
    re.IGNORECASE,
)
# The doctor bullet: "- Арман Рахимов — невролог, ... Приём: Вт/Пт 09:00–14:00."
_DOCTOR_LINE_RE = re.compile(r"^-\s+([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)\s+—\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class ScheduleBlock:
    weekdays: frozenset[int]
    start: str  # "09:00"
    end: str    # "14:00"

    def covers(self, weekday: int, hhmm: str | None = None) -> bool:
        if weekday not in self.weekdays:
            return False
        if hhmm is None:
            return True
        return _to_minutes(self.start) <= _to_minutes(hhmm) <= _to_minutes(self.end)


@dataclass(frozen=True)
class DoctorSchedule:
    name: str
    specialty: str  # canonical
    blocks: tuple[ScheduleBlock, ...]

    def works_on(self, weekday: int) -> bool:
        return any(b.covers(weekday) for b in self.blocks)

    def hours_on(self, weekday: int) -> tuple[str, str] | None:
        for block in self.blocks:
            if block.covers(weekday):
                return (block.start, block.end)
        return None


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _to_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _parse_days(token: str) -> frozenset[int]:
    """"Пн/Ср/Пт" -> {0,2,4};  "Пн–Пт" -> {0,1,2,3,4}."""
    token = token.strip().casefold()
    if "–" in token or "-" in token:
        parts = re.split(r"\s*[–\-]\s*", token)
        if len(parts) == 2 and parts[0] in _KB_DAY_ABBR and parts[1] in _KB_DAY_ABBR:
            first, last = _KB_DAY_ABBR[parts[0]], _KB_DAY_ABBR[parts[1]]
            if first <= last:
                return frozenset(range(first, last + 1))
    days = {
        _KB_DAY_ABBR[part.strip()]
        for part in token.split("/")
        if part.strip() in _KB_DAY_ABBR
    }
    return frozenset(days)


def _parse_schedule_text(text: str) -> tuple[ScheduleBlock, ...]:
    blocks: list[ScheduleBlock] = []
    for days_token, start, end in _BLOCK_RE.findall(text):
        weekdays = _parse_days(days_token)
        if weekdays:
            blocks.append(ScheduleBlock(weekdays, start, end))
    return tuple(blocks)


def _load_schedules() -> dict[str, DoctorSchedule]:
    """Parse every doctor bullet in the KB into a schedule, keyed by specialty."""
    schedules: dict[str, DoctorSchedule] = {}
    for first, last, rest in _DOCTOR_LINE_RE.findall(get_full_kb_context()):
        match = _SCHEDULE_LINE_RE.search(rest)
        if not match:
            continue
        blocks = _parse_schedule_text(match.group(1))
        if not blocks:
            continue
        specialty = normalize_specialty(rest.split(",", 1)[0])
        if not specialty or specialty in schedules:
            continue
        schedules[specialty] = DoctorSchedule(f"{first} {last}", specialty, blocks)
    return schedules


_SCHEDULES: dict[str, DoctorSchedule] | None = None


def schedule_for(specialty: str | None) -> DoctorSchedule | None:
    """The (first) KB doctor schedule for a specialty, or None."""
    global _SCHEDULES
    if _SCHEDULES is None:
        _SCHEDULES = _load_schedules()
    canonical = normalize_specialty(specialty)
    return _SCHEDULES.get(canonical) if canonical else None


def weekday_from_text(text: str) -> int | None:
    """The weekday the user asked for ("давайте на вторник" -> 1), or None.

    A weekday named in a NEGATED clause ("не в четверг, а во вторник") must not
    win over the one the user actually wants, so the last named weekday that is
    not immediately preceded by "не" is returned.
    """
    low = (text or "").casefold()
    found: list[tuple[int, int]] = []  # (position, weekday)
    for weekday, stems in _WEEKDAY_STEMS:
        for stem in stems:
            for match in re.finditer(re.escape(stem), low):
                prefix = low[max(0, match.start() - 12):match.start()]
                if re.search(r"\bне\s+(?:в[ово]?\s+)?$", prefix):
                    continue
                found.append((match.start(), weekday))
    if not found:
        return None
    return max(found)[1]  # the last one mentioned wins ("не завтра, а во вторник")


def works_on(specialty: str | None, weekday: int) -> bool:
    schedule = schedule_for(specialty)
    return bool(schedule and schedule.works_on(weekday))


def hours_on(specialty: str | None, weekday: int) -> tuple[str, str] | None:
    schedule = schedule_for(specialty)
    return schedule.hours_on(weekday) if schedule else None


def time_within_schedule(specialty: str | None, weekday: int, hhmm: str) -> bool:
    """True when this specialty actually sees patients then. Never invents."""
    schedule = schedule_for(specialty)
    if not schedule:
        return False
    return any(block.covers(weekday, hhmm) for block in schedule.blocks)


def filter_windows_by_schedule(
    specialty: str | None,
    windows: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    """Drop every (weekday, time) the doctor does not actually work.

    This is the guard the booking flow was missing: a candidate list containing
    Friday 16:00 for a doctor who works Friday 09:00-14:00 must come back empty
    of it, rather than being offered to the patient.
    """
    return [w for w in windows if time_within_schedule(specialty, w[0], w[1])]


def windows_on(specialty: str | None, weekday: int) -> list[str]:
    """Deterministic demo windows for a weekday, always inside the schedule.

    Two per working block: half an hour after opening, and two hours before
    closing. Fictional (like the rest of the demo availability) but never
    outside the doctor's real KB hours.
    """
    schedule = schedule_for(specialty)
    if not schedule:
        return []
    times: list[str] = []
    for block in schedule.blocks:
        if weekday not in block.weekdays:
            continue
        start, end = _to_minutes(block.start), _to_minutes(block.end)
        for candidate in (start + 30, end - 120):
            if start <= candidate <= end and _to_hhmm(candidate) not in times:
                times.append(_to_hhmm(candidate))
    return sorted(times)


def schedule_sentence(specialty: str | None, weekday: int | None = None) -> str:
    """«по вторникам с 09:00 до 14:00», or the whole schedule when no weekday."""
    schedule = schedule_for(specialty)
    if not schedule:
        return ""
    if weekday is not None:
        hours = schedule.hours_on(weekday)
        if not hours:
            return ""
        return f"{WEEKDAY_PLURAL[weekday]} с {hours[0]} до {hours[1]}"
    parts = []
    for block in schedule.blocks:
        days = ", ".join(WEEKDAY_PLURAL[d] for d in sorted(block.weekdays))
        parts.append(f"{days} с {block.start} до {block.end}")
    return "; ".join(parts)


def working_days_sentence(specialty: str | None) -> str:
    """«вторник и пятница» — the days this specialty sees patients."""
    schedule = schedule_for(specialty)
    if not schedule:
        return ""
    days = sorted({d for block in schedule.blocks for d in block.weekdays})
    names = [dict((i, nom) for i, nom, _a, _p in _WEEKDAY_NAMES)[d] for d in days]
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} и {names[-1]}"
