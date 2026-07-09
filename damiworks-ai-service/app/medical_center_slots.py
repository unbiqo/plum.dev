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
    ("стоматолог", ("стоматолог", "dentist", "dental")),
    ("травматолог-ортопед", ("травматолог", "ортопед", "orthoped", "traumatolog")),
    ("ревматолог", ("ревматолог", "rheumatolog")),
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
    "стоматолог": "стоматолог",
    "травматолог-ортопед": "травматолог-ортопед",
    "ревматолог": "ревматолог",
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

    Every KB specialty part ends in a consonant, so appending 'у' is correct
    (ЛОР -> ЛОРу). Hyphenated names decline both parts
    (травматолог-ортопед -> травматологу-ортопеду). Unknown text is unchanged.
    """
    canonical = normalize_specialty(raw)
    if not canonical:
        return (raw or "").strip()
    display = _SPECIALTY_DISPLAY[canonical]
    return "-".join(part + "у" for part in display.split("-"))


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
    (re.compile(r"\bsneezing\b|\bsneeze\b", re.IGNORECASE), "чихание"),
    (re.compile(r"\bredness\b", re.IGNORECASE), "покраснение"),
    (re.compile(r"\brunny nose\b", re.IGNORECASE), "насморк"),
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
    "дерматолог": (("завтра", "14:30"), ("послезавтра", "11:30"), ("послезавтра", "16:00")),
    "стоматолог": (("сегодня", "17:00"), ("завтра", "14:00"), ("послезавтра", "12:30")),
    "травматолог-ортопед": (("завтра", "12:30"), ("завтра", "17:00"), ("послезавтра", "10:30")),
    "ревматолог": (("завтра", "13:30"), ("послезавтра", "15:30")),
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
_TIME_RE = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")  # explicit HH:MM
_BARE_HOUR_RE = re.compile(r"(?<!\d)(\d{1,2})(?!\d)")
# Order matters: «послезавтра» contains «завтра» as a substring, so it must be
# tested first to avoid a false «завтра» match.
_DAY_WORDS = ("послезавтра", "завтра", "сегодня")
# Time-of-day qualifiers that disambiguate a bare hour (4 дня -> 16:00).
_QUALIFIER_PM_RE = re.compile(r"\bдня\b|\bдн[её]м\b|\bвечер\w*|\bпополудни\b", re.IGNORECASE)
_QUALIFIER_AM_RE = re.compile(r"\bутра\b|\bутром\b|\bноч[иь]\w*", re.IGNORECASE)


def resolve_slot(specialty: str | None, message: str) -> tuple[str, str | None]:
    """Map a natural-language reply to an offered demo slot.

    Returns ``(kind, slot)`` where ``kind`` is:
    - ``"matched"`` — confident, ``slot`` is the chosen "день ЧЧ:ММ";
    - ``"suggest"`` — one plausible guess but ambiguous, ask "хотите X?";
    - ``"none"``    — nothing offered matched, ``slot`` is None.

    Handles ordinals, explicit HH:MM, a bare hour ("в 16"), 12-hour phrasing
    ("в 4 дня" -> 16:00), and a day word that disambiguates a small hour
    ("завтра в 4" -> the offered afternoon slot). A bare small hour with no day
    and no качественный qualifier stays a *suggestion* so we confirm instead of
    guessing silently.
    """
    slots = _slot_tuples(specialty)
    if not slots:
        return ("none", None)
    low = (message or "").lower()

    for pattern, index in _ORDINALS:
        if pattern.search(low) and index < len(slots):
            day, time = slots[index]
            return ("matched", f"{day} {time}")

    day_in_msg = next((d for d in _DAY_WORDS if d in low), None)
    pm = bool(_QUALIFIER_PM_RE.search(low))
    am = bool(_QUALIFIER_AM_RE.search(low))

    explicit = {(int(h), int(m)) for h, m in _TIME_RE.findall(low)}
    low_wo_times = _TIME_RE.sub(" ", low)
    bare = [int(x) for x in _BARE_HOUR_RE.findall(low_wo_times) if 0 <= int(x) <= 23]

    confident: set[tuple[int, int]] = set(explicit)
    ambiguous: set[tuple[int, int]] = set()
    for h in bare:
        if h >= 13:
            confident.add((h, 0))
        elif pm:
            confident.add((12 if h == 12 else h + 12, 0))
        elif am:
            confident.add((0 if h == 12 else h, 0))
        else:
            target = confident if day_in_msg else ambiguous
            for cand in {h, h if h >= 12 else h + 12}:
                target.add((cand, 0))

    def _match(cands: set[tuple[int, int]]) -> list[str]:
        found: list[str] = []
        for sday, stime in slots:
            if day_in_msg is not None and day_in_msg != sday:
                continue
            sh, sm = int(stime.split(":")[0]), int(stime.split(":")[1])
            if any(ch == sh and (cm == sm or cm == 0) for ch, cm in cands):
                label = f"{sday} {stime}"
                if label not in found:
                    found.append(label)
        return found

    conf = _match(confident)
    if len(conf) == 1:
        return ("matched", conf[0])
    if len(conf) >= 2:
        return ("none", None)  # ambiguous among several confident hits — clarify
    amb = _match(ambiguous)
    if len(amb) == 1:
        return ("suggest", amb[0])

    # A lone day word with exactly one slot on that day.
    if day_in_msg and not explicit and not bare:
        same_day = [f"{d} {t}" for d, t in slots if d == day_in_msg]
        if len(same_day) == 1:
            return ("matched", same_day[0])

    return ("none", None)


def match_slot(specialty: str | None, message: str) -> str | None:
    """Confident slot match only (or None) — thin wrapper over resolve_slot."""
    kind, slot = resolve_slot(specialty, message)
    return slot if kind == "matched" else None
