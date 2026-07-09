"""Deterministic symptom -> specialist routing for the Medical Center demo.

Safe administrative routing, NOT diagnosis. Maps common musculoskeletal / joint
complaints to the most appropriate starting specialist with warm, non-diagnostic
wording, so obvious cases (knee pain -> травматолог-ортопед) route consistently
without depending on the LLM. Emergency red flags still preempt this (they are
handled earlier by ``detect_red_flags``).

Priority for overlapping clues:
1. Inflammatory / multi-joint clues  -> ревматолог.
2. A joint complaint (колено/плечо/…) -> травматолог-ортопед
   (mentions невролог only if nerve-like clues are also present).
3. Nerve-like limb/back clues alone   -> невролог.
Everything else returns None and is left to the existing planner/writer flow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingResult:
    specialty: str      # canonical RU specialty (matches slots/KB)
    complaint: str      # short RU complaint label for the summary panel
    explanation: str    # warm, non-diagnostic routing explanation
    cta: str            # invitation to show windows for that specialty


# Musculoskeletal joints (spine is intentionally excluded — plain back/neck pain
# stays with the existing невролог routing).
_JOINT_RE = re.compile(
    r"колен|\bсустав|плеч[оаеиуе]|\bлокот|\bлокт|голеностоп|лодыжк"
    r"|растяжени|вывих|\bсвязк|потянул\w*\s+(?:ногу|плечо|руку|мышц)"
    r"|подверн\w+\s+(?:ногу|стопу|лодыжк)|ушиб\w*\s+(?:колен|сустав|ног|руку|плеч)",
    re.IGNORECASE,
)

# Inflammatory / systemic clues -> rheumatologist.
_RHEUM_CLUE_RE = re.compile(
    r"утренн\w+\s+скованност|скованност\w+\s+(?:по\s+утр|утр|с\s+утр)"
    r"|припухл\w+\s+сустав|сустав\w*\s+припух|симметричн"
    r"|несколько\s+сустав|мн(?:ого|ожеств)\w*\s+сустав|болят\s+сустав"
    r"|\bартрит|ревмат|аутоиммун|систем\w+\s+заболеван",
    re.IGNORECASE,
)

# Nerve-like clues (radicular / neuropathic) -> neurologist.
_NEURO_LIMB_RE = re.compile(
    r"онемен|немеет|неметь|прострел|отда[её]т\s+в\s+ногу"
    r"|от\s+поясниц\w+\s+в\s+ногу|боль\s+(?:ид[её]т|отда[её]т|стреляет)\s+[^.!?]*ног"
    r"|слабост\w+\s+в\s+ноге|покалыван|потеря\s+чувствительн|мурашк"
    r"|нарушени\w+\s+походк",
    re.IGNORECASE,
)

_TRAUMA_RE = re.compile(r"травм|ударил|упал|падени|подверн|растяжени|вывих|ушиб", re.IGNORECASE)

# Distinct joint tokens — 2+ different joints hints at a systemic (rheum) picture.
_MULTI_JOINT_TOKENS = ("колен", "кист", "пальц", "локот", "плеч", "голеностоп", "лодыжк", "запяст")

# Joint word -> (nominative label, prepositional form for "боль в …").
_JOINT_LABELS: tuple[tuple[str, str, str], ...] = (
    ("колен", "колено", "колене"),
    ("плеч", "плечо", "плече"),
    ("локот", "локоть", "локте"),
    ("локт", "локоть", "локте"),
    ("голеностоп", "голеностоп", "голеностопе"),
    ("лодыжк", "лодыжка", "лодыжке"),
)


def _multi_joint(low: str) -> bool:
    return sum(1 for token in set(_MULTI_JOINT_TOKENS) if token in low) >= 2


def _joint_forms(low: str) -> tuple[str, str]:
    """Return (nominative, prepositional) for the joint mentioned, else generic."""
    for token, nom, prep in _JOINT_LABELS:
        if token in low:
            return nom, prep
    return "сустав", "суставе"


def route_symptom(message: str) -> RoutingResult | None:
    """Deterministic musculoskeletal/nerve routing, or None to defer to the LLM."""
    low = (message or "").lower()

    joint = bool(_JOINT_RE.search(low))
    neuro = bool(_NEURO_LIMB_RE.search(low))
    rheum = bool(_RHEUM_CLUE_RE.search(low)) or (
        _multi_joint(low) and "бол" in low and not _TRAUMA_RE.search(low)
    )

    if rheum:
        return RoutingResult(
            specialty="ревматолог",
            complaint="боль в суставах",
            explanation=(
                "Если суставы беспокоят в нескольких местах, есть скованность по утрам "
                "или припухлость, лучше начать с ревматолога — он оценит, нет ли "
                "воспалительного процесса, и при необходимости направит к смежному специалисту."
            ),
            cta="Могу подобрать ближайшее окно к ревматологу?",
        )

    if joint:
        nom, prep = _joint_forms(low)
        if neuro:
            explanation = (
                f"При боли именно в {prep} обычно начинают с травматолога-ортопеда. "
                "Если боль отдаёт от поясницы, есть онемение или слабость в ноге, может "
                "понадобиться невролог — врач сориентирует на приёме."
            )
        else:
            explanation = (
                f"Если беспокоит {nom}, лучше начать с травматолога-ортопеда — он оценит "
                "сустав, движение и нагрузку или возможную старую травму. Если появятся "
                "признаки воспаления, врач подскажет, нужен ли ревматолог."
            )
        return RoutingResult(
            specialty="травматолог-ортопед",
            complaint=f"боль в {prep}",
            explanation=explanation,
            cta="Могу подобрать ближайшее окно к травматологу-ортопеду?",
        )

    if neuro:
        return RoutingResult(
            specialty="невролог",
            complaint="боль с онемением/слабостью",
            explanation=(
                "Если боль отдаёт от поясницы в ногу, есть онемение, слабость или "
                "покалывание, лучше показаться неврологу — он оценит нервные корешки "
                "и чувствительность."
            ),
            cta="Могу подобрать ближайшее окно к неврологу?",
        )

    return None
