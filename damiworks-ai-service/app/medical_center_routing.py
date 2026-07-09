"""Deterministic symptom -> specialist routing for the Medical Center demo.

Safe administrative routing, NOT diagnosis. The router first classifies the
complaint domain (skin / joints-trauma / nerve / unclear general symptom) and
only then uses body location as context. This prevents false positives where a
location word like "плечо" or "рука" is mistaken for a joint complaint.

Emergency red flags still preempt this before ``route_symptom`` is called.

Priority for overlapping clues:
1. Dermatology / skin clues           -> дерматолог.
2. Inflammatory / multi-joint clues   -> ревматолог.
3. Nerve-like clues                   -> невролог.
4. Musculoskeletal evidence           -> травматолог-ортопед.
5. Unclear general symptom phrases    -> терапевт.
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
    domain: str = ""     # complaint domain used by the deterministic router
    confidence: float = 0.0


_PRICE_OR_ADMIN_RE = re.compile(
    r"сколько\s+сто|стоимост|цена|прайс|поч[её]м|оплат|скидк",
    re.IGNORECASE,
)

# Skin terms win over body-location words ("пятно на плече" is dermatology, not
# shoulder-joint routing).
_SKIN_RE = re.compile(
    r"\bкож\w*|пятн\w*|сып[ьи]\w*|высыпани\w*|покраснен\w*\s+кож\w*"
    r"|зуд\w*|чеш\w*|шелушени\w*|родинк\w*|прыщ\w*|акне"
    r"|раздражени\w*|волдыр\w*|пузырьк\w*|дерматит|экзем\w*|грибок\w*",
    re.IGNORECASE,
)


# Body-location / joint words are context only. They do not route to
# травматолог-ортопед unless paired with pain, trauma, swelling, load, or
# movement-limitation evidence.
_MSK_LOCATION_RE = re.compile(
    r"колен|сустав|плеч[оаеиуе]|локот|локт|голеностоп|лодыжк|запяст|кист"
    r"|рук[ауеи]?|ног[ауеи]?",
    re.IGNORECASE,
)
_MSK_PAIN_LOCATION_RE = re.compile(
    r"(?:бол\w*|боль)[^.!?]{0,45}(?:колен|сустав|плеч|локот|локт|голеностоп|лодыжк|запяст|кист|рук|ног)"
    r"|(?:колен|сустав|плеч|локот|локт|голеностоп|лодыжк|запяст|кист|рук|ног)[^.!?]{0,45}(?:бол\w*|боль)",
    re.IGNORECASE,
)
_MSK_FUNCTION_RE = re.compile(
    r"не\s+могу\s+(?:согнуть|разогнуть|поднять|опустить|наступить|двигать)"
    r"|ограничени\w+\s+движени|боль\s+при\s+движени|щ[её]лка\w*|хруст\w*"
    r"|опух\w*[^.!?]{0,30}(?:сустав|колен|плеч|локот|лодыжк|голеностоп)"
    r"|(?:сустав|колен|плеч|локот|лодыжк|голеностоп)[^.!?]{0,30}опух\w*"
    r"|после\s+(?:тренировк|нагрузк)",
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
    r"онемен|немеет|неметь|прострел|отда[её]т\s+в\s+(?:ногу|руку)"
    r"|от\s+(?:поясниц\w+|ше[еи])\s+в\s+(?:ногу|руку)"
    r"|боль\s+(?:ид[её]т|отда[её]т|стреляет)\s+[^.!?]*(?:ног|рук)"
    r"|слабост\w+\s+в\s+(?:ноге|руке)|покалыван|потеря\s+чувствительн|мурашк"
    r"|нарушени\w+\s+походк",
    re.IGNORECASE,
)

_TRAUMA_RE = re.compile(r"травм|ударил|упал|падени|подверн|растяжени|вывих|ушиб", re.IGNORECASE)

_GENERAL_UNCLEAR_RE = re.compile(
    r"непонятн\w+\s+ощущени|плохо\s+себя\s+чувств|не\s+знаю,\s*что\s+со\s+мной"
    r"|общее\s+недомогани|слабость\s+без\s+температур",
    re.IGNORECASE,
)

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


def _skin_complaint_label(low: str) -> str:
    if "пятн" in low and "кож" in low:
        return "пятно на коже"
    if "сып" in low or "высыпани" in low:
        return "сыпь"
    if "родинк" in low:
        return "родинка"
    if "зуд" in low or "чеш" in low:
        return "зуд кожи"
    if "покраснен" in low and "кож" in low:
        return "покраснение кожи"
    return "жалоба на кожу"


def _skin_explanation(label: str) -> str:
    if label == "пятно на коже":
        return (
            "Если появилось пятно на коже, лучше начать с дерматолога. "
            "Врач посмотрит кожу и подскажет, нужно ли дополнительное обследование."
        )
    if label == "сыпь":
        return (
            "Если появилась сыпь, лучше начать с дерматолога. "
            "Врач посмотрит кожу и подскажет, нужно ли дополнительное обследование."
        )
    if label == "родинка":
        return (
            "Если родинка изменилась или стала беспокоить, лучше начать с дерматолога. "
            "Врач посмотрит кожу и подскажет, нужно ли дополнительное обследование."
        )
    return (
        "Если появилась жалоба на коже, лучше начать с дерматолога. "
        "Врач посмотрит кожу и подскажет, нужно ли дополнительное обследование."
    )


def _has_msk_evidence(low: str) -> bool:
    if _MSK_PAIN_LOCATION_RE.search(low):
        return True
    if _TRAUMA_RE.search(low) and _MSK_LOCATION_RE.search(low):
        return True
    return bool(_MSK_FUNCTION_RE.search(low) and _MSK_LOCATION_RE.search(low))


def route_symptom(message: str) -> RoutingResult | None:
    """Deterministic symptom routing, or None to defer to the LLM."""
    low = (message or "").lower()
    if not low.strip() or _PRICE_OR_ADMIN_RE.search(low):
        return None

    skin = bool(_SKIN_RE.search(low))
    msk = _has_msk_evidence(low)
    neuro = bool(_NEURO_LIMB_RE.search(low))
    rheum = bool(_RHEUM_CLUE_RE.search(low)) or (
        _multi_joint(low) and "бол" in low and not _TRAUMA_RE.search(low)
    )

    if skin:
        label = _skin_complaint_label(low)
        return RoutingResult(
            specialty="дерматолог",
            complaint=label,
            explanation=_skin_explanation(label),
            cta="Могу подобрать ближайшее окно к дерматологу?",
            domain="skin",
            confidence=0.95,
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
            domain="rheumatology",
            confidence=0.9,
        )

    if neuro:
        return RoutingResult(
            specialty="невролог",
            complaint="боль с онемением/слабостью",
            explanation=(
                "Если есть онемение, покалывание, прострел или боль отдаёт от шеи/поясницы "
                "в руку или ногу, лучше показаться неврологу — он оценит нервные корешки "
                "и чувствительность."
            ),
            cta="Могу подобрать ближайшее окно к неврологу?",
            domain="neurology",
            confidence=0.9,
        )

    if msk:
        nom, prep = _joint_forms(low)
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
            domain="musculoskeletal",
            confidence=0.88,
        )

    if _GENERAL_UNCLEAR_RE.search(low):
        return RoutingResult(
            specialty="терапевт",
            complaint="непонятное самочувствие",
            explanation=(
                "Если самочувствие непонятное и нет явных признаков узкого специалиста, "
                "лучше начать с терапевта. Он проведёт первичный осмотр и подскажет "
                "дальнейший маршрут."
            ),
            cta="Могу подобрать ближайшее окно к терапевту?",
            domain="general",
            confidence=0.55,
        )

    return None
