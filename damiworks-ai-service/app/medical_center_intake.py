"""Generic medical-complaint understanding for the Medical Center demo.

Deterministic, zero-LLM. Turns a free-text complaint into a small structured
record — *what happened, where, to whom, how risky, what to ask next* — so the
demo understands the SHAPE of a complaint instead of recognising one hardcoded
body part at a time. "Дискомфорт в икрах", "надорвал бицепс", "порезал язык",
"сын порезал палец", "ударился головой" and "прищемил палец" all flow through
the same three detectors (complaint type, body part, who) and the same
complaint-type-driven safety screen.

This layer never diagnoses and never treats. It only:
- names the complaint in plain Russian (for state/summary),
- asks the safety questions that the complaint TYPE warrants,
- picks a starting specialty (administrative routing, from the KB's list).

True emergencies (``detect_red_flags``) short-circuit before this module runs.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace

from .medical_center_slots import normalize_specialty
from .schemas import ChatHistoryMessage

# Complaint taxonomy. Response rules key off THIS, never off a body part, so a
# new body part never needs a new flow.
COMPLAINT_TYPES = (
    "pain_discomfort",
    "strain_or_sprain",
    "cut_or_wound",
    "impact_or_head_injury",
    "gait_limping",
    "back_pain",
    "swelling",
    "numbness_or_weakness",
    "respiratory_or_chest",
    "infection_or_fever",
    "child_case",
    "unknown",
)

# Injury-type complaints always get a safety screen: the user already told us an
# event happened, and "есть ли травма?" would be a silly question. A plain
# pain/discomfort complaint is screened only when nothing routes it (see
# ``needs_safety_screen``) — a knee or stomach complaint has a routing rule and
# must keep going straight to the right specialist.
_SCREEN_COMPLAINT_TYPES = frozenset({
    "strain_or_sprain", "cut_or_wound", "impact_or_head_injury", "gait_limping",
    "back_pain",
})


@dataclass(frozen=True)
class BodyPart:
    nom: str   # "икры"
    gen: str   # "икры"      -> "порез икры"
    prep: str  # "в икрах"   -> "дискомфорт в икрах"
    region: str  # arm | leg | head | mouth | torso | other


# Most specific first: "запястье" must win over the generic "рука", "икра" over
# "нога". A trailing generic entry keeps an unmapped part from breaking anything.
_BODY_PARTS: tuple[tuple[re.Pattern[str], BodyPart], ...] = (
    (re.compile(r"икр\w*", re.I), BodyPart("икры", "икры", "в икрах", "leg")),
    (re.compile(r"голен(?!остоп)\w*", re.I), BodyPart("голень", "голени", "в голени", "leg")),
    (re.compile(r"бицепс\w*", re.I), BodyPart("бицепс", "бицепса", "в бицепсе", "arm")),
    (re.compile(r"трицепс\w*", re.I), BodyPart("трицепс", "трицепса", "в трицепсе", "arm")),
    (re.compile(r"запяст\w*", re.I), BodyPart("запястье", "запястья", "в запястье", "arm")),
    (re.compile(r"предплеч\w*", re.I), BodyPart("предплечье", "предплечья", "в предплечье", "arm")),
    (re.compile(r"локот\w*|локт\w*", re.I), BodyPart("локоть", "локтя", "в локте", "arm")),
    (re.compile(r"плеч\w*", re.I), BodyPart("плечо", "плеча", "в плече", "arm")),
    (re.compile(r"кист[ьияей]\w*", re.I), BodyPart("кисть", "кисти", "в кисти", "arm")),
    (re.compile(r"пальц\w*|палец", re.I), BodyPart("палец", "пальца", "на пальце", "arm")),
    (re.compile(r"колен\w*", re.I), BodyPart("колено", "колена", "в колене", "leg")),
    (re.compile(r"голеностоп\w*", re.I), BodyPart("голеностоп", "голеностопа", "в голеностопе", "leg")),
    (re.compile(r"лодыжк\w*", re.I), BodyPart("лодыжка", "лодыжки", "в лодыжке", "leg")),
    (re.compile(r"стоп[аеуы]\w*", re.I), BodyPart("стопа", "стопы", "в стопе", "leg")),
    (re.compile(r"голов\w*", re.I), BodyPart("голова", "головы", "в голове", "head")),
    (re.compile(r"язык\w*|языч\w*", re.I), BodyPart("язык", "языка", "на языке", "mouth")),
    (re.compile(r"губ[аыуе]\w*", re.I), BodyPart("губа", "губы", "на губе", "mouth")),
    (re.compile(r"д[ёе]сн\w*", re.I), BodyPart("десна", "десны", "на десне", "mouth")),
    (re.compile(r"горл\w*", re.I), BodyPart("горло", "горла", "в горле", "mouth")),
    (re.compile(r"спин[аыуе]\w*", re.I), BodyPart("спина", "спины", "в спине", "torso")),
    (re.compile(r"поясниц\w*", re.I), BodyPart("поясница", "поясницы", "в пояснице", "torso")),
    (re.compile(r"живот\w*", re.I), BodyPart("живот", "живота", "в животе", "torso")),
    (re.compile(r"груд[ьи]\w*", re.I), BodyPart("грудь", "груди", "в груди", "torso")),
    (re.compile(r"рук[ауиеой]\w*", re.I), BodyPart("рука", "руки", "в руке", "arm")),
    (re.compile(r"ног[ауиеой]\w*", re.I), BodyPart("нога", "ноги", "в ноге", "leg")),
)

# Complaint-type markers, checked in this order (an event beats a sensation:
# "порезал палец, болит" is a cut, not a pain complaint).
_CUT_RE = re.compile(r"пор[еє]з\w*|разрез\w*|рассек\w*|ран[аиуы]\w*|ранил\w*|кровоточ\w*", re.I)
_IMPACT_RE = re.compile(
    r"удар\w*|стукнул\w*|прищем\w*|защем\w*|упал\w*|падени\w*|ушиб\w*|прибил\w*",
    re.I,
)
_STRAIN_VERB_RE = re.compile(r"надорв\w*|надрыв\w*|потяну\w*|растяну\w*|растяжени\w*|подверн\w*|вывих\w*|перенапряг\w*", re.I)
_LOAD_CONTEXT_RE = re.compile(
    r"после\s+(?:тренировк\w*|нагрузк\w*|пробежк\w*|занят\w*|бега|зала|спортзал\w*)"
    r"|в\s+(?:спорт)?зале|на\s+тренировк\w*",
    re.I,
)
_SHARP_MOVE_RE = re.compile(r"резк\w+\s+движени\w*", re.I)
# Gait / weight-bearing complaints. Always about the leg even when no body part
# is named, which is why they get an implicit one (see extract_medical_intake):
# an unmapped body part would otherwise send an obvious complaint to the planner.
_GAIT_RE = re.compile(
    r"хрома\w*|прихрам\w*|хромот\w*"
    r"|не\s+могу\s+нормально\s+ходить|тяжело\s+ходить|трудно\s+ходить"
    r"|больно\s+(?:наступать|ходить|ступать)|бол[ьи]\w*\s+при\s+ходьбе"
    r"|тянет\s+ногу\s+при\s+ходьбе",
    re.I,
)
# "не проходит" / "не проходит уже неделю" — a persistence marker, not a duration.
_PERSISTS_RE = re.compile(r"не\s+прох[оа]д\w*|не\s+проходит|всё\s+ещ[ёе]|до\s+сих\s+пор", re.I)
# Low-back complaints get their own compact safety screen (radiating pain,
# leg weakness, fever, trauma, bladder problems) before any booking.
_BACK_RE = re.compile(r"поясниц\w*|\bспин[аыуе]\w*|\bпоясн\w*", re.I)
_SWELLING_RE = re.compile(r"от[ёе]к\w*|опух\w*|припух\w*", re.I)
_NUMBNESS_RE = re.compile(r"онемен\w*|неме\w+|покалыван\w*|слабост\w+\s+в\s+\w+", re.I)
_RESP_CHEST_RE = re.compile(
    r"одышк\w*|(?:тяжело|трудно)\s+дыш\w*|дыш\w*\s+(?:тяжело|трудно)|бол\w*\s+в\s+груди",
    re.I,
)
_FEVER_RE = re.compile(
    r"температур\w*|\bорви\b|простуд\w*|лихорад\w*|\bжар\b|кашель|кашля\w*|насморк\w*|озноб\w*|ломит|ломота",
    re.I,
)
_PAIN_RE = re.compile(
    r"бол[иья]\w*|болит|болят|бол[ьи]\b|дискомфорт\w*|ноет|ноющ\w*|тянет|беспокоит|жж[ёе]т|саднит|раскалыва\w*",
    re.I,
)
_DURATION_RE = re.compile(
    r"\b(?:третий|четвертый|четв[её]ртый|пятый|второй|первый)\s+день\b"
    r"|\b(?:уже\s+)?\d+\s*(?:день|дня|дней)\b"
    r"|\bнесколько\s+дн(?:ей|я)\b"
    r"|\b(?:уже\s+)?(?:как\s+|около\s+)?недел[юия]\b"
    r"|\b(?:уже\s+)?\d+\s*недел\w*\b"
    r"|\b(?:уже\s+)?(?:как\s+|около\s+)?месяц\w*\b",
    re.I,
)
# Colloquial spellings normalise to one phrase for the summary panel: "уже как
# неделю", "неделю", "около недели" all mean the same thing to the reader.
_DURATION_NORMALIZED: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"недел", re.I), "около недели"),
    (re.compile(r"месяц", re.I), "около месяца"),
)

# Price/admin questions are never a complaint ("сколько стоит лечение боли в
# спине" must not open a safety screen). Mirrors medical_center_routing's guard.
_PRICE_OR_ADMIN_RE = re.compile(r"сколько\s+сто|стоимост|цена|прайс|поч[её]м|оплат|скидк", re.I)

# Who is the patient.
_CHILD_RE = re.compile(
    r"\bсын\w*|\bдоч\w*|\bреб[ёе]н\w*|\bдет[еия]\w*|малыш\w*|внук\w*|внучк\w*|\bмладен\w*|груднич\w*",
    re.I,
)
_OTHER_ADULT_RE = re.compile(r"\bмам[аыуе]\w*|\bпап[аыуе]\w*|\bжен[аыуе]\b|\bмуж[аыуе]?\b|бабушк\w*|дедушк\w*", re.I)

_SIDE_BOTH_RE = re.compile(r"\bоб[ео]их\w*|\bоба\b|\bобе\b|с\s+двух\s+сторон|двусторон", re.I)
_SIDE_ONE_RE = re.compile(r"\bодной\b|\bодна\b|\bодном\b|с\s+одной\s+стороны|только\s+справа|только\s+слева", re.I)
_SIDE_LEFT_RE = re.compile(r"\bлев\w+", re.I)
_SIDE_RIGHT_RE = re.compile(r"\bправ\w+", re.I)

# "нет отёка", "без отёка", "отёка нет", "кровь не идёт", "сознание не терял".
_DENIAL_TOKENS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("отёк", re.compile(r"(?:нет|без)\s+(?:сильного\s+)?от[ёе]к\w*|от[ёе]к\w*\s+нет", re.I)),
    ("покраснение", re.compile(r"(?:нет|без)\s+покраснени\w*|покраснени\w*\s+нет", re.I)),
    ("травма", re.compile(r"(?:нет|без)\s+травм\w*|травм\w*\s+не\s+было|не\s+ударял\w*", re.I)),
    ("онемение", re.compile(r"(?:нет|без)\s+онемени\w*|онемени\w*\s+нет|не\s+немеет", re.I)),
    ("одышка", re.compile(r"(?:нет|без)\s+одышк\w*|одышк\w*\s+нет", re.I)),
    ("кровь", re.compile(r"кров[ьи]\w*\s+(?:уже\s+)?нет|кровь\s+не\s+ид[ёе]т|кровотечени\w*\s+нет|кровь\s+останов\w*", re.I)),
    ("потеря сознания", re.compile(r"сознани\w*\s+не\s+тер\w*|без\s+потери\s+сознани\w*|не\s+теря\w*\s+сознани\w*", re.I)),
    ("рвота", re.compile(r"(?:нет|без)\s+рвот\w*|рвот\w*\s+нет|не\s+тошнит", re.I)),
)

# Substrings of the questions this module generates, used to detect "we already
# ran the safety screen" from the assistant's last turn (the demo server is
# stateless — the screen state lives in the transcript, like every other
# medical_center_demo marker).
SCREEN_MARKERS: tuple[str, ...] = (
    "кровь сейчас идёт",
    "была потеря сознания",
    "есть отёк, синяк или онемение",
    "синяк, онемение или сильная боль",
    "получается нормально двигать",
    "покраснение, онемение",
    "была травма или резкая боль",
    "проблемы с мочеиспусканием",
    "какая температура сейчас",
    "нарушение речи или зрения",
    "боль/скованность в шее",
)

# A reply that carries no new information ("и", "а?", "ну", "дальше"). The screen
# repeats its question rather than routing on an empty answer.
_FILLER_RE = re.compile(r"^\W*(?:и|а|ну|ок|угу|ага|дальше|что|дальше\?)\W*$", re.I)


def is_filler_reply(text: str) -> bool:
    """True when the message carries no new information (a continuation grunt)."""
    return bool(_FILLER_RE.match((text or "").strip()))


def assistant_asked_safety_screen(text: str) -> bool:
    """True if this assistant message is one of our generated safety screens."""
    low = (text or "").casefold()
    return any(marker in low for marker in SCREEN_MARKERS)


@dataclass(frozen=True)
class MedicalIntake:
    is_medical_complaint: bool = False
    symptoms_or_goal: str = ""
    complaint_type: str = "unknown"
    body_part: str = ""
    region: str = ""
    body_side: str = "unknown"
    event_context: str = "неизвестно"
    self_patient: bool = True
    child_case: bool = False
    red_flags_mentioned: tuple[str, ...] = ()
    red_flags_denied: tuple[str, ...] = ()
    missing_safety_questions: tuple[str, ...] = ()
    duration: str = ""
    suggested_next_step: str = "none"
    # Hybrid routing: this module is the cheap FIRST PASS. When it is not
    # confident, the turn is handed to the medical planner (an LLM call that
    # already happens on that path — no extra call is introduced) with this
    # record attached as a draft it may correct.
    intake_source: str = "deterministic"  # deterministic | llm | hybrid
    intake_confidence: float = 0.0
    needs_llm_review: bool = False
    review_reason: str = ""

    def with_source(self, source: str) -> "MedicalIntake":
        return replace(self, intake_source=source)

    def to_metadata(self) -> dict[str, object]:
        data = asdict(self)
        for key in ("red_flags_mentioned", "red_flags_denied", "missing_safety_questions"):
            data[key] = list(data[key])
        data["extracted_fields"] = {
            "symptoms_or_goal": self.symptoms_or_goal,
            "complaint_type": self.complaint_type,
            "duration": self.duration,
            "body_part": self.body_part,
            "self_patient": self.self_patient,
            "child_case": self.child_case,
            "red_flags": list(self.red_flags_mentioned),
            "missing_questions": list(self.missing_safety_questions),
        }
        return data

    def as_planner_draft(self) -> str:
        """Compact, human-readable draft for the planner prompt."""
        return "; ".join([
            f"жалоба={self.symptoms_or_goal or 'не распознана'}",
            f"тип={self.complaint_type}",
            f"часть тела={self.body_part or 'не распознана'}",
            f"пациент={'ребёнок' if self.child_case else ('сам пишущий' if self.self_patient else 'другой взрослый')}",
            f"уверенность={self.intake_confidence:.2f}",
            f"причина проверки={self.review_reason or 'нет'}",
        ])


def _match_body_part(text: str) -> BodyPart | None:
    for pattern, part in _BODY_PARTS:
        if pattern.search(text):
            return part
    return None


def _classify_complaint(text: str) -> str:
    if _CUT_RE.search(text):
        return "cut_or_wound"
    if _IMPACT_RE.search(text):
        return "impact_or_head_injury"
    if _STRAIN_VERB_RE.search(text):
        return "strain_or_sprain"
    # "болит запястье после тренировки" — a load context turns a pain complaint
    # into a strain picture, which is what the safety questions must address.
    if _PAIN_RE.search(text) and (_LOAD_CONTEXT_RE.search(text) or _SHARP_MOVE_RE.search(text)):
        return "strain_or_sprain"
    # Limping / painful weight-bearing beats a bare pain reading: the safety
    # questions it needs (trauma, swelling, ability to step) are its own.
    if _GAIT_RE.search(text):
        return "gait_limping"
    if _RESP_CHEST_RE.search(text):
        return "respiratory_or_chest"
    if _NUMBNESS_RE.search(text):
        # Checked BEFORE back_pain on purpose: "боль от поясницы в ногу, немеет
        # стопа" is a radicular picture the routing table already sends to the
        # neurologist correctly, and must not be slowed by a generic screen.
        return "numbness_or_weakness"
    # A plain aching back with no neuro signs: screen it before booking.
    if _PAIN_RE.search(text) and _BACK_RE.search(text):
        return "back_pain"
    if _FEVER_RE.search(text):
        return "infection_or_fever"
    if _SWELLING_RE.search(text):
        return "swelling"
    if _PAIN_RE.search(text):
        return "pain_discomfort"
    return "unknown"


def _event_context(text: str, complaint_type: str) -> str:
    if _LOAD_CONTEXT_RE.search(text):
        return "после нагрузки"
    if _SHARP_MOVE_RE.search(text):
        return "резкое движение"
    if complaint_type == "cut_or_wound":
        return "порез"
    if complaint_type == "impact_or_head_injury":
        return "защемление" if re.search(r"прищем\w*|защем\w*", text, re.I) else "удар"
    if complaint_type == "strain_or_sprain":
        return "возможная нагрузка или резкое движение"
    return "неизвестно"


def _body_side(text: str) -> str:
    if _SIDE_BOTH_RE.search(text):
        return "both"
    if _SIDE_ONE_RE.search(text):
        return "one"
    if _SIDE_LEFT_RE.search(text):
        return "left"
    if _SIDE_RIGHT_RE.search(text):
        return "right"
    return "unknown"


def _duration(text: str) -> str:
    match = _DURATION_RE.search(text or "")
    if not match:
        return ""
    raw = match.group(0).strip()
    # A plain "\d+ недель" keeps its number; a bare "неделю" reads better as
    # "около недели" in the summary.
    if not re.search(r"\d", raw):
        for pattern, normalized in _DURATION_NORMALIZED:
            if pattern.search(raw):
                return normalized
    return raw


def _denied_flags(text: str) -> tuple[str, ...]:
    return tuple(name for name, pattern in _DENIAL_TOKENS if pattern.search(text))


def _strip_denials(text: str) -> str:
    """Blank out denied symptoms before classification.

    "отёка нет, одышки нет" answers a safety question; it must not be read as a
    swelling/breathing COMPLAINT just because the words appear in the sentence.
    """
    for _name, pattern in _DENIAL_TOKENS:
        text = pattern.sub(" ", text)
    return text


def _complaint_label(text: str, complaint_type: str, part: BodyPart | None, child: bool) -> str:
    """Short human-readable complaint for the state/summary panel."""
    where_prep = part.prep if part else ""
    where_gen = part.gen if part else ""

    if complaint_type == "cut_or_wound":
        label = f"порез {where_gen}".strip() if where_gen else "порез"
    elif complaint_type == "strain_or_sprain":
        if re.search(r"надорв\w*|надрыв\w*", text, re.I):
            label = f"ощущение надрыва {where_prep}".strip() if where_prep else "ощущение надрыва"
        elif re.search(r"потяну\w*|растяну\w*|растяжени\w*", text, re.I):
            label = f"растяжение {where_gen}".strip() if where_gen else "растяжение"
        else:
            label = f"боль {where_prep} после нагрузки".strip() if where_prep else "боль после нагрузки"
    elif complaint_type == "impact_or_head_injury":
        if part and part.region == "head":
            label = "удар головой"
        elif re.search(r"прищем\w*|защем\w*", text, re.I):
            label = f"защемление {where_gen}".strip() if where_gen else "защемление"
        else:
            label = f"ушиб {where_gen}".strip() if where_gen else "ушиб"
    elif complaint_type == "gait_limping":
        base = "хромота" if re.search(r"хром\w*|прихрам\w*", text, re.I) else "боль при ходьбе"
        duration = _duration(text)
        label = f"{base} {duration}".strip() if duration else base
        if _PERSISTS_RE.search(text):
            label = f"{label}, не проходит"
    elif complaint_type == "back_pain":
        kind = "ноющая боль" if re.search(r"ноет|ноющ\w*", text, re.I) else "боль"
        label = f"{kind} {where_prep}".strip() if where_prep else f"{kind} в спине"
    elif complaint_type == "swelling":
        label = f"отёк {where_gen}".strip() if where_gen else "отёк"
    elif complaint_type == "numbness_or_weakness":
        label = f"онемение {where_gen}".strip() if where_gen else "онемение"
    elif complaint_type == "infection_or_fever":
        clean = re.sub(r"\s+", " ", text).strip(" .,;:!?")
        label = clean[:160] if clean else "температура или простудные симптомы"
    elif complaint_type == "respiratory_or_chest":
        label = "жалобы на дыхание или грудную клетку"
    else:  # pain_discomfort / unknown
        word = "дискомфорт" if re.search(r"дискомфорт", text, re.I) else "боль"
        label = f"{word} {where_prep}".strip() if where_prep else word

    return f"ребёнок: {label}" if child else label


def _missing_safety_questions(complaint_type: str, region: str, denied: tuple[str, ...]) -> tuple[str, ...]:
    if complaint_type == "cut_or_wound":
        wanted = ["кровотечение", "глубина раны"]
        if region == "mouth":
            wanted.append("дыхание и глотание")
    elif complaint_type == "impact_or_head_injury" and region == "head":
        wanted = ["потеря сознания", "рвота", "головная боль", "рана"]
    elif complaint_type == "impact_or_head_injury":
        wanted = ["сильная боль", "отёк", "онемение", "подвижность", "рана"]
    elif complaint_type == "strain_or_sprain":
        wanted = ["обстоятельства травмы", "подвижность", "отёк", "онемение"]
    elif complaint_type == "gait_limping":
        wanted = ["травма", "отёк", "покраснение", "онемение", "опора на ногу"]
    elif complaint_type == "back_pain":
        wanted = ["онемение или слабость в ноге", "иррадиация в ногу", "температура",
                  "травма", "мочеиспускание"]
    elif complaint_type == "pain_discomfort":
        wanted = ["возраст", "отёк", "покраснение", "онемение"]
        if region == "leg":
            wanted += ["одышка", "боль в груди"]
    elif complaint_type == "infection_or_fever":
        wanted = [
            "возраст",
            "температура сейчас",
            "сыпь",
            "рвота",
            "сильная слабость",
            "спутанность",
            "речь/зрение",
            "онемение",
            "шея",
        ]
    else:
        wanted = []
    denied_set = {d for d in denied}
    return tuple(q for q in wanted if q not in denied_set)


# Confidence floor below which the planner must review the draft.
LLM_REVIEW_CONFIDENCE_THRESHOLD = 0.7

# Neuro / cardiac clues. On their own these are often triaged correctly by the
# deterministic routing table (a radicular "боль от поясницы в ногу, немеет
# стопа" is a textbook neurologist case, and sending it there is right). What a
# regex genuinely cannot resolve is a CONFLICT: the same signs described after
# exertion could be musculoskeletal or neurological, and the two point at
# different specialists. That conflict, not the sign itself, triggers review.
_AMBIGUOUS_SIGN_RE = re.compile(
    r"прострел\w*|мурашк\w*|покалыван\w*|онемен\w*|неме\w+"
    r"|сердцебиен\w*|аритми\w*|перебо\w+\s+в\s+сердц|давит\s+в\s+груди|одышк\w*",
    re.I,
)
# The user is repeating themselves or pushing back — a regex has already failed
# them once, so let the planner read the whole conversation instead.
_FRUSTRATION_RE = re.compile(
    r"\bопять\b|\bснова\b|я\s+же\s+(?:говорил|писал|сказал)|уже\s+(?:говорил|писал|сказал)"
    r"|вы\s+не\s+пон[яи]|повторяю|сколько\s+можно",
    re.I,
)
# "Major" complaint categories. Two or more in one message means the user
# described several things at once and the ordering heuristics can't be trusted.
_MAJOR_CATEGORY_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("cut_or_wound", _CUT_RE),
    ("impact_or_head_injury", _IMPACT_RE),
    ("strain_or_sprain", _STRAIN_VERB_RE),
    ("swelling", _SWELLING_RE),
    ("numbness_or_weakness", _NUMBNESS_RE),
    ("respiratory_or_chest", _RESP_CHEST_RE),
    ("infection_or_fever", _FEVER_RE),
)


def _major_categories(asserted: str) -> list[str]:
    return [name for name, pattern in _MAJOR_CATEGORY_RES if pattern.search(asserted)]


def _assess_confidence(
    *,
    raw: str,
    asserted: str,
    complaint_type: str,
    body_part: str,
    event_context: str,
) -> tuple[float, bool, str]:
    """Score the draft and decide whether the planner must review it.

    Returns ``(confidence, needs_llm_review, review_reason)``. The deterministic
    layer earns a clean pass only for the obvious, common, safety-simple shapes;
    everything hedged, multi-symptom, neurological or unmapped goes to the LLM.
    """
    reasons: list[str] = []

    confidence = 0.0
    if complaint_type != "unknown":
        confidence += 0.5
    if body_part:
        confidence += 0.3
    if event_context != "неизвестно":
        confidence += 0.1
    if complaint_type in _SCREEN_COMPLAINT_TYPES:
        confidence += 0.1
    confidence = min(confidence, 1.0)

    if complaint_type == "unknown":
        reasons.append("complaint_type_unknown")
    if not body_part and complaint_type != "infection_or_fever":
        # A symptom is clearly described but we cannot say WHERE. The screen's
        # questions are body-region-dependent, so guessing here is unsafe.
        reasons.append("body_part_unknown")
        confidence = min(confidence, 0.5)

    categories = _major_categories(asserted)
    if len(categories) >= 2:
        reasons.append("multiple_complaints")
        confidence = min(confidence, 0.5)

    # Neuro/cardiac signs described after exertion: musculoskeletal and
    # neurological explanations point at different specialists and a regex has
    # no way to choose. Without the exertion context the routing table's own
    # neuro rule is trustworthy, so we leave it alone.
    if (
        _AMBIGUOUS_SIGN_RE.search(asserted)
        and _LOAD_CONTEXT_RE.search(asserted)
        and complaint_type not in _SCREEN_COMPLAINT_TYPES
    ):
        reasons.append("ambiguous_neuro_cardiac_signs")
        confidence = min(confidence, 0.5)

    if _FRUSTRATION_RE.search(raw):
        reasons.append("user_frustrated_or_repeating")
        confidence = min(confidence, 0.5)

    needs_review = bool(reasons) or confidence < LLM_REVIEW_CONFIDENCE_THRESHOLD
    if needs_review and not reasons:
        reasons.append("low_confidence")
    return round(confidence, 2), needs_review, ",".join(reasons)


def extract_medical_intake(message: str) -> MedicalIntake:
    """Structure a single free-text message into a MedicalIntake record."""
    text = (message or "").strip()
    if not text or _PRICE_OR_ADMIN_RE.search(text):
        return MedicalIntake()

    denied = _denied_flags(text)
    asserted = _strip_denials(text)
    complaint_type = _classify_complaint(asserted)
    part = _match_body_part(asserted)
    duration = _duration(asserted)
    if complaint_type == "gait_limping" and part is None:
        # "Я хромаю" names no body part, but it is unambiguously the leg. Without
        # this the draft would look unmapped and be handed to the planner for a
        # complaint the deterministic layer understands perfectly well.
        part = BodyPart("нога", "ноги", "в ноге", "leg")

    if complaint_type == "unknown":
        # No complaint marker matched. If the message still *looks* like a
        # symptom (a body part, or a neuro/cardiac sign), the first pass has
        # simply failed to parse it — say so, so the planner reviews it rather
        # than the turn being treated as ordinary small talk.
        looks_symptomatic = bool(part) or bool(_AMBIGUOUS_SIGN_RE.search(asserted))
        if not looks_symptomatic:
            return MedicalIntake()
        return MedicalIntake(
            body_part=part.nom if part else "",
            region=part.region if part else "",
            intake_source="llm",
            intake_confidence=0.0,
            needs_llm_review=True,
            review_reason="complaint_type_unknown",
            suggested_next_step="ask_clarifying",
        )
    child = bool(_CHILD_RE.search(text))
    other_adult = bool(_OTHER_ADULT_RE.search(text))
    region = part.region if part else ""

    missing = _missing_safety_questions(complaint_type, region, denied)
    event_context = _event_context(text, complaint_type)
    confidence, needs_review, review_reason = _assess_confidence(
        raw=text,
        asserted=asserted,
        complaint_type=complaint_type,
        body_part=part.nom if part else "",
        event_context=event_context,
    )

    if needs_review:
        next_step = "ask_clarifying"
    elif complaint_type == "respiratory_or_chest":
        next_step = "emergency"
    elif missing:
        next_step = "ask_clarifying"
    else:
        next_step = "route_to_specialist"

    return MedicalIntake(
        is_medical_complaint=True,
        symptoms_or_goal=_complaint_label(asserted, complaint_type, part, child),
        complaint_type=complaint_type,
        duration=duration,
        body_part=part.nom if part else "",
        region=region,
        body_side=_body_side(text),
        event_context=event_context,
        self_patient=not (child or other_adult),
        child_case=child,
        red_flags_denied=denied,
        missing_safety_questions=missing,
        suggested_next_step=next_step,
        intake_confidence=confidence,
        needs_llm_review=needs_review,
        review_reason=review_reason,
    )


def extract_conversation_intake(
    history: list[ChatHistoryMessage],
    message: str,
) -> MedicalIntake:
    """The complaint currently under discussion, recovered from the transcript.

    The demo server is stateless, so a complaint stated three turns ago must
    still be recoverable when the user answers a safety question with "кровь
    остановилась, порез неглубокий" — a reply that names the complaint type but
    has lost the body part. The most recent complaint that still names a body
    part therefore wins over a vaguer, more recent one; the current message
    always contributes its side ("в обеих") and denials ("отёка нет") on top.
    """
    text = message or ""
    candidates = [m.content or "" for m in (history or []) if m.role == "user"]
    candidates.append(text)

    found = [
        intake
        for intake in (extract_medical_intake(c) for c in reversed(candidates))
        if intake.is_medical_complaint
    ]
    if not found:
        return MedicalIntake()

    base = next((i for i in found if i.body_part), found[0])

    denied = tuple(sorted(set(base.red_flags_denied) | set(_denied_flags(text))))
    side = _body_side(text)
    duration = _duration(text) or base.duration
    merged = replace(
        base,
        body_side=side if side != "unknown" else base.body_side,
        red_flags_denied=denied,
        duration=duration,
    )
    return replace(
        merged,
        missing_safety_questions=_missing_safety_questions(
            merged.complaint_type, merged.region, denied
        ),
    )


def needs_safety_screen(intake: MedicalIntake, has_routing_rule: bool) -> bool:
    """Whether this complaint must be screened before any routing suggestion.

    Injury-shaped complaints (strain / cut / impact) always are — the user told
    us an event happened and we owe them the event's safety questions. A plain
    pain/discomfort complaint is screened only when nothing in the deterministic
    routing tables covers it: a knee or stomach complaint already has a correct,
    specific destination and must not be slowed down by a generic questionnaire.

    A draft the first pass isn't confident about (``needs_llm_review``) is never
    screened here: the deterministic questions are only as good as the fields
    they key off, so an unmapped body part or a tangle of symptoms goes to the
    planner instead of getting confidently wrong questions.
    """
    if not intake.is_medical_complaint:
        return False
    if intake.complaint_type == "infection_or_fever":
        return intake.self_patient
    if intake.needs_llm_review:
        return False
    if intake.complaint_type in _SCREEN_COMPLAINT_TYPES:
        return True
    return intake.complaint_type == "pain_discomfort" and not has_routing_rule


def _age_question(intake: MedicalIntake) -> str:
    if intake.child_case:
        return "Сколько лет ребёнку?"
    if intake.self_patient:
        return "Сколько вам лет?"
    return "Сколько лет пациенту?"


# Instrumental case for the "can you still move it?" question, for the parts
# where naming the part itself reads better than the whole limb.
_MOVE_INSTRUMENTAL = {
    "палец": "пальцем",
    "кисть": "кистью",
    "запястье": "запястьем",
    "локоть": "локтем",
    "плечо": "плечом",
    "стопа": "стопой",
    "колено": "коленом",
}


def _move_question(intake: MedicalIntake) -> str:
    part = _MOVE_INSTRUMENTAL.get(intake.body_part)
    if part:
        suffix = " и наступать" if intake.region == "leg" else ""
        return f"Получается нормально двигать {part}{suffix}?"
    if intake.region == "leg":
        return "Получается нормально двигать ногой и наступать?"
    if intake.region == "arm":
        return "Получается нормально двигать рукой?"
    return "Получается нормально двигать этой областью?"


def build_safety_question(intake: MedicalIntake, age_known: bool = False) -> str:
    """The safety questions this complaint TYPE warrants. Never a diagnosis."""
    parts: list[str] = []
    ct, region = intake.complaint_type, intake.region

    if intake.child_case and not age_known:
        parts.append(_age_question(intake))

    if ct == "cut_or_wound":
        parts.append("Кровь сейчас идёт?")
        parts.append("Порез глубокий?")
        if region == "mouth":
            parts.append("Трудно говорить, глотать или дышать?")
    elif ct == "impact_or_head_injury" and region == "head":
        parts.append("Была потеря сознания?")
        parts.append("Есть рвота, сильная головная боль, спутанность или сонливость?")
        parts.append("Есть рана или кровотечение?")
    elif ct == "impact_or_head_injury":
        parts.append("Сильная боль есть?")
        parts.append("Есть отёк, синяк или онемение?")
        parts.append(_move_question(intake))
        parts.append("Есть рана или кровь?")
    elif ct == "strain_or_sprain":
        if intake.event_context not in ("после нагрузки", "резкое движение"):
            parts.append("Боль появилась после нагрузки или резкого движения?")
        parts.append(_move_question(intake))
        parts.append("Есть отёк, синяк, онемение или сильная боль?")
    elif ct == "gait_limping":
        # Deliberately two short questions, not a questionnaire: the complaint is
        # already a week old, so the point is to catch a trauma or a red flag and
        # then route, not to interview the patient.
        parts.append("Была травма или резкая боль?")
        parts.append("Есть отёк, покраснение, онемение или трудно наступать на ногу?")
    elif ct == "back_pain":
        # One compact question covering the low-back red flags (radiculopathy,
        # cauda equina, infection, trauma). Not a diagnosis, just triage.
        if not age_known and not intake.child_case:
            parts.append(_age_question(intake))
        parts.append(
            "Есть онемение или слабость в ноге, боль отдаёт в ногу, температура, "
            "травма или проблемы с мочеиспусканием?"
        )
    elif ct == "infection_or_fever":
        if not age_known and not intake.child_case:
            parts.append(_age_question(intake))
        parts.append(
            "Какая температура сейчас? Есть ли сыпь, рвота, сильная слабость, "
            "спутанность, нарушение речи или зрения, онемение, боль/скованность в шее?"
        )
    else:  # pain_discomfort
        if not age_known and not intake.child_case:
            parts.append(_age_question(intake))
        if region == "leg":
            parts.append("Есть отёк, покраснение, онемение, одышка или боль в груди?")
        else:
            parts.append("Есть отёк, покраснение, онемение или температура?")

    return " ".join(parts)


#: Where we send a complaint whose ideal specialist the clinic does not employ.
#: The KB always has a therapist, and a first-contact therapist deciding the next
#: step is honest routing — inventing a specialist the clinic lacks is not.
FIRST_CONTACT_SPECIALTY = "терапевт"


def specialty_for_intake(intake: MedicalIntake) -> str:
    """Starting specialty from the KB list. Administrative routing, not a diagnosis.

    Every branch is validated against the KB (``normalize_specialty`` returns
    None for a specialty MedNova does not have), so a routing table that grows a
    specialist the clinic does not employ degrades to the therapist instead of
    confidently sending the patient to a doctor who is not there.
    """
    ct, region = intake.complaint_type, intake.region
    if ct == "cut_or_wound":
        candidate = "стоматолог" if region == "mouth" else "травматолог-ортопед"
    elif ct == "back_pain":
        candidate = "невролог"
    elif ct in ("strain_or_sprain", "gait_limping"):
        candidate = "травматолог-ортопед" if region in ("arm", "leg") else FIRST_CONTACT_SPECIALTY
    elif ct == "impact_or_head_injury":
        candidate = FIRST_CONTACT_SPECIALTY if region == "head" else "травматолог-ортопед"
    else:
        candidate = FIRST_CONTACT_SPECIALTY
    return candidate if normalize_specialty(candidate) else FIRST_CONTACT_SPECIALTY


def build_routing_answer(intake: MedicalIntake, dative: str) -> str:
    """Post-screen routing: a natural "if X then plan, if Y then urgent" pair.

    Deliberately conversational rather than policy-flavoured, and free of the em
    dash (see the writer's style rules). Never names a diagnosis, a doctor or a
    price; the booking CTA is the only next step offered.

    ``dative`` is the specialty in the dative case, so every sentence here must
    use a verb that governs it ("показаться терапевту", "обратиться к терапевту")
    and never a preposition that wants another case ("начать с терапевта").
    """
    ct, region = intake.complaint_type, intake.region

    if ct == "cut_or_wound":
        caveat = (
            f"Если кровь остановилась и порез неглубокий, можно спокойно показаться {dative}. "
            "Если кровь не останавливается, рана глубокая или трудно глотать и дышать, "
            "нужна срочная очная помощь."
        )
    elif ct == "impact_or_head_injury" and region == "head":
        caveat = (
            "Если сознание не терялось и нет рвоты, сильной головной боли или сонливости, "
            f"можно показаться {dative} в плановом порядке. Если появится хотя бы один из "
            "этих признаков, лучше обратиться очно как можно скорее."
        )
    elif ct == "back_pain":
        caveat = (
            f"Если сильной слабости в ноге и температуры нет, можно показаться {dative}. "
            "Если боль резко усиливается, отдаёт в ногу с онемением, поднялась температура "
            "или появились проблемы с мочеиспусканием, нужна срочная очная помощь."
        )
    elif ct == "gait_limping":
        # Conversational, not clinical: never "чтобы исключить повреждения или
        # воспалительные процессы". A complaint that has lasted a while is the
        # reason to go now, so the duration belongs in the sentence when we have it.
        what = "хромота" if "хром" in intake.symptoms_or_goal else "боль"
        how_long = f", особенно если {what} держится {intake.duration}" if intake.duration else ""
        caveat = (
            f"С такой жалобой обычно показываются {dative}{how_long}. "
            "Если есть сильная боль, отёк или трудно наступать на ногу, лучше обратиться "
            "очно как можно скорее."
        )
    elif ct in ("impact_or_head_injury", "strain_or_sprain"):
        caveat = (
            f"Если движение сохраняется и боль терпимая, можно показаться {dative}. "
            "Если боль резкая, место сильно отекает или есть онемение, лучше обратиться "
            "очно как можно скорее."
        )
    elif region == "leg":
        caveat = (
            f"Если нет сильного отёка, онемения, одышки или боли в груди, можно показаться {dative}. "
            "Если боль резкая, нога отекает или трудно наступать, лучше обратиться очно "
            "как можно скорее."
        )
    else:
        caveat = (
            f"Если самочувствие не ухудшается и сильной боли нет, можно показаться {dative}. "
            "Если боль усиливается или появляются новые симптомы, лучше обратиться очно "
            "как можно скорее."
        )

    return f"{caveat}\n\nМогу подобрать ближайшее окно к {dative}?"
