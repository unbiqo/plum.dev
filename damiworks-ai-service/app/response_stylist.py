"""Deterministic post-processing that shapes a final consultant answer into
1-3 short messenger-style parts with exactly one question.

Pure Python — the optional LLM repair pass is injected as a callable, so this
module never imports the LLM service. Every public function is best-effort:
on any inconsistency it falls back to the deterministic path and never raises.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

MAX_PARTS = 3
# Answers longer than this without blank lines get split on sentence boundaries.
_LONG_ANSWER_CHARS = 450

_BLANK_LINE_RE = re.compile(r"\n\s*\n")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?…])\s+")
# A question is a run of "?" with optional surrounding "!" ("Как??", "Правда?!").
_QUESTION_RE = re.compile(r"!*\?+!*")

STYLE_REPAIR_SYSTEM_PROMPT = (
    "Ты — редактор живых сообщений для мессенджера. Перепиши сообщение консультанта "
    "так, чтобы в нём остался ровно ОДИН вопрос (самый важный), смысл и факты "
    "сохранились, а текст состоял из 1-3 коротких абзацев по 1-2 предложения, "
    "разделённых пустой строкой. Верни только итоговый текст на русском, без "
    "пояснений, JSON и markdown."
)


def build_style_repair_prompt(answer: str) -> str:
    """Prompt for the single cheap repair pass (too many questions)."""
    return (
        "Сообщение консультанта содержит несколько вопросов. Перепиши его, оставив "
        "ровно один (самый важный) вопрос и сохранив смысл и факты:\n\n"
        f"{answer}"
    )


def count_questions(text: str) -> int:
    """Count sentence-ending question marks; "?!"/"??" count as one."""
    return len(_QUESTION_RE.findall(text))


def _split_sentences(text: str) -> list[str]:
    return [piece.strip() for piece in _SENTENCE_END_RE.split(text) if piece.strip()]


def split_into_parts(answer: str, max_parts: int = MAX_PARTS) -> list[str]:
    """Split ``answer`` into 1..``max_parts`` messenger parts.

    Primary split is on blank lines; an over-long single block is split on
    sentence boundaries into 2-3 roughly even parts. Overflowing tail is merged
    back into the last part. Never returns an empty list.
    """
    stripped = (answer or "").strip()
    if not stripped:
        return [answer]

    parts = [piece.strip() for piece in _BLANK_LINE_RE.split(stripped) if piece.strip()]

    if len(parts) == 1 and len(stripped) > _LONG_ANSWER_CHARS:
        sentences = _split_sentences(stripped)
        if len(sentences) >= 2 * max_parts - 1:
            chunk_size = max(1, -(-len(sentences)) // max_parts)  # ceil
            parts = [
                " ".join(sentences[i : i + chunk_size])
                for i in range(0, len(sentences), chunk_size)
            ]

    if len(parts) > max_parts:
        parts = parts[: max_parts - 1] + ["\n\n".join(parts[max_parts - 1 :])]

    return parts or [stripped]


def _strip_questions(text: str) -> str:
    """Turn every question sentence into a statement, deterministically.

    An exclamation attached to the question ("Серьёзно?!") survives as a plain
    exclamation; plain questions end with a period.
    """

    def _sub(match: re.Match[str]) -> str:
        return "!" if "!" in match.group(0) else "."

    stripped = _QUESTION_RE.sub(_sub, text)
    while ".." in stripped:
        stripped = stripped.replace("..", ".")
    return stripped


def _keep_first_question(text: str) -> str:
    """Keep the first question mark in ``text``; strip all later ones."""
    match = _QUESTION_RE.search(text)
    if match is None:
        return text
    head, tail = text[: match.end()], text[match.end() :]
    return head + _strip_questions(tail)


def ensure_single_question(parts: list[str]) -> list[str]:
    """Reduce ``parts`` to exactly one question (the first one), deterministically.

    Later question sentences become statements. Parts without questions stay
    untouched. Never raises.
    """
    if count_questions("\n\n".join(parts)) <= 1:
        return parts

    result: list[str] = []
    question_kept = False
    for part in parts:
        if count_questions(part) == 0:
            result.append(part)
            continue
        if not question_kept:
            result.append(_keep_first_question(part))
            question_kept = True
        else:
            result.append(_strip_questions(part))
    return result


async def style_answer(
    answer: str,
    *,
    llm_repair: Callable[[str], Awaitable[str | None]] | None = None,
    max_parts: int = MAX_PARTS,
) -> list[str]:
    """Shape ``answer`` into 1-3 parts with at most one question.

    Pipeline: deterministic split -> if >1 question and ``llm_repair`` is
    available, one cheap repair pass -> if still >1 question (or no repair),
    deterministic ``ensure_single_question``. Never raises.
    """
    parts = split_into_parts(answer, max_parts=max_parts)
    if count_questions("\n\n".join(parts)) <= 1:
        return parts

    if llm_repair is not None:
        try:
            repaired = await llm_repair(answer)
        except Exception:
            logger.warning("Style repair pass failed; using deterministic fallback")
            repaired = None
        if repaired and repaired.strip():
            repaired_parts = split_into_parts(repaired.strip(), max_parts=max_parts)
            if count_questions("\n\n".join(repaired_parts)) <= 1:
                return repaired_parts
            # Repair improved the shape but kept too many questions: finish
            # deterministically on the repaired text.
            return ensure_single_question(repaired_parts)

    return ensure_single_question(parts)
