"""
Post-intake response policy for the DamiWorks website chat (channel=web_site).

When the guided intake questionnaire completes, the frontend injects a
[WEBSITE INTAKE CONTEXT] block as a prefix to each user message.  This module:

  1. parse_message()   — splits the prefix from the real user text → IntakeContext
  2. detect_intent()   — classifies the real message into a semantic intent category
  3. apply_post_intake_policy() — returns a deterministic canned answer for
                                  price/objection/acknowledgment intents, or strips
                                  known-field re-asks for generic intents

Matching is intent-based (pattern *groups*), not phrase-exact — paraphrases of the
same intent resolve to the same policy branch.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Context marker / separator — must match buildIntakeContextString in intake.ts
# ---------------------------------------------------------------------------

CONTEXT_MARKER = "[WEBSITE INTAKE CONTEXT"
CONTEXT_SEP = "\n\nCurrent user message:\n"

# ---------------------------------------------------------------------------
# IntakeContext
# ---------------------------------------------------------------------------


@dataclass
class IntakeContext:
    exists: bool = False
    channels: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    handoff: str | None = None
    volume: str | None = None
    timeline: str | None = None
    business_type: str | None = None
    recommended_package: str | None = None
    shown_price: str | None = None

    @property
    def known_fields(self) -> set[str]:
        """Fields that the user explicitly filled in during intake."""
        known: set[str] = set()
        if self.channels:
            known.add("channels")
        if self.tasks:
            known.add("tasks")
        if self.volume:
            known.add("volume")
        if self.timeline:
            known.add("timeline")
        if self.handoff:
            known.add("handoff")
        return known


def parse_message(user_message: str) -> tuple[str, IntakeContext]:
    """Split [WEBSITE INTAKE CONTEXT] prefix from real user message.

    Returns (real_message, IntakeContext).  When no marker is present the
    original message is returned verbatim and IntakeContext.exists == False.
    """
    if CONTEXT_MARKER not in user_message:
        return user_message, IntakeContext()
    idx = user_message.find(CONTEXT_SEP)
    if idx == -1:
        return user_message, IntakeContext()
    block = user_message[:idx].strip()
    real_msg = user_message[idx + len(CONTEXT_SEP):].strip()
    return real_msg, _parse_block(block)


def _parse_block(block: str) -> IntakeContext:
    ctx = IntakeContext(exists=True)
    for line in block.splitlines():
        s = line.strip()
        if s.startswith("- Channels:"):
            val = s[len("- Channels:"):].strip()
            ctx.channels = [c.strip() for c in val.split(",") if c.strip()]
        elif s.startswith("- Tasks:"):
            val = s[len("- Tasks:"):].strip()
            ctx.tasks = [t.strip() for t in val.split(",") if t.strip()]
        elif s.startswith("- Handoff:"):
            ctx.handoff = s[len("- Handoff:"):].strip() or None
        elif s.startswith("- Volume:"):
            ctx.volume = s[len("- Volume:"):].strip() or None
        elif s.startswith("- Timeline:"):
            ctx.timeline = s[len("- Timeline:"):].strip() or None
        elif s.startswith("- Business type:"):
            ctx.business_type = s[len("- Business type:"):].strip() or None
        elif s.startswith("- Recommended package:"):
            ctx.recommended_package = s[len("- Recommended package:"):].strip() or None
        elif s.startswith("- Shown price:"):
            ctx.shown_price = s[len("- Shown price:"):].strip() or None
    return ctx


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

PostIntakeIntent = Literal[
    "price_objection",
    "price_question",
    "already_answered_complaint",
    "implementation_question",
    "start_intent",
    "generic",
]

# Pattern groups — each covers multiple paraphrases of the same semantic intent.
_PRICE_OBJECTION_RE = re.compile(
    r"почему\s+(так(ая)?\s+)?(дорого|цена|стоит)|"
    r"за\s+что\s+(такая\s+)?цена|"
    r"слишком\s+дорого|"
    r"это\s+дорого|"
    r"так\s+дорого|"
    r"почему\s+столько|"
    r"есть\s+дешевле|"
    r"можно\s+начать\s+дешевле|"
    r"^\s*дорого[\s,\.!?]*$",
    re.IGNORECASE | re.MULTILINE,
)

_PRICE_QUESTION_RE = re.compile(
    r"сколько\s+стоит|"
    r"какая\s+цена|"
    r"какова\s+стоимость|"
    r"стоимость|"
    r"тариф|"
    r"порядок\s+цен|"
    r"сколько\s+будет\s+стоить",
    re.IGNORECASE,
)

_ALREADY_ANSWERED_RE = re.compile(
    r"я\s+(?:же|уже)\s+(?:выбрал|ответил|указал|заполнил|сказал|говорил|писал)|"
    r"это\s+уже\s+было\s+в\s+анкете|"
    r"в\s+анкете\s+(?:я|уже)|"
    r"вы\s+(?:уже|же)\s+спросили|"
    r"я\s+(?:это\s+)?уже\s+(?:отвечал|указал)",
    re.IGNORECASE,
)

_IMPLEMENTATION_RE = re.compile(
    r"как\s+(это\s+)?будет\s+работать|"
    r"как\s+(это\s+)?настраивается|"
    r"что\s+нужно\s+для\s+запуска|"
    r"что\s+входит\s+в\s+(?:запуск|пакет|услугу)|"
    r"как\s+проходит\s+запуск|"
    r"расскажи\s+подробнее",
    re.IGNORECASE,
)

_START_INTENT_RE = re.compile(
    r"хочу\s+начать|"
    r"хочу\s+(?:попробовать|запустить)|"
    r"давайте\s+(?:начнем|запускаем|старт|запуск)\b|"
    r"ок[,\s]+запускаем|"
    r"\b(?:запускаем|начинаем)\b|"
    r"\bберём\b|\bберем\b|"
    r"готов(?:ы|а)?\b|"
    r"\bсогласен\b|\bсогласна\b|"
    r"как\s+начать\b|"
    r"когда\s+(?:можно\s+)?начать|"
    r"как\s+(?:мы\s+)?(?:можем\s+)?начать|"
    r"как\s+(?:можно\s+)?запустить|"
    r"что\s+дальше|"
    r"^\s*подходит\b|"
    r"^\s*давайте[\s.!?]*$|"
    r"^\s*да\s*[.!]*$|"
    r"^\s*погнали\b|"
    r"\bоставить\s+заявку\b|"
    r"как\s+(?:мне\s+)?(?:отправить|оставить)\s+заявку",
    re.IGNORECASE | re.MULTILINE,
)

# Post-intake: user is unsure / cannot recall details — reassure, do not re-ask.
_NOT_REMEMBERED_RE = re.compile(
    r"не\s+помню|не\s+знаю|не\s+уверен|затрудняюсь",
    re.IGNORECASE,
)

# Post-intake: explicit request for a cheaper / simpler option (downgrade).
_CHEAPER_RE = re.compile(
    r"начать\s+дешевле|можно\s+дешевле|есть\s+дешевле|подешевле|"
    r"вариант\s+проще|что[-\s]?нибудь\s+проще|что[-\s]?то\s+проще",
    re.IGNORECASE,
)

# Post-intake: softer/semantic agreement, interest, or readiness — the user is
# moving forward without an explicit "хочу начать". After a recommendation is
# shown, these should lead to a contact handoff, not more discovery.
_SOFT_START_INTENT_RE = re.compile(
    r"звучит\s+(?:нормально|норм|неплохо|хорошо|интересно)|"
    r"в\s+целом\s+подходит|\bподходит\b|"
    r"\bинтересно\b|"
    r"можно\s+попробовать|"
    r"давайте\s+обсуд|"
    r"дальше\s+что|что\s+дальше|"
    r"что\s+(?:от\s+меня\s+)?нужно(?:\s+от\s+меня)?|"
    r"мне\s+нравится|нравится\s+вариант|"
    r"думаю[,\s]+можно|"
    r"следующий\s+шаг|"
    r"ок[,\s]+это\s+подходит",
    re.IGNORECASE,
)


def is_start_intent(user_message: str) -> bool:
    """True for explicit OR soft/semantic start intent (post-intake)."""
    msg = user_message.casefold().replace("ё", "е")
    # Normalize accidental split words: "с огласен" → "согласен", "с огласна" → "согласна"
    msg = re.sub(r"\bс\s+оглас", "соглас", msg)
    return bool(_START_INTENT_RE.search(msg) or _SOFT_START_INTENT_RE.search(msg))


def detect_intent(user_message: str) -> PostIntakeIntent:
    """Classify user message into a post-intake intent category.

    Order matters: already_answered_complaint before price_objection to avoid
    "я уже ответил — это дорого" colliding with the wrong branch.
    """
    msg = user_message.casefold().replace("ё", "е")
    if _ALREADY_ANSWERED_RE.search(msg):
        return "already_answered_complaint"
    if _PRICE_OBJECTION_RE.search(msg):
        return "price_objection"
    if _START_INTENT_RE.search(msg):
        return "start_intent"
    if _PRICE_QUESTION_RE.search(msg):
        return "price_question"
    if _IMPLEMENTATION_RE.search(msg):
        return "implementation_question"
    return "generic"


# ---------------------------------------------------------------------------
# Pre-intake FAQ — curated answers for the 3 known quick-reply buttons.
#
# Applies ONLY before the guided intake is completed (no [WEBSITE INTAKE
# CONTEXT] marker).  Covers the three quick-reply intents and very close simple
# variants; detailed business/pricing questions return None and fall through to
# the LLM + guards.
# ---------------------------------------------------------------------------

PreIntakeFaqIntent = Literal["price", "how_it_works", "vs_chatbot"]

_FAQ_VS_CHATBOT_RE = re.compile(
    r"чем\s+отлич|"
    r"отлича\w*\s+от\s+(?:чат[\s-]?бот|обычного\s+бот|бот)|"
    r"это\s+(?:просто\s+)?(?:обычный\s+)?чат[\s-]?бот|"
    r"чем\s+вы\s+лучше\s+(?:чат[\s-]?бот|бот)",
    re.IGNORECASE,
)
_FAQ_HOW_RE = re.compile(
    r"как\s+(?:это\s+)?работает|"
    r"как\s+(?:оно|вс[её])\s+работает|"
    r"как\s+у\s+вас\s+(?:это\s+)?работает|"
    r"как\s+устроено|"
    r"как\s+работает\s+ваш",
    re.IGNORECASE,
)
_FAQ_PRICE_RE = re.compile(
    r"сколько\s+(?:это\s+)?стоит|"
    r"какая\s+цена|"
    r"какие\s+цены|"
    r"сколько\s+будет\s+стоить|"
    r"стоимость|"
    r"порядок\s+цен",
    re.IGNORECASE,
)

# When any of these specifics appear, the question is detailed — let the LLM
# handle it instead of returning the generic curated answer.
_FAQ_SPECIFICS_RE = re.compile(
    r"\bcrm\b|amo\s*crm|amocrm|битрикс|bitrix|google\s*sheets|таблиц|\bapi\b|вебхук|webhook|"
    r"инстаграм|instagram|whatsapp|ватсап|телеграм|telegram|"
    r"follow|воронк|квалификац|интеграц|"
    r"\d{2,}",  # 2+ digit number → volume/budget specifics
    re.IGNORECASE,
)


def detect_pre_intake_faq_intent(user_message: str) -> PreIntakeFaqIntent | None:
    """Classify a short, generic quick-reply question before intake is completed.

    Returns None when the intake context is present (intake completed), when the
    message carries specifics (channels, integrations, numbers), or when no FAQ
    intent matches — in all those cases the message goes to the LLM + guards.
    """
    real_msg, ctx = parse_message(user_message)
    if ctx.exists:
        return None
    msg = real_msg.casefold().replace("ё", "е")
    if _FAQ_SPECIFICS_RE.search(msg):
        return None
    if _FAQ_VS_CHATBOT_RE.search(msg):
        return "vs_chatbot"
    if _FAQ_HOW_RE.search(msg):
        return "how_it_works"
    if _FAQ_PRICE_RE.search(msg):
        return "price"
    return None


# Varied soft guided-intake CTAs. The repetition guard skips any phrase already
# present in the previous assistant message so the same CTA is never used twice
# in a row.
GUIDED_INTAKE_CTAS: tuple[str, ...] = (
    "Если хотите, я могу подобрать подходящий вариант за 1 минуту — нажмите «Подобрать AI-сотрудника».",
    "Чтобы понять, какой формат подойдёт именно вам, можно пройти короткий подбор.",
    "Лучше всего начать с короткого подбора — он займёт около минуты.",
    "Могу помочь быстро сориентироваться: ответьте на несколько вопросов, и я покажу подходящий вариант.",
)


def pick_guided_intake_cta(last_assistant_message: str = "") -> str:
    """Pick a soft guided-intake CTA not present in the previous assistant message."""
    prev = last_assistant_message or ""
    for cta in GUIDED_INTAKE_CTAS:
        if cta not in prev:
            return cta
    return GUIDED_INTAKE_CTAS[0]


def answer_has_guided_intake_cta(answer: str) -> bool:
    """True if the answer already nudges toward the guided intake."""
    text = answer or ""
    if "Подобрать AI-сотрудника" in text:
        return True
    return any(cta in text for cta in GUIDED_INTAKE_CTAS)


# Discovery mode: hide exact DamiWorks package prices from public chat.
# Flip to False to restore public prices (also update api.py and intake.ts).
# Scope: damiworks_site only — English School and Custom Demo are unaffected.
HIDE_DAMIWORKS_PUBLIC_PRICES: bool = True

_FAQ_VS_CHATBOT_BODY = (
    "Обычный чат-бот чаще работает по жёсткому сценарию: кнопки, шаблоны и заранее "
    "прописанные ответы.\n\n"
    "AI-сотрудник DamiWorks понимает контекст диалога, может задавать уточняющие вопросы, "
    "квалифицировать заявку, собирать контакты и передавать менеджеру уже тёплый лид "
    "с краткой сводкой."
)

_FAQ_HOW_IT_WORKS_BODY = (
    "DamiWorks подключает AI-сотрудника к вашему каналу — например WhatsApp, Instagram, "
    "Telegram или сайту.\n\n"
    "Мы настраиваем базу знаний, сценарии ответов, сбор контактов, квалификацию заявок "
    "и передачу менеджеру или в Google Sheets/CRM.\n\n"
    "Клиент пишет как обычно, а AI отвечает, уточняет детали и помогает не терять обращения."
)

_FAQ_PRICE_BODY = (
    "Стоимость зависит от каналов, объёма обращений, интеграций и уровня автоматизации.\n\n"
    "Обычно мы сначала коротко разбираем задачу и предлагаем формат пилота с понятным объёмом. "
    "Точная цена называется после уточнения сценария."
    if HIDE_DAMIWORKS_PUBLIC_PRICES else
    "Pilot / Start обычно начинается от 150 000–200 000 ₸ за запуск и от 40 000–60 000 ₸ "
    "в месяц за сопровождение.\n\n"
    "Более продвинутый Sales Assistant с квалификацией лидов и передачей менеджеру обычно "
    "стоит дороже.\n\n"
    "Точная цена зависит от каналов, задач, объёма сообщений и интеграций."
)

_FAQ_BODIES: dict[str, str] = {
    "vs_chatbot": _FAQ_VS_CHATBOT_BODY,
    "how_it_works": _FAQ_HOW_IT_WORKS_BODY,
    "price": _FAQ_PRICE_BODY,
}


def pre_intake_faq_answer(
    intent: PreIntakeFaqIntent,
    *,
    last_assistant_message: str = "",
    suppress_cta: bool = False,
) -> str:
    """Curated pre-intake answer for a known FAQ intent + one soft guided-intake CTA.

    Never asks for contact details. ``suppress_cta=True`` (the questionnaire was
    already offered earlier in the conversation) returns the body only — the
    guided intake is suggested at most once per conversation.
    """
    body = _FAQ_BODIES[intent]
    if suppress_cta:
        return body
    cta = pick_guided_intake_cta(last_assistant_message)
    return f"{body}\n\n{cta}"


# ---------------------------------------------------------------------------
# Known-field re-ask patterns
# ---------------------------------------------------------------------------

# Keyed by IntakeContext field name.  A sentence is stripped only when the
# corresponding field is already known (user answered it in the questionnaire).
_REASK_PATTERNS: dict[str, re.Pattern[str]] = {
    "channels": re.compile(
        r"какой\s+(?:у\s+вас\s+)?(?:основной\s+)?канал|"
        r"где\s+(?:у\s+вас\s+)?пишут\s+клиенты|"
        r"в\s+каком\s+канале|"
        r"какой\s+канал\s+(?:используете|у\s+вас|вам|для\s+вас)",
        re.IGNORECASE,
    ),
    "tasks": re.compile(
        r"какой\s+функционал|"
        r"что\s+именно\s+вы\s+хотели\s+бы\s+включить|"
        r"какие\s+задачи\s+хотите\s+автоматизировать|"
        r"что\s+должен\s+делать\s+(?:бот|ассистент)",
        re.IGNORECASE,
    ),
    "volume": re.compile(
        r"какой\s+(?:у\s+вас\s+)?объем|"
        r"сколько\s+(?:обращений|запросов)\s+в\s+день",
        re.IGNORECASE,
    ),
    "timeline": re.compile(
        r"когда\s+(?:хотите\s+)?запустить|"
        r"когда\s+планируете\s+(?:старт|запуск|начать)",
        re.IGNORECASE,
    ),
    "handoff": re.compile(
        r"куда\s+(?:хотите\s+)?передавать\s+(?:лидов|заявки)|"
        r"в\s+какую\s+(?:систему|crm)\s+передавать",
        re.IGNORECASE,
    ),
}


def remove_known_field_reasks(answer: str, ctx: IntakeContext) -> str:
    """Strip sentences that ask for information already captured in IntakeContext.

    Only removes a sentence when the corresponding field is actually filled in,
    so we never silently drop a question that was legitimately open.
    """
    known = ctx.known_fields
    if not known:
        return answer

    active = [_REASK_PATTERNS[f] for f in known if f in _REASK_PATTERNS]
    if not active:
        return answer

    paragraphs = [p.strip() for p in answer.split("\n\n") if p.strip()]
    new_paras: list[str] = []
    for para in paragraphs:
        sentences = re.split(r"(?<=[.!?])\s+", para)
        kept = [s for s in sentences if not any(pat.search(s) for pat in active)]
        clean = " ".join(kept).strip().rstrip(",;")
        if clean:
            new_paras.append(clean)
    return "\n\n".join(new_paras) if new_paras else answer


# ---------------------------------------------------------------------------
# Package-aware answer templates
# ---------------------------------------------------------------------------

_KZT_START = "150 000–200 000 ₸ за запуск + 40 000–60 000 ₸/мес"
_KZT_START_SENTENCE = "150 000–200 000 ₸ за запуск и 40 000–60 000 ₸ в месяц за сопровождение"
_KZT_SALES_ASST = "от 350 000 ₸ за запуск + 120 000 ₸/мес"
_KZT_INTEGRATED = "от 700 000 ₸ за запуск + 200 000 ₸/мес"

_SKIP_BIZ = frozenset({"не указан", "unknown", ""})

# User-facing package names (PART 10). Never expose internal keys (base/agent).
_START_LABEL = "Pilot / Start"
_SALES_LABEL = "Sales Assistant"
_INTEGRATED_LABEL = "Integrated AI Employee"


def _pkg_label(pkg: str | None) -> str:
    """Map any internal/recommended package value to its user-facing name."""
    p = (pkg or "").strip().lower()
    if "integrated" in p:
        return _INTEGRATED_LABEL
    if "sales" in p or "agent" in p:
        return _SALES_LABEL
    if "start" in p or "pilot" in p or "base" in p or "basic" in p:
        return _START_LABEL
    return pkg or _START_LABEL


def _biz_phrase(ctx: IntakeContext) -> str:
    biz = (ctx.business_type or "").strip().lower()
    return f"для {biz}" if biz not in _SKIP_BIZ else "для вашей задачи"


def _tasks_str(ctx: IntakeContext) -> str:
    return ", ".join(ctx.tasks) if ctx.tasks else "выбранные задачи"


def _channels_str(ctx: IntakeContext) -> str:
    return ", ".join(ctx.channels) if ctx.channels else "WhatsApp"


def price_objection_answer(ctx: IntakeContext) -> str | None:
    """Package-aware price objection explanation using exact intake answers."""
    if not ctx.exists or not ctx.recommended_package:
        return None
    pkg = ctx.recommended_package
    tasks = _tasks_str(ctx)
    channels = _channels_str(ctx)
    handoff = ctx.handoff or "Google Sheets"

    if HIDE_DAMIWORKS_PUBLIC_PRICES:
        return (
            f"Стоимость {_pkg_label(pkg)} под ваши задачи ({tasks}, каналы: {channels}) "
            f"зависит от объёма работ и интеграций.\n\n"
            f"После короткого разбора предложим конкретный формат и объём запуска. "
            f"Если нужен вариант проще — можно начать с {_START_LABEL}: "
            f"базовые ответы + сбор контактов, без сложной квалификации.\n\n"
            f"Хотите обсудить варианты?"
        )

    price = ctx.shown_price or ""
    if "Sales Assistant" in pkg:
        return (
            f"Пакет Sales Assistant — под ваши задачи:\n"
            f"• Каналы: {channels}\n"
            f"• Задачи: {tasks}\n"
            f"• Передача в: {handoff}\n\n"
            f"Разовый запуск ({price or _KZT_SALES_ASST}) включает: подключение и настройку каналов, "
            f"базу знаний, сценарии квалификации и follow-up, интеграцию с {handoff}.\n\n"
            f"Абонплата — техподдержка, корректировки сценариев, мониторинг.\n\n"
            f"Если нужно проще (только ответы + сбор контакта, без follow-up) — "
            f"можно начать с {_START_LABEL}: {_KZT_START}."
        )
    if "Integrated AI Employee" in pkg:
        return (
            f"Цена обоснована задачами, которые вы выбрали:\n"
            f"• Каналы: {channels}\n"
            f"• Задачи: {tasks}\n"
            f"• Передача в: {handoff}\n\n"
            f"Разовый запуск ({price or _KZT_INTEGRATED}) включает: подключение всех каналов, "
            f"сложные сценарии квалификации, CRM-интеграцию, кастомные воркфлоу.\n\n"
            f"Абонплата — поддержка, обновления, мониторинг.\n\n"
            f"Если нужен вариант проще — рассмотрим Sales Assistant: {_KZT_SALES_ASST}."
        )
    if "Start" in pkg:
        return (
            f"Пакет {_START_LABEL} — базовая автоматизация под ваши задачи:\n"
            f"• Канал: {channels}\n"
            f"• Задачи: {tasks}\n\n"
            f"Ориентир: {price or _KZT_START}. Настройка 3–7 дней, без сложных интеграций."
        )
    return None


def implementation_answer(ctx: IntakeContext, last_assistant_message: str = "") -> str | None:
    """How the launch goes — numbered steps + a context line + a soft, non-contact
    next step (PART 5).  Informational: never forces a contact ask."""
    if not ctx.exists:
        return None
    channels = _channels_str(ctx)
    biz = (ctx.business_type or "").strip().lower()
    biz_line = (
        f"Для вашего бизнеса ({biz}) можно начать с каналов {channels}: "
        if biz and biz not in _SKIP_BIZ
        else f"Можно начать с каналов {channels}: "
    )
    return (
        "Запуск обычно проходит так:\n"
        "1. Уточняем задачи и каналы.\n"
        "2. Собираем базу знаний: товары, цены, доставка, оплата, возврат, частые вопросы.\n"
        "3. Настраиваем сценарии ответов и передачу заявок.\n"
        "4. Тестируем AI-сотрудника на реальных диалогах.\n"
        "5. Запускаем и вносим первые правки по результатам.\n\n"
        f"{biz_line}ответы на вопросы клиентов, сбор контактов и передача заявок менеджеру.\n\n"
        f"{pick_soft_next_step(last_assistant_message)}"
    )


def price_question_answer(ctx: IntakeContext) -> str | None:
    """Package-aware price answer when user asks what it costs."""
    if not ctx.exists or not ctx.recommended_package:
        return None
    pkg = ctx.recommended_package
    tasks = _tasks_str(ctx)

    if HIDE_DAMIWORKS_PUBLIC_PRICES:
        return (
            f"Для вашего набора задач — {tasks} — подойдёт {_pkg_label(pkg)}.\n\n"
            f"Точную стоимость лучше назвать после короткого разбора: важны каналы, "
            f"объём заявок, интеграции и глубина автоматизации. "
            f"Оставьте контакт — мы свяжемся и предложим конкретный формат запуска."
        )

    price = ctx.shown_price or ""
    if "Sales Assistant" in pkg:
        return (
            f"Для вашего набора задач — {tasks} — подойдёт {_SALES_LABEL}.\n\n"
            f"Ориентир: {price or _KZT_SALES_ASST}. "
            f"Если нужна только базовая автоматизация — {_START_LABEL}: {_KZT_START}."
        )
    if "Integrated AI Employee" in pkg:
        return (
            f"Для вашего набора задач — {tasks} — подойдёт {_INTEGRATED_LABEL}.\n\n"
            f"Ориентир: {price or _KZT_INTEGRATED}."
        )
    if "Start" in pkg:
        return (
            f"Для вашего набора задач — {tasks} — подойдёт {_START_LABEL}.\n\n"
            f"Ориентир: {price or _KZT_START}."
        )
    return None


def already_answered_acknowledgment(ctx: IntakeContext) -> str | None:
    """Acknowledgment when user says the bot is asking for info already given."""
    if not ctx.exists or not ctx.tasks or not ctx.recommended_package:
        return None
    pkg = ctx.recommended_package
    price = ctx.shown_price or ""
    channels = _channels_str(ctx)
    tasks = _tasks_str(ctx)
    biz = (ctx.business_type or "").strip().lower()
    next_step = (
        f"Следующий шаг — подготовить короткое ТЗ по вашему {biz} и примерам вопросов клиентов."
        if biz and biz not in _SKIP_BIZ else
        "Следующий шаг — подготовить короткое ТЗ и примеры вопросов клиентов."
    )
    if HIDE_DAMIWORKS_PUBLIC_PRICES:
        return (
            f"Да, вы правы — вы уже выбрали: {channels}, {tasks}.\n\n"
            f"Ориентируюсь на {_pkg_label(pkg)}. {next_step}"
        )
    price = ctx.shown_price or ""
    return (
        f"Да, вы правы — вы уже выбрали: {channels}, {tasks}.\n\n"
        f"Поэтому ориентируюсь на {_pkg_label(pkg)}: {price}. {next_step}"
    )


# ---------------------------------------------------------------------------
# Post-intake handoff — contact asks, soft non-contact next steps, dispatch
# ---------------------------------------------------------------------------

# Varied contact asks (PART 11). The repetition guard skips any phrase already
# present in the previous assistant message so the same one is never used twice
# in a row.
CONTACT_ASKS: tuple[str, ...] = (
    "Оставьте, пожалуйста, имя и номер WhatsApp/Telegram — мы свяжемся, уточним детали и предложим следующий шаг.",
    "Можете оставить номер WhatsApp/Telegram — мы передадим заявку команде.",
    "Если хотите продолжить, оставьте контакт, и мы обсудим запуск.",
    "Для следующего шага оставьте имя и номер — мы свяжемся и уточним детали.",
)

# Calendly-preferred contact ask — used only when the frontend reports that a
# booking CTA is visible (ChatRequest.calendly_enabled). Presents the call as
# the preferred next step while keeping WhatsApp/Telegram as an equal option.
CALENDLY_CONTACT_ASK = (
    "Лучший следующий шаг — выбрать удобное время для короткого 20-минутного звонка. "
    "Так я смогу быстро понять вашу воронку, каналы и где AI-сотрудник даст больше пользы.\n\n"
    "Можете забронировать звонок или просто оставить WhatsApp/Telegram — как удобнее."
)

# Soft, non-contact next steps for informational post-intake answers — never a
# contact ask (keeps the chat helpful, not pushy).
SOFT_NEXT_STEPS: tuple[str, ...] = (
    "Если хотите, следующим шагом можем перейти к запуску.",
    "Если захотите продолжить, я подскажу следующий шаг.",
)


def pick_contact_ask(last_assistant_message: str = "", *, calendly_enabled: bool = False) -> str:
    prev = last_assistant_message or ""
    if calendly_enabled and CALENDLY_CONTACT_ASK not in prev:
        return CALENDLY_CONTACT_ASK
    for ask in CONTACT_ASKS:
        if ask not in prev:
            return ask
    return CONTACT_ASKS[0]


def pick_soft_next_step(last_assistant_message: str = "") -> str:
    prev = last_assistant_message or ""
    for step in SOFT_NEXT_STEPS:
        if step not in prev:
            return step
    return SOFT_NEXT_STEPS[0]


def answer_has_contact_ask(answer: str) -> bool:
    text = answer or ""
    if CALENDLY_CONTACT_ASK in text:
        return True
    if any(ask in text for ask in CONTACT_ASKS):
        return True
    return bool(
        re.search(
            r"оставьте[^.?!]{0,40}(?:номер|контакт|имя)|номер\s+whatsapp|номер\s+telegram",
            text,
            re.IGNORECASE,
        )
    )


_PHONE_RE = re.compile(r"\+?\d[\d\-\s()]{6,}\d")


def _has_phone(text: str) -> bool:
    for match in _PHONE_RE.finditer(text or ""):
        if len(re.sub(r"\D", "", match.group(0))) >= 7:
            return True
    return False


_BUSINESS_DETAILS_RE = re.compile(
    r"прода[еёю]м?|продаю|доставк|оплат|kaspi|каспи|halyk|халык|возврат|"
    r"наш\s+магазин|у\s+нас\s+магазин|ассортимент|каталог|\bтовар\w*",
    re.IGNORECASE,
)


def _looks_like_business_details(message: str) -> bool:
    """True when the user volunteered substantive business info (not a question)."""
    if "?" in message:
        return False
    hits = len(_BUSINESS_DETAILS_RE.findall(message))
    return hits >= 2 or (hits >= 1 and len(message.strip()) >= 60)


# Neutral acknowledgements — short confirms that don't indicate start intent.
# MUST NOT be followed by a contact ask; respond with a soft continuation hint.
_NEUTRAL_ACK_RE = re.compile(
    r"^(?:понял[аи]?|понятно|ясно|ясненько|ок|окей|ok)\s*[.!,]*$",
    re.IGNORECASE,
)


def _is_neutral_ack(message: str) -> bool:
    m = (message or "").strip()
    if "?" in m or len(m.split()) > 4:
        return False
    return bool(_NEUTRAL_ACK_RE.match(m))


def neutral_ack_answer() -> str:
    return "Хорошо. Если захотите продолжить, следующим шагом можно перейти к запуску."


def start_handoff_answer(last_assistant_message: str = "", *, calendly_enabled: bool = False) -> str:
    """Acknowledge start intent and ask for contact (PART 2)."""
    return "Отлично. " + pick_contact_ask(last_assistant_message, calendly_enabled=calendly_enabled)


def phone_handoff_ack() -> str:
    """Acknowledge a provided phone number without a fake SLA (PART 8)."""
    return (
        "Отлично, номер записал. Передам заявку команде — "
        "с вами свяжутся в WhatsApp/Telegram и уточнят детали запуска."
    )


def not_remembered_answer(ctx: IntakeContext, last_assistant_message: str = "") -> str:
    """Reassure + summarize known context + soft non-contact next step (PART 6)."""
    biz = (ctx.business_type or "").strip().lower()
    parts: list[str] = []
    if biz and biz not in _SKIP_BIZ:
        parts.append(biz)
    if ctx.channels:
        parts.append(_channels_str(ctx))
    if ctx.volume:
        parts.append(f"{ctx.volume} обращений в день")
    summary = ", ".join(parts) if parts else "ваш сценарий"
    return (
        f"Ничего страшного. По вашим ответам я уже вижу базовый сценарий: {summary}, "
        f"ответы на вопросы и передача заявок менеджеру.\n\n"
        f"Недостающие детали можно спокойно уточнить на этапе настройки. Для старта достаточно "
        f"понять товары, доставку, оплату и возврат.\n\n"
        f"{pick_soft_next_step(last_assistant_message)}"
    )


def cheaper_answer(ctx: IntakeContext, last_assistant_message: str = "") -> str:  # noqa: ARG001
    """Downgrade explanation for 'можно начать дешевле?' (PART 4)."""
    if HIDE_DAMIWORKS_PUBLIC_PRICES:
        return (
            f"Да, можно начать с {_START_LABEL}. Это проще: AI-сотрудник будет отвечать "
            f"на частые вопросы, собирать контакты и передавать заявки менеджеру. Без сложной "
            f"квалификации, follow-up и интеграций на первом этапе.\n\n"
            f"Если после теста будет понятно, что нужно больше автоматизации, можно расширить до "
            f"{_SALES_LABEL}.\n\n"
            f"Хотите начать с {_START_LABEL}?"
        )
    return (
        f"Да, можно начать с {_START_LABEL}. Это проще и дешевле: AI-сотрудник будет отвечать "
        f"на частые вопросы, собирать контакты и передавать заявки менеджеру. Без сложной "
        f"квалификации, follow-up и интеграций на первом этапе.\n\n"
        f"Ориентир: {_KZT_START_SENTENCE}.\n\n"
        f"Если после теста будет понятно, что нужно больше автоматизации, можно расширить до "
        f"{_SALES_LABEL}.\n\n"
        f"Хотите начать с {_START_LABEL}?"
    )


def business_details_answer(ctx: IntakeContext, last_assistant_message: str = "") -> str:  # noqa: ARG001
    """Treat volunteered business details as enough for an initial estimate (PART 7)."""
    if HIDE_DAMIWORKS_PUBLIC_PRICES:
        return (
            f"Отлично, этого уже достаточно для первичной оценки. Для вашего бизнеса можно начать "
            f"с {_START_LABEL}: AI-сотрудник будет отвечать на вопросы клиентов, собирать контакты "
            f"и передавать заявки менеджеру.\n\n"
            f"{pick_contact_ask(last_assistant_message)}"
        )
    return (
        f"Отлично, этого уже достаточно для первичной оценки. Для вашего бизнеса можно начать "
        f"с {_START_LABEL}: AI-сотрудник будет отвечать на вопросы клиентов, собирать контакты "
        f"и передавать заявки менеджеру.\n\n"
        f"Ориентир: {_KZT_START_SENTENCE}.\n\n"
        f"{pick_contact_ask(last_assistant_message)}"
    )


# ---------------------------------------------------------------------------
# Contact collection — accept a contact reply after the consultant asked for it
# and close the lead instead of continuing qualification (PART 1–4).
# ---------------------------------------------------------------------------

_ASKED_FOR_CONTACT_RE = re.compile(
    r"остав\w*|"                       # оставьте / оставить
    r"\bимя\b|"
    r"\bномер\b|"
    r"whatsapp|"
    r"telegram|телеграм\w*|"
    r"\bконтакт\w*|"
    r"свяжемся|с\s+вами\s+свяж\w+|"
    r"следующ\w+\s+шаг|"
    r"перед(?:ам|адим)\s+заявку",
    re.IGNORECASE,
)


def assistant_asked_for_contact(last_assistant_message: str) -> bool:
    """True if the previous assistant message asked the user for contact info."""
    return bool(_ASKED_FOR_CONTACT_RE.search(last_assistant_message or ""))


_TELEGRAM_RE = re.compile(
    r"@[A-Za-z0-9_]{3,}|t\.me/|\btelegram\b|\bтелеграм\w*|\bтг\b|"
    r"мой\s+тг|мой\s+telegram",
    re.IGNORECASE,
)


def _is_telegram_contact(message: str) -> bool:
    return bool(_TELEGRAM_RE.search(message or ""))


# Post-intake: user names a concrete extra feature or task they want included —
# a short noun phrase with no question mark.  Triggers acknowledge + contact ask
# rather than falling through to the LLM for another discovery round.
_FEATURE_DETAIL_RE = re.compile(
    r"\bквалификаци\w*|"
    r"\bсбор\s+(?:контакт|лид|заявок)\w*|"
    r"\bналичи\w+\s+товар\w*|"
    r"\bдоставк\w+|"
    r"\bоплат\w+|"
    r"\bзапис[ьи]\b|\bзапись\b|"
    r"\bстатус\w+\s+(?:заказ|доставк)\w*|"
    r"\bfollow[\s-]?up\b|"
    r"\bапсейл\w*|\bupsell\b|"
    r"\bкросс[\s-]?продаж\w*",
    re.IGNORECASE,
)


def is_feature_detail(user_message: str) -> bool:
    """True when user mentions a concrete extra feature/task post-intake (no '?', ≤6 words)."""
    m = (user_message or "").strip()
    if not m or "?" in m or len(m.split()) > 6:
        return False
    return bool(_FEATURE_DETAIL_RE.search(m.casefold().replace("ё", "е")))


def feature_detail_answer(last_assistant_message: str = "", *, calendly_enabled: bool = False) -> str:
    """Acknowledge a user-mentioned feature and move to contact ask."""
    return "Понял, добавим в запуск. " + pick_contact_ask(last_assistant_message, calendly_enabled=calendly_enabled)


# Generic fillers that must never be treated as a contact name (PART 2).
_CONTACT_FILLERS = frozenset(
    {
        "да", "нет", "ок", "окей", "ok", "хорошо", "ладно", "понятно", "не знаю",
        "не помню", "пока нет", "позже", "что дальше", "как начать",
        "сколько стоит", "что входит", "можно дешевле",
        # Neutral acknowledgements — must not be misread as a contact name after a contact ask.
        "понял", "поняла", "ясно",
    }
)

_NAME_ALLOWED_RE = re.compile(r"^[\w .\-]+$", re.UNICODE)
_HAS_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)


def _is_other_post_intake_intent(message: str) -> bool:
    """True when the message is some other deterministic intent (start/cheaper/
    not-remembered/price/impl/feature-detail), so it must not be misread as a bare name."""
    if is_start_intent(message):
        return True
    if is_feature_detail(message):
        return True
    m = message.casefold().replace("ё", "е")
    if _NOT_REMEMBERED_RE.search(m) or _CHEAPER_RE.search(m):
        return True
    return detect_intent(message) != "generic"


def _is_plausible_name(message: str) -> bool:
    s = (message or "").strip()
    if not (2 <= len(s) <= 40):
        return False
    if "?" in s:
        return False
    if len(s.split()) > 4:
        return False
    if not _HAS_LETTER_RE.search(s):
        return False
    if not _NAME_ALLOWED_RE.match(s):
        return False
    return s.casefold().replace("ё", "е") not in _CONTACT_FILLERS


@dataclass
class ParsedContact:
    kind: str | None  # "phone" | "telegram" | "name" | None
    name: str | None = None
    phone: str | None = None
    telegram: str | None = None
    raw: str = ""


def parse_contact(user_message: str, last_assistant_message: str = "") -> ParsedContact:
    """Classify a user reply as a contact: phone or Telegram (always), or a
    plausible bare name (only right after a contact ask). Mirrors the frontend
    lib/contact.ts so both sides agree."""
    raw = (user_message or "").strip()
    if _has_phone(raw):
        m = re.search(r"\+?\d[\d\-\s()]{6,}\d", raw)
        return ParsedContact("phone", phone=(m.group(0).strip() if m else raw), raw=raw)
    if _is_telegram_contact(raw):
        at = re.search(r"@[A-Za-z0-9_]{3,}", raw)
        return ParsedContact("telegram", telegram=(at.group(0) if at else raw), raw=raw)
    if (
        assistant_asked_for_contact(last_assistant_message)
        and _is_plausible_name(raw)
        and not _is_other_post_intake_intent(raw)
    ):
        return ParsedContact("name", name=raw, raw=raw)
    return ParsedContact(None, raw=raw)


def has_contact_like_reply(user_message: str, last_assistant_message: str = "") -> bool:
    """True if the user message is a contact reply (phone / Telegram / bare name
    after a contact ask)."""
    return parse_contact(user_message, last_assistant_message).kind is not None


_CONTACT_CLOSE_GENERIC = (
    "Отлично, контакт получил. Передам заявку команде — "
    "с вами свяжутся в WhatsApp/Telegram и уточнят детали запуска."
)
_CONTACT_CLOSE_TELEGRAM = (
    "Отлично, Telegram получил. Передам заявку команде — "
    "с вами свяжутся и уточнят детали запуска."
)


def contact_close_answer(user_message: str) -> str:
    """Final close answer when contact is received — never re-qualifies (PART 4)."""
    if _has_phone(user_message):
        return phone_handoff_ack()
    if _is_telegram_contact(user_message):
        return _CONTACT_CLOSE_TELEGRAM
    return _CONTACT_CLOSE_GENERIC


def post_intake_response(
    user_message: str,
    ctx: IntakeContext,
    *,
    last_assistant_message: str = "",
) -> str | None:
    """Deterministic post-intake reply for obvious cases, else None (LLM answers).

    Order matters: contact reply → start intent → not-remembered → cheaper →
    price/impl intents → volunteered business details.
    """
    if not ctx.exists:
        return None
    # Contact reply (phone / Telegram / bare name after a contact ask) closes the
    # lead before any other branch — never fall through to qualification.
    if has_contact_like_reply(user_message, last_assistant_message):
        return contact_close_answer(user_message)

    msg = user_message.casefold().replace("ё", "е")
    if is_start_intent(user_message):
        return start_handoff_answer(last_assistant_message)
    if _NOT_REMEMBERED_RE.search(msg):
        return not_remembered_answer(ctx, last_assistant_message)
    if _CHEAPER_RE.search(msg):
        return cheaper_answer(ctx, last_assistant_message)

    intent = detect_intent(user_message)
    if intent == "price_objection":
        return price_objection_answer(ctx)
    if intent == "already_answered_complaint":
        return already_answered_acknowledgment(ctx)
    if intent == "price_question":
        return price_question_answer(ctx)
    if intent == "implementation_question":
        return implementation_answer(ctx, last_assistant_message)

    if _looks_like_business_details(user_message):
        return business_details_answer(ctx, last_assistant_message)

    # Neutral acknowledgement (понял/ясно/ок without a proposal) — soft continuation,
    # no discovery question, no premature contact ask.
    if _is_neutral_ack(user_message):
        return neutral_ack_answer()

    return None


# ---------------------------------------------------------------------------
# Pre-intake free-form profile — deterministic extraction from natural chat.
#
# The guided questionnaire is path A; this section makes path B (free-form
# conversation) first-class: the same channels/tasks/CRM/business facts are
# extracted from normal user messages, so the consultant can move to the
# Calendly/contact step without forcing the questionnaire, and the frontend
# summary can fill in real time.
# ---------------------------------------------------------------------------


@dataclass
class FreeformProfile:
    channels: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    crm: str | None = None
    business_type: str | None = None


_FF_CHANNEL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"whats\s*app|ватсап|вотсап|воцап", re.IGNORECASE), "WhatsApp"),
    (re.compile(r"instagram|инстаграм", re.IGNORECASE), "Instagram"),
    (re.compile(r"telegram|телеграм|\bтг\b", re.IGNORECASE), "Telegram"),
    (re.compile(r"2\s*(?:гис|gis)|дубль\s*гис", re.IGNORECASE), "2GIS"),
    (re.compile(r"\bсайт\w*|website", re.IGNORECASE), "Website"),
)

_FF_TASK_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"отвеча\w+|ответы\s+(?:клиент|на\s+вопрос)|консультир", re.IGNORECASE),
        "Отвечать на вопросы",
    ),
    (
        re.compile(r"запис\w+|appointment|назнача\w+\s+(?:при[её]м|встреч)|бронир", re.IGNORECASE),
        "Запись клиентов",
    ),
    (re.compile(r"собира\w+\s+контакт|сбор\s+контакт", re.IGNORECASE), "Собирать контакты"),
    (re.compile(r"квалифи", re.IGNORECASE), "Квалифицировать лидов"),
    (
        re.compile(r"передава\w+\s+заявк|передача\s+заявок", re.IGNORECASE),
        "Передавать заявки менеджеру",
    ),
    (re.compile(r"follow[\s-]?up|фоллоу", re.IGNORECASE), "Делать follow-up"),
)

_FF_CRM_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b1[сc]\b", re.IGNORECASE), "1С"),
    (re.compile(r"amo\s*crm|амосрм", re.IGNORECASE), "amoCRM"),
    (re.compile(r"битрикс|bitrix", re.IGNORECASE), "Bitrix24"),
    (re.compile(r"google\s*sheets|гугл\s*табл", re.IGNORECASE), "Google Sheets"),
)

_FF_BUSINESS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"стоматолог", re.IGNORECASE), "Стоматология"),
    (re.compile(r"клиник|медцентр|мед\.?\s*центр", re.IGNORECASE), "Клиника/салон"),
    (re.compile(r"салон|барбершоп", re.IGNORECASE), "Клиника/салон"),
    (re.compile(r"магазин", re.IGNORECASE), "Онлайн-магазин"),
    (re.compile(r"школ\w+|курс\w+|репетит|обучени", re.IGNORECASE), "Обучение"),
    (re.compile(r"кафе|ресторан|доставк\w+\s+еды", re.IGNORECASE), "Услуги"),
)


def extract_freeform_profile(user_texts: list[str]) -> FreeformProfile:
    """Deterministically extract channels/tasks/CRM/business from user messages."""
    profile = FreeformProfile()
    combined = "\n".join(t for t in (user_texts or []) if t)
    for pattern, label in _FF_CHANNEL_PATTERNS:
        if pattern.search(combined) and label not in profile.channels:
            profile.channels.append(label)
    for pattern, label in _FF_TASK_PATTERNS:
        if pattern.search(combined) and label not in profile.tasks:
            profile.tasks.append(label)
    for pattern, label in _FF_CRM_PATTERNS:
        if pattern.search(combined):
            profile.crm = label
            break
    for pattern, label in _FF_BUSINESS_PATTERNS:
        if pattern.search(combined):
            profile.business_type = label
            break
    return profile


def has_enough_freeform_context(profile: FreeformProfile) -> bool:
    """Enough for a first scoping call: at least one channel and one task."""
    return bool(profile.channels and profile.tasks)


def profile_to_intake_context(profile: FreeformProfile) -> IntakeContext:
    """Map a free-form profile onto IntakeContext so lead rows/notifications work."""
    qualifying = {"Квалифицировать лидов", "Передавать заявки менеджеру", "Делать follow-up"}
    pkg = "Sales Assistant" if qualifying & set(profile.tasks) else "Start"
    return IntakeContext(
        exists=True,
        channels=list(profile.channels),
        tasks=list(profile.tasks),
        handoff=profile.crm,
        business_type=profile.business_type,
        recommended_package=pkg,
    )


# User asks whether/how to leave THEIR contact ("контакт будешь брать?",
# "куда номер оставить?"). This is DamiWorks conversion intent — never a
# question about collecting end-customer contacts.
_CONTACT_OFFER_RE = re.compile(
    r"контакт\w*\s+(?:будешь|будете|возьм[её]шь|возьм[её]те|брать|бер[её]те|нужен)|"
    r"куда\s+(?:номер|контакт|телефон|заявку)\s*(?:оставить|остав\w*|писать|скинуть|отправить)?|"
    r"как\s+(?:с\s+вами\s+)?связаться|"
    r"как\s+(?:мне\s+)?(?:оставить|отправить)\s+(?:заявку|контакт|номер)|"
    r"как\s+(?:мне\s+)?(?:заявку|контакт|номер)\s+(?:оставить|отправить)|"
    r"(?:номер|контакт)\s+оставить\b|"
    r"хотите\s+мой\s+(?:номер|контакт)|"
    r"взять\s+(?:мой\s+)?(?:номер|контакт)",
    re.IGNORECASE,
)

# User dismisses the current question ("это не важно") — stop asking, move on.
_DISMISSAL_RE = re.compile(
    r"^\s*(?:это\s+)?не\s*важно[\s.!]*$|без\s+разницы|какая\s+разница|\bневажно\b",
    re.IGNORECASE,
)

# Price/objection vocabulary — those turns belong to the FAQ/price branches,
# not the free-form close.
_FF_PRICE_VOCAB_RE = re.compile(
    r"сто[ия]т|стоимост|цен[аыуе]|дорог|дешев|скидк|тариф|прайс", re.IGNORECASE
)

_FREEFORM_CLOSE_MARKER = "достаточно для первичного разбора"

_PREINTAKE_CLOSED_ANSWER = (
    "Заявка уже отправлена — команда свяжется с вами в WhatsApp/Telegram "
    "и уточнит детали запуска."
)


def is_contact_offer_question(user_message: str) -> bool:
    msg = (user_message or "").casefold().replace("ё", "е")
    return bool(_CONTACT_OFFER_RE.search(msg))


def contact_offer_answer(*, calendly_enabled: bool = False) -> str:
    if calendly_enabled:
        return (
            "Да. Удобнее всего — сразу выбрать время для короткого звонка. "
            "Или оставьте WhatsApp/Telegram, и я передам заявку команде."
        )
    return (
        "Да. Оставьте, пожалуйста, ваше имя и WhatsApp/Telegram — "
        "передам заявку команде, и с вами свяжутся."
    )


def freeform_close_answer(profile: FreeformProfile, *, calendly_enabled: bool = False) -> str:
    """Transition to the scoping call once free-form context is sufficient.

    Careful wording for integrations: we discuss HOW to hand data over — never
    promise a specific automatic integration.
    """
    bits: list[str] = []
    if profile.channels:
        bits.append(", ".join(profile.channels))
    if profile.crm:
        bits.append(f"как передавать заявки в {profile.crm} — напрямую, через API или таблицу")
    scope = "посмотрим " + "; ".join(bits) if bits else "разберём ваши каналы и задачи"
    tail = (
        "Можете забронировать время для звонка или оставить WhatsApp/Telegram — как удобнее."
        if calendly_enabled
        else "Оставьте, пожалуйста, ваше имя и WhatsApp/Telegram — мы свяжемся и предложим формат запуска."
    )
    return (
        f"Этого уже достаточно для первичного разбора. Лучше всего обсудить сценарий "
        f"на коротком 20-минутном звонке: {scope}.\n\n{tail}"
    )


@dataclass
class PreintakeTurn:
    answer: str | None
    lead_status: str | None = None  # "contact_requested" | "contact_collected"
    contact: ParsedContact | None = None


def resolve_preintake_turn(
    user_message: str,
    profile: FreeformProfile,
    last_assistant_message: str = "",
    *,
    calendly_enabled: bool = False,
    lead_closed: bool = False,
) -> PreintakeTurn:
    """Deterministic pre-intake turn for the free-form conversation path.

    Order: closed → contact reply → contact-offer question → friction
    (already-said / dismissal) → enough-context close on short low-info
    messages. Returns answer=None when the LLM should handle the turn.
    """
    msg = (user_message or "").strip()
    if not msg:
        return PreintakeTurn(None)
    if lead_closed:
        return PreintakeTurn(_PREINTAKE_CLOSED_ANSWER, "contact_collected")

    contact = parse_contact(msg, last_assistant_message)
    if contact.kind == "telegram":
        # A bare "клиенты пишут в телеграм" is channel info, not the user's own
        # contact — require an actual handle/link or a preceding contact ask.
        if not re.search(r"@[A-Za-z0-9_]{3,}|t\.me/", msg) and not assistant_asked_for_contact(
            last_assistant_message
        ):
            contact = ParsedContact(None, raw=msg)
    if contact.kind:
        return PreintakeTurn(contact_close_answer(msg), "contact_collected", contact)

    low = msg.casefold().replace("ё", "е")
    if _CONTACT_OFFER_RE.search(low):
        return PreintakeTurn(
            contact_offer_answer(calendly_enabled=calendly_enabled), "contact_requested"
        )

    # Friction: the user says they already answered, or dismisses the question.
    # Stop the loop and move to the scoping-call close.
    if _ALREADY_ANSWERED_RE.search(low) or _DISMISSAL_RE.search(low):
        return PreintakeTurn(
            freeform_close_answer(profile, calendly_enabled=calendly_enabled),
            "contact_requested",
        )

    # Enough context + a short low-info reply ("1с", "срм", "да") → close.
    # Never on questions or price/objection turns, and never twice in a row.
    if (
        has_enough_freeform_context(profile)
        and "?" not in msg
        and len(msg.split()) <= 6
        and not _FF_PRICE_VOCAB_RE.search(low)
        and _FREEFORM_CLOSE_MARKER not in (last_assistant_message or "")
    ):
        return PreintakeTurn(
            freeform_close_answer(profile, calendly_enabled=calendly_enabled),
            "contact_requested",
        )

    return PreintakeTurn(None)


# ---------------------------------------------------------------------------
# Policy entry point
# ---------------------------------------------------------------------------


def apply_post_intake_policy(
    answer: str,
    user_message: str,
    ctx: IntakeContext,
    close_intent: bool,  # noqa: ARG001 — reserved for future close_intent templates
) -> str:
    """Full pipeline: detect intent, return canned answer or strip known-field re-asks.

    When no intake context is present, returns the original answer unchanged.
    When a deterministic intent is detected (objection / question / complaint),
    returns the canned template.  Otherwise strips any re-ask of known fields.
    """
    if not ctx.exists:
        return answer

    intent = detect_intent(user_message)

    if intent == "price_objection":
        canned = price_objection_answer(ctx)
        if canned:
            return canned

    if intent == "already_answered_complaint":
        ack = already_answered_acknowledgment(ctx)
        if ack:
            return ack

    if intent == "price_question":
        canned = price_question_answer(ctx)
        if canned:
            return canned

    if intent == "implementation_question":
        canned = implementation_answer(ctx)
        if canned:
            return canned

    return remove_known_field_reasks(answer, ctx)
