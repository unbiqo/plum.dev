"""Booking slot guardrail (deterministic, no LLM).

Hard rule: the model may only speak appointment slots that came from the slot
provider (today the deterministic demo source in ``medical_center_slots``,
tomorrow a real SoM API). It must never generate dates/times of its own. If
the final answer mentions a slot the provider did not supply — or any concrete
slot while the provider supplied none — the answer is replaced with a safe
"let me check and come back" message.
"""
from __future__ import annotations

import re

# What the model must say when it has no provider-supplied slots to offer.
SAFE_NO_SLOTS_ANSWER = (
    "Уточню свободное время у администратора и вернусь к вам с ближайшими окнами."
)

# Order matters: «послезавтра» contains «завтра» (checked first).
_DAY_WORDS = ("послезавтра", "завтра", "сегодня")
_DAY_RE = re.compile(r"послезавтра|завтра|сегодня", re.IGNORECASE)
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:.](\d{2})\b")
# Clinic working-hours ranges ("с 9:00 до 18:00") are facts, not slot claims.
_WORKING_HOURS_RE = re.compile(
    r"(?:с|от)\s+[01]?\d[:.]\d{2}\s+(?:до|по|—|-)\s*[01]?\d[:.]\d{2}",
    re.IGNORECASE,
)


def parse_slot_label(label: str) -> tuple[str, str] | None:
    """Parse a provider slot label ("завтра 10:00") into ("завтра", "10:00")."""
    text = (label or "").strip().lower()
    day = next((d for d in _DAY_WORDS if d in text), None)
    match = _TIME_RE.search(text)
    if day is None or match is None:
        return None
    return (day, f"{int(match.group(1)):02d}:{match.group(2)}")


def _mentioned_slots(answer: str) -> tuple[set[tuple[str, str]], set[str]]:
    """Extract (day, HH:MM) pairs and bare HH:MM times mentioned in ``answer``.

    Working-hours ranges are excluded — stating "работаем с 9:00 до 18:00" is
    not a booking claim.
    """
    text = _WORKING_HOURS_RE.sub(" ", (answer or "").lower())
    pairs: set[tuple[str, str]] = set()
    bare_times: set[str] = set()
    for day in _DAY_WORDS:
        # Cyrillic-letter lookbehind: «завтра» inside «послезавтра» is not a match.
        for day_match in re.finditer(rf"(?<![а-яё]){day}", text):
            window = text[day_match.start() : day_match.start() + 40]
            for time_match in _TIME_RE.finditer(window):
                pairs.add((day, f"{int(time_match.group(1)):02d}:{time_match.group(2)}"))
    paired_times = {time for _, time in pairs}
    for time_match in _TIME_RE.finditer(text):
        normalized = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
        if normalized not in paired_times:
            bare_times.add(normalized)
    return pairs, bare_times


def enforce_slot_guardrail(
    *,
    answer: str,
    offered_slots: list[str],
    booking_context: bool,
    safe_answer: str = SAFE_NO_SLOTS_ANSWER,
) -> tuple[str, bool]:
    """Enforce the slots-come-from-the-provider rule on a final answer.

    ``offered_slots`` — slot labels the provider supplied for this turn (the
    already-confirmed slot, if any, must be included by the caller).
    ``booking_context`` — True when this turn is about scheduling (booking
    intent/planner intent), so bare times without a day word are slot claims
    too. Outside a booking context a bare time ("приём длится до 16:00") is
    tolerated; a day+time pair is always treated as a slot claim.

    Returns ``(answer, replaced)``. Never raises.
    """
    if not answer or not answer.strip():
        return answer, False

    try:
        allowed_pairs = {
            parsed for label in offered_slots if (parsed := parse_slot_label(label))
        }
        allowed_times = {time for _, time in allowed_pairs}
        mentioned_pairs, mentioned_bare = _mentioned_slots(answer)

        violations = {pair for pair in mentioned_pairs if pair not in allowed_pairs}
        if booking_context:
            # Bare slot claims in a booking turn are only allowed when the
            # provider actually offered that time.
            if any(time not in allowed_times for time in mentioned_bare):
                return safe_answer, True

        if violations:
            return safe_answer, True
        return answer, False
    except Exception:  # defensive: a guardrail must never break a turn
        return answer, False
