"""Tests for the deterministic response stylist (app/response_stylist.py).

Covers: split into 1-3 messenger parts, the exactly-one-question rule
(deterministic path + injected LLM repair pass), and the never-raise contract.
"""

from __future__ import annotations

import asyncio

from app.response_stylist import (
    MAX_PARTS,
    build_style_repair_prompt,
    count_questions,
    ensure_single_question,
    split_into_parts,
    style_answer,
)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# split_into_parts
# ---------------------------------------------------------------------------

def test_short_answer_stays_single_part() -> None:
    assert split_into_parts("Привет! Чем могу помочь?") == ["Привет! Чем могу помочь?"]


def test_blank_lines_define_parts() -> None:
    answer = "Первый абзац.\n\nВторой абзац.\n\nТретий абзац."
    assert split_into_parts(answer) == ["Первый абзац.", "Второй абзац.", "Третий абзац."]


def test_overflow_tail_is_merged_into_last_part() -> None:
    answer = "\n\n".join(f"Абзац {i}." for i in range(1, 6))
    parts = split_into_parts(answer)
    assert len(parts) == MAX_PARTS
    assert parts[0] == "Абзац 1."
    assert parts[1] == "Абзац 2."
    assert "Абзац 3." in parts[2] and "Абзац 5." in parts[2]


def test_long_wall_of_text_splits_on_sentence_boundaries() -> None:
    sentences = [
        f"Предложение номер {i} с достаточно длинным текстом про автоматизацию продаж."
        for i in range(1, 9)
    ]
    answer = " ".join(sentences)
    assert len(answer) > 450
    parts = split_into_parts(answer)
    assert 2 <= len(parts) <= MAX_PARTS
    # No content is lost: every sentence still appears in exactly one part.
    joined = " ".join(parts)
    for sentence in sentences:
        assert sentence in joined


def test_overflow_tail_with_price_and_date_is_never_dropped() -> None:
    # Invariant: the merged tail keeps commercial facts — a price/date in the
    # overflowing part must survive the split verbatim.
    tail = "Стоимость консультации — 5 000 ₸. Ближайшая запись на завтра в 10:00."
    answer = "\n\n".join([f"Абзац {i}." for i in range(1, 5)] + [tail])
    parts = split_into_parts(answer)
    assert len(parts) == MAX_PARTS
    assert tail in "\n\n".join(parts)


def test_style_answer_never_loses_content_only_replaces_question_marks() -> None:
    # Invariant: deterministic question-stripping rewrites "?" to "." but never
    # deletes text — the joined result differs from the input only in punctuation.
    answer = "Подходит такой формат?\n\nЦена — 12 000 ₸, записываем на завтра?"
    parts = _run(style_answer(answer))
    joined = "\n\n".join(parts)
    assert count_questions(joined) == 1
    assert "Цена — 12 000 ₸, записываем на завтра." in joined


def test_empty_input_never_returns_empty_list() -> None:
    assert split_into_parts("") == [""]
    assert split_into_parts("   ") == ["   "]


def test_whitespace_only_separators_are_collapsed() -> None:
    answer = "Один.\n \n \nДва."
    assert split_into_parts(answer) == ["Один.", "Два."]


# ---------------------------------------------------------------------------
# count_questions
# ---------------------------------------------------------------------------

def test_count_questions_basic() -> None:
    assert count_questions("Привет.") == 0
    assert count_questions("Как дела? Что делаешь?") == 2
    assert count_questions("Правда?!") == 1
    assert count_questions("Точно??") == 1


# ---------------------------------------------------------------------------
# ensure_single_question
# ---------------------------------------------------------------------------

def test_single_question_passes_through_untouched() -> None:
    parts = ["Отличный вопрос.", "Расскажу подробнее.", "Какой у вас канал продаж?"]
    assert ensure_single_question(parts) == parts


def test_later_questions_become_statements() -> None:
    parts = [
        "Понял вас. Какой у вас канал продаж?",
        "А сколько заявок в день? И кто отвечает?",
    ]
    result = ensure_single_question(parts)
    assert count_questions("\n\n".join(result)) == 1
    assert result[0] == "Понял вас. Какой у вас канал продаж?"
    assert result[1] == "А сколько заявок в день. И кто отвечает."


def test_first_part_keeps_only_its_first_question() -> None:
    parts = ["Какой канал? И какой объём?", "Остальное без вопросов."]
    result = ensure_single_question(parts)
    assert count_questions(result[0]) == 1
    assert result[0].startswith("Какой канал?")


def test_question_exclamation_combo_is_preserved_as_exclamation() -> None:
    parts = ["Что думаете?", "Серьёзно?!"]
    result = ensure_single_question(parts)
    assert result[1] == "Серьёзно!"


# ---------------------------------------------------------------------------
# style_answer (with injected repair)
# ---------------------------------------------------------------------------

def test_style_answer_no_repair_needed() -> None:
    called = False

    async def repair(_: str) -> str | None:
        nonlocal called
        called = True
        return "unused"

    parts = _run(style_answer("Короткий ответ. Один вопрос?", llm_repair=repair))
    assert parts == ["Короткий ответ. Один вопрос?"]
    assert called is False


def test_style_answer_uses_repair_when_it_fixes_questions() -> None:
    async def repair(_: str) -> str | None:
        return "Собрал всё в одну мысль.\n\nКакой у вас канал продаж?"

    answer = "Какой канал? Сколько заявок? Кто отвечает?"
    parts = _run(style_answer(answer, llm_repair=repair))
    assert parts == ["Собрал всё в одну мысль.", "Какой у вас канал продаж?"]


def test_style_answer_falls_back_when_repair_returns_none() -> None:
    async def repair(_: str) -> str | None:
        return None

    answer = "Какой канал?\n\nСколько заявок?"
    parts = _run(style_answer(answer, llm_repair=repair))
    assert count_questions("\n\n".join(parts)) == 1


def test_style_answer_falls_back_when_repair_raises() -> None:
    async def repair(_: str) -> str | None:
        raise RuntimeError("classifier is down")

    answer = "Какой канал?\n\nСколько заявок?"
    parts = _run(style_answer(answer, llm_repair=repair))
    assert count_questions("\n\n".join(parts)) == 1
    assert "Какой канал?" in parts[0]


def test_style_answer_deterministic_when_repair_keeps_many_questions() -> None:
    async def repair(_: str) -> str | None:
        return "Всё равно два вопроса? И ещё один?"

    parts = _run(style_answer("Вопрос? Вопрос?", llm_repair=repair))
    assert count_questions("\n\n".join(parts)) == 1


def test_style_answer_without_repair_is_deterministic() -> None:
    parts = _run(style_answer("Первый?\n\nВторой?\n\nТретий."))
    assert count_questions("\n\n".join(parts)) == 1
    assert parts[0] == "Первый?"


def test_build_style_repair_prompt_contains_answer() -> None:
    prompt = build_style_repair_prompt("Текст ответа?")
    assert "Текст ответа?" in prompt
    assert "один" in prompt.lower()
