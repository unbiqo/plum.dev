"""Controlled demo appointment availability for the Medical Center demo.

This is a FICTIONAL, deterministic demo source — never real clinic availability
and never LLM-invented. It lets the assistant offer concrete booking slots and
confirm a demo appointment safely, keyed by a normalized (Russian) specialty.

Also holds the RU normalization used so the summary panel never shows English
values for a known specialty/symptom.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Specialty normalization (EN + declensions -> canonical RU base word)
# ---------------------------------------------------------------------------
# Canonical keys are the KB specialties. Each maps to a list of match stems
# (lowercased). RU declensions match by stem prefix; EN synonyms match exactly.
_SPECIALTY_STEMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("терапевт", ("терапевт", "therapist")),
    ("педиатр", ("педиатр", "pediatric", "paediatric")),
    ("кардиолог", ("кардиолог", "cardiolog")),
    ("эндокринолог", ("эндокринолог", "endocrinolog")),
    ("гастроэнтеролог", ("гастроэнтеролог", "gastroenterolog")),
    ("невролог", ("невролог", "neurolog")),
    ("лор", ("лор", "отоларинголог", "ent", "otolaryngolog")),
    ("дерматолог", ("дерматолог", "dermatolog")),
    ("гинеколог", ("гинеколог", "gynecolog", "gynaecolog")),
    ("уролог", ("уролог", "urolog")),
    ("офтальмолог", ("офтальмолог", "окулист", "ophthalmolog", "oculist")),
)

# How each canonical specialty is shown in the RU summary panel / answers.
_SPECIALTY_DISPLAY: dict[str, str] = {
    "терапевт": "терапевт",
    "педиатр": "педиатр",
    "кардиолог": "кардиолог",
    "эндокринолог": "эндокринолог",
    "гастроэнтеролог": "гастроэнтеролог",
    "невролог": "невролог",
    "лор": "ЛОР",
    "дерматолог": "дерматолог",
    "гинеколог": "гинеколог",
    "уролог": "уролог",
    "офтальмолог": "офтальмолог",
}


def normalize_specialty(raw: str | None) -> str | None:
    """Return the canonical RU specialty base for ``raw`` (or None).

    Handles English synonyms and Russian declensions. For a phrase naming
    several specialties («гастроэнтеролог или терапевт») the first match wins.
    """
    if not raw:
        return None
    low = raw.strip().lower()
    if not low or low == "unknown":
        return None
    # First specialty mentioned in the string wins (scan by position).
    best: tuple[int, str] | None = None
    for canonical, stems in _SPECIALTY_STEMS:
        for stem in stems:
            idx = low.find(stem)
            if idx != -1 and (best is None or idx < best[0]):
                best = (idx, canonical)
    return best[1] if best else None


def specialty_display(raw: str | None) -> str:
    """RU display form for a specialty, normalized. Falls back to the raw text."""
    canonical = normalize_specialty(raw)
    if canonical:
        return _SPECIALTY_DISPLAY[canonical]
    return (raw or "").strip()


def specialty_dative(raw: str | None) -> str:
    """Dative RU form for 'к <specialist>' phrasing (терапевт -> терапевту).

    Every KB specialty ends in a consonant, so appending 'у' is correct for all
    of them (including ЛОР -> ЛОРу). Unknown values are returned unchanged.
    """
    canonical = normalize_specialty(raw)
    if not canonical:
        return (raw or "").strip()
    return _SPECIALTY_DISPLAY[canonical] + "у"


# ---------------------------------------------------------------------------
# Symptom term normalization (known EN clinical words -> RU)
# ---------------------------------------------------------------------------
_SYMPTOM_TERMS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bheadache\b", re.IGNORECASE), "головная боль"),
    (re.compile(r"\bfever\b", re.IGNORECASE), "температура"),
    (re.compile(r"\btemperature\b", re.IGNORECASE), "температура"),
    (re.compile(r"\bcough\b", re.IGNORECASE), "кашель"),
    (re.compile(r"\bsore throat\b", re.IGNORECASE), "боль в горле"),
    (re.compile(r"\bstomach ache\b|\babdominal pain\b", re.IGNORECASE), "боль в животе"),
    (re.compile(r"\bback pain\b", re.IGNORECASE), "боль в спине"),
    (re.compile(r"\brash\b", re.IGNORECASE), "сыпь"),
    (re.compile(r"\bconsultation\b", re.IGNORECASE), "консультация"),
    (re.compile(r"\bappointment\b", re.IGNORECASE), "запись"),
)


def normalize_symptom_terms(raw: str | None) -> str:
    """Replace known English clinical terms with their RU equivalents.

    Only swaps a small closed set; free Russian text is returned unchanged.
    """
    text = (raw or "").strip()
    if not text:
        return ""
    for pattern, replacement in _SYMPTOM_TERMS:
        text = pattern.sub(replacement, text)
    return text


# ---------------------------------------------------------------------------
# Fictional demo availability (day label + time). NOT real clinic availability.
# ---------------------------------------------------------------------------
_DEMO_SLOTS: dict[str, tuple[tuple[str, str], ...]] = {
    "терапевт": (("завтра", "10:00"), ("завтра", "15:30"), ("послезавтра", "11:00")),
    "педиатр": (("сегодня", "16:30"), ("завтра", "12:00"), ("послезавтра", "10:30")),
    "кардиолог": (("завтра", "11:30"), ("послезавтра", "15:00")),
    "невролог": (("завтра", "16:00"), ("послезавтра", "13:00")),
}
_DEFAULT_SLOTS: tuple[tuple[str, str], ...] = (
    ("завтра", "11:00"),
    ("завтра", "16:00"),
    ("послезавтра", "12:00"),
)


def _slot_tuples(specialty: str | None) -> tuple[tuple[str, str], ...]:
    canonical = normalize_specialty(specialty)
    if canonical and canonical in _DEMO_SLOTS:
        return _DEMO_SLOTS[canonical]
    return _DEFAULT_SLOTS


def slots_for(specialty: str | None) -> list[str]:
    """Rendered demo slot strings for a specialty, e.g. ['завтра 10:00', ...]."""
    return [f"{day} {time}" for day, time in _slot_tuples(specialty)]


def format_slots(slots: list[str]) -> str:
    """Join slot strings for a sentence: 'a, b или c'."""
    if not slots:
        return ""
    if len(slots) == 1:
        return slots[0]
    return f"{', '.join(slots[:-1])} или {slots[-1]}"


_ORDINALS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\bперв(?:ый|ое|ая|ых)?\b|\b1[-\s]?(?:й|е|ый|вариант)\b", re.IGNORECASE), 0),
    (re.compile(r"\bвтор(?:ой|ое|ая|ых)?\b|\b2[-\s]?(?:й|е|ой|вариант)\b", re.IGNORECASE), 1),
    (re.compile(r"\bтрет(?:ий|ье|ья|ьих)?\b|\b3[-\s]?(?:й|е|ий|вариант)\b", re.IGNORECASE), 2),
)
_TIME_RE = re.compile(r"\b(\d{1,2})[:.\s](\d{2})\b")
# Order matters: «послезавтра» contains «завтра» as a substring, so it must be
# tested first to avoid a false «завтра» match.
_DAY_WORDS = ("послезавтра", "завтра", "сегодня")


def match_slot(specialty: str | None, message: str) -> str | None:
    """Return the rendered slot the user's message refers to, or None.

    Deterministic: matches by (day + time), a unique bare time, a mentioned day
    if it has a single slot, or an ordinal ('второй вариант'). Never guesses.
    """
    slots = _slot_tuples(specialty)
    if not slots:
        return None
    low = (message or "").lower()

    # 1. Ordinal reference into the offered list.
    for pattern, index in _ORDINALS:
        if pattern.search(low) and index < len(slots):
            day, time = slots[index]
            return f"{day} {time}"

    # 2. Time mentioned in the message.
    times_in_msg = {f"{int(h):d}:{m}" for h, m in _TIME_RE.findall(low)}
    day_in_msg = next((d for d in _DAY_WORDS if d in low), None)
    if times_in_msg:
        # Prefer an exact day+time match.
        for day, time in slots:
            norm = f"{int(time.split(':')[0]):d}:{time.split(':')[1]}"
            if norm in times_in_msg and (day_in_msg is None or day_in_msg == day):
                return f"{day} {time}"
        # Otherwise a unique time across the offered slots.
        for day, time in slots:
            norm = f"{int(time.split(':')[0]):d}:{time.split(':')[1]}"
            if norm in times_in_msg:
                matching = [s for s in slots if f"{int(s[1].split(':')[0]):d}:{s[1].split(':')[1]}" == norm]
                if len(matching) == 1:
                    return f"{day} {time}"

    # 3. A day mentioned with exactly one slot on that day.
    if day_in_msg:
        same_day = [(d, t) for d, t in slots if d == day_in_msg]
        if len(same_day) == 1:
            return f"{same_day[0][0]} {same_day[0][1]}"

    return None
