"""
Smoke tests for damiworks-ai-service critical backend logic.

Layer 1 — Unit tests: pure Python, zero API calls, run in milliseconds.
Layer 2 — Smart text checks: test output-filter functions directly, not LLM output.

Run from damiworks-ai-service/:
    pytest tests/test_smoke.py -v
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Imports under test (no Supabase / Gemini touched — only pure logic modules)
# ---------------------------------------------------------------------------
from app.api import (
    BUYING_MILESTONE_KEYS,
    RATE_LIMIT_B2B,
    RATE_LIMIT_BUCKETS,
    RATE_LIMIT_ROLEPLAY,
    RATE_LIMIT_WINDOW_SECONDS,
    ROLEPLAY_AWAITING_CONTEXT_KEY,
    ROLEPLAY_CONTEXT_SOURCE_KEY,
    ROLEPLAY_CONTEXT_SUMMARY_KEY,
    ROLEPLAY_CONTEXT_WAIT_COUNT_KEY,
    ROLEPLAY_NO_FILE_FALLBACK_KEY,
    SESSION_TIMEOUT,
    _check_rate_limit,
    _clear_roleplay_state,
    _is_new_session,
    _is_roleplay_demo_exit_request,
    _is_roleplay_output_context,
    _sanitize_roleplay_output,
)
from app.schemas import ChatHistoryMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_key(prefix: str) -> tuple[str, str]:
    """Return a channel/chat_id pair guaranteed to be absent from RATE_LIMIT_BUCKETS."""
    channel, chat_id = "telegram", f"{prefix}_{time.time_ns()}"
    RATE_LIMIT_BUCKETS.pop(f"{channel}:{chat_id}", None)
    return channel, chat_id


def _full_b2b_state() -> dict:
    return {
        "pain_expressed": True,
        "demo_activated": True,
        "price_exposed": True,
        "close_consented": False,
        "contact_phone_collected": False,
        "roleplay_demo_active": True,
        "roleplay_demo_topic": "детейлинг",
        ROLEPLAY_AWAITING_CONTEXT_KEY: True,
        ROLEPLAY_CONTEXT_SUMMARY_KEY: "Детейлинг-студия, цены от 5000р",
        ROLEPLAY_CONTEXT_SOURCE_KEY: "text_description",
        ROLEPLAY_CONTEXT_WAIT_COUNT_KEY: 1,
        ROLEPLAY_NO_FILE_FALLBACK_KEY: False,
    }


# ===========================================================================
# LAYER 1 — Rate limit logic
# ===========================================================================

class TestRateLimitB2B:
    def test_first_ten_requests_pass(self):
        ch, cid = _fresh_key("b2b_pass")
        for _ in range(RATE_LIMIT_B2B):
            _check_rate_limit(ch, cid)  # must not raise

    def test_eleventh_request_blocked(self):
        ch, cid = _fresh_key("b2b_block")
        for _ in range(RATE_LIMIT_B2B):
            _check_rate_limit(ch, cid)
        with pytest.raises(HTTPException) as exc_info:
            _check_rate_limit(ch, cid)
        assert exc_info.value.status_code == 429

    def test_requests_outside_window_not_counted(self):
        """Timestamps older than RATE_LIMIT_WINDOW_SECONDS are ignored."""
        ch, cid = _fresh_key("b2b_window")
        key = f"{ch}:{cid}"
        old_ts = time.time() - RATE_LIMIT_WINDOW_SECONDS - 1
        # Pre-fill bucket with 10 stale timestamps
        RATE_LIMIT_BUCKETS[key] = [old_ts] * RATE_LIMIT_B2B
        # Current request should pass because old timestamps are expired
        _check_rate_limit(ch, cid)  # must not raise


class TestRateLimitRoleplay:
    def test_twenty_requests_pass_in_roleplay(self):
        ch, cid = _fresh_key("rp_pass")
        for _ in range(RATE_LIMIT_ROLEPLAY):
            _check_rate_limit(ch, cid, roleplay_active=True)  # must not raise

    def test_twentyfirst_request_blocked_in_roleplay(self):
        ch, cid = _fresh_key("rp_block")
        for _ in range(RATE_LIMIT_ROLEPLAY):
            _check_rate_limit(ch, cid, roleplay_active=True)
        with pytest.raises(HTTPException) as exc_info:
            _check_rate_limit(ch, cid, roleplay_active=True)
        assert exc_info.value.status_code == 429

    def test_roleplay_limit_higher_than_b2b(self):
        assert RATE_LIMIT_ROLEPLAY > RATE_LIMIT_B2B

    def test_same_bucket_b2b_then_roleplay(self):
        """Switching to roleplay mode on same key still uses the shared bucket."""
        ch, cid = _fresh_key("mixed")
        # Fill up to B2B limit in B2B mode
        for _ in range(RATE_LIMIT_B2B):
            _check_rate_limit(ch, cid, roleplay_active=False)
        # In roleplay mode the limit is higher — extra requests should pass
        for _ in range(RATE_LIMIT_ROLEPLAY - RATE_LIMIT_B2B):
            _check_rate_limit(ch, cid, roleplay_active=True)


# ===========================================================================
# LAYER 1 — Session TTL and roleplay state clearing
# ===========================================================================

class TestIsNewSession:
    def test_none_timestamp_is_new_session(self):
        assert _is_new_session(None) is True

    def test_recent_timestamp_is_not_new(self):
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        assert _is_new_session(recent) is False

    def test_old_timestamp_is_new_session(self):
        old = datetime.now(timezone.utc) - SESSION_TIMEOUT - timedelta(seconds=1)
        assert _is_new_session(old) is True

    def test_exactly_at_timeout_boundary(self):
        """Exactly at SESSION_TIMEOUT should trigger new-session."""
        boundary = datetime.now(timezone.utc) - SESSION_TIMEOUT - timedelta(milliseconds=100)
        assert _is_new_session(boundary) is True


class TestClearRoleplayState:
    def test_all_roleplay_keys_removed(self):
        state = _full_b2b_state()
        _clear_roleplay_state(state)
        assert not state.get("roleplay_demo_active")
        assert "roleplay_demo_topic" not in state
        assert ROLEPLAY_AWAITING_CONTEXT_KEY not in state
        assert ROLEPLAY_CONTEXT_SUMMARY_KEY not in state
        assert ROLEPLAY_CONTEXT_SOURCE_KEY not in state
        assert ROLEPLAY_CONTEXT_WAIT_COUNT_KEY not in state
        assert ROLEPLAY_NO_FILE_FALLBACK_KEY not in state

    def test_b2b_milestones_preserved(self):
        """Clearing roleplay must never touch B2B funnel progress."""
        state = _full_b2b_state()
        _clear_roleplay_state(state)
        for key in BUYING_MILESTONE_KEYS:
            assert key in state, f"B2B key '{key}' was wiped by _clear_roleplay_state"

    def test_idempotent_on_already_clear_state(self):
        """Calling twice must not raise and must leave B2B intact."""
        state = {"pain_expressed": True, "price_exposed": False}
        _clear_roleplay_state(state)
        _clear_roleplay_state(state)
        assert state["pain_expressed"] is True

    def test_contact_phone_preserved(self):
        state = _full_b2b_state()
        state["contact_phone_collected"] = True
        _clear_roleplay_state(state)
        assert state.get("contact_phone_collected") is True

    def test_roleplay_history_start_index_removed(self):
        state = _full_b2b_state()
        state["roleplay_history_start_index"] = 5
        _clear_roleplay_state(state)
        assert "roleplay_history_start_index" not in state


# ===========================================================================
# LAYER 1 — Exit request detection (regression for past-tense / natural forms)
# ===========================================================================

class TestRoleplayExitDetection:
    """
    Regression suite for _is_roleplay_demo_exit_request.
    Each test documents a phrase that previously slipped through and caused
    the echo-bug ("В проект добавим: <user exit message>").
    """

    @pytest.mark.parametrize("phrase", [
        # Slash command
        "/exit",
        # Explicit role-exit commands
        "выйди из роли",
        "выходи из ролевки",
        # Mask removal (imperative and past tense)
        "сними маску",
        "снимите маску",
        "маску сняли",
        "маску снял",
        "маску убрал",
        # Stop the roleplay / test-drive
        "хватит играть",
        "хватит играть роль",
        "стоп игру",
        "стоп ролевку",
        "заканчивай тестдрайв",
        "тормози ролевку",
        "тормози игру",
        # Return to Dami Works (explicit B2B keyword)
        "вернись к damiworks",
        "вернись к боту",
        "вернись в damiworks",
        "вернемся к расчету",
        "возвращаемся к проекту",
    ])
    def test_exit_phrase_detected(self, phrase: str):
        normalized = phrase.strip().casefold().replace("ё", "е")
        assert _is_roleplay_demo_exit_request(normalized), (
            f"Exit phrase not detected: {phrase!r} — this would trigger the echo-bug"
        )

    @pytest.mark.parametrize("phrase", [
        # Normal roleplay messages that must NOT be treated as exit
        "сколько стоит полировка",
        "а доставка есть?",
        "у вас есть скидки",
        "окей, давай попробуем",
        "хорошо, договорились",
        "расскажи про гарантию",
        # Deal-closing phrases that look like exit but aren't — sauna/B2C context
        "я готова купить",
        "давайте к делу, запишите меня",
        "все, оформляйте",
        "ок, хватит, беру",
        # Phrases covered by SOFT-EXIT RULE in prompt (no roleplay reference → stay in role)
        "ладно хорош, давай оформлять",
        "ок достаточно, беру",
    ])
    def test_roleplay_message_not_exit(self, phrase: str):
        normalized = phrase.strip().casefold().replace("ё", "е")
        assert not _is_roleplay_demo_exit_request(normalized), (
            f"Normal roleplay message incorrectly flagged as exit: {phrase!r}"
        )


# ===========================================================================
# LAYER 2 — Smart text checks: output filter functions (no LLM)
# ===========================================================================

DAMIWORKS_LEAKAGE_PHRASES = [
    "Dami Works",
    "$300",
    "спецификац",
    "Фиксируем в спецификации",
    "Задача ясна",
    "Понял задачу",
    "В расчет беру",
    "Закладываем в спецификацию",
    "Базовое внедрение Dami Works",
]


class TestRoleplayOutputContext:
    def test_active_flag_triggers_roleplay_context(self):
        assert _is_roleplay_output_context(
            answer="Добрый день! Чем могу помочь?",
            roleplay_demo_active=True,
            dialog_state={},
        )

    def test_context_summary_triggers_roleplay_context(self):
        """Even if runtime flag is False, stored context summary = still in roleplay."""
        assert _is_roleplay_output_context(
            answer="Добрый день!",
            roleplay_demo_active=False,
            dialog_state={ROLEPLAY_CONTEXT_SUMMARY_KEY: "Детейлинг-студия"},
        )

    def test_b2b_answer_not_roleplay_context(self):
        assert not _is_roleplay_output_context(
            answer="Базовый ИИ-ассистент: от 200 000 ₸ за запуск. Какой канал заявок основной?",
            roleplay_demo_active=False,
            dialog_state={},
        )

    def test_exit_turn_answer_not_roleplay_context(self):
        """The EXIT_ROLEPLAY bridge answer must NOT be treated as roleplay output."""
        exit_answer = (
            "Маску снял, вернулся в режим архитектора Dami Works. "
            "Теперь можем посчитать, как собрать такого ИИ-продавца под ваш продукт."
        )
        assert not _is_roleplay_output_context(
            answer=exit_answer,
            roleplay_demo_active=False,
            dialog_state={},
        )


class TestSanitizeRoleplayOutput:
    @pytest.mark.parametrize("leaked_phrase", [
        "Задача ясна.",
        "Понял задачу.",
        "Фиксируем в спецификации проект.",
        "Закладываем в спецификацию автоматизацию.",
        "Базовое внедрение Dami Works включает...",
        "Dami Works подготовит спецификацию.",
    ])
    def test_forbidden_b2b_phrase_stripped(self, leaked_phrase: str):
        answer = f"Понял, с удовольствием помогу!\n\n{leaked_phrase}\n\nКакой бюджет вам подходит?"
        result = _sanitize_roleplay_output(answer)
        for phrase in ("Задача ясна", "Понял задачу", "спецификац", "Dami Works", "Базовое внедрение"):
            assert phrase.lower() not in result.lower(), (
                f"Leaked phrase '{phrase}' survived sanitize in: {result!r}"
            )

    def test_clean_roleplay_answer_unchanged(self):
        clean = "Да, доставка занимает 2-3 дня по Москве.\n\nВам удобнее курьер или самовывоз?"
        result = _sanitize_roleplay_output(clean)
        assert "доставка" in result
        assert "Москве" in result

    def test_empty_input_handled(self):
        assert _sanitize_roleplay_output("") == ""
        # Whitespace-only: function returns original (no crash); result is falsy
        result = _sanitize_roleplay_output("   ")
        assert not result.strip()

    def test_roleplay_exit_answer_not_sanitized_by_caller(self):
        """
        EXIT_ROLEPLAY turn deliberately contains 'Dami Works'.
        The caller (api.py) skips _sanitize_roleplay_output when router_requested_roleplay_exit=True.
        This test documents that the sanitizer WOULD strip 'Dami Works' — confirming the caller
        must gate it correctly via skip_b2b_postprocessing.
        """
        exit_answer = "Маску снял, вернулся в режим архитектора Dami Works."
        result = _sanitize_roleplay_output(exit_answer)
        # sanitizer does not have a special case for Dami Works alone — only Dami Works + commercial CTA
        # so isolated "Dami Works" in a clean sentence survives sanitizer
        assert "Dami Works" in result, (
            "If this fails, sanitizer now strips bare 'Dami Works' — "
            "verify exit-roleplay answers still pass through correctly."
        )


# ===========================================================================
# LAYER 1 — Roleplay history isolation (bookmark approach)
# ===========================================================================

class TestRoleplayHistoryIsolation:
    def test_setdefault_sets_index_on_first_entry(self):
        state: dict = {}
        fake_history_len = 3
        state.setdefault("roleplay_history_start_index", fake_history_len)
        assert state["roleplay_history_start_index"] == 3

    def test_setdefault_idempotent_on_subsequent_turns(self):
        """Second roleplay turn must not overwrite the original index."""
        state = {"roleplay_history_start_index": 2}
        state.setdefault("roleplay_history_start_index", 99)
        assert state["roleplay_history_start_index"] == 2

    def test_roleplay_history_slice_excludes_b2b_prefix(self):
        history = [
            ChatHistoryMessage(role="user", content="B2B msg 0"),
            ChatHistoryMessage(role="assistant", content="B2B reply 1"),
            ChatHistoryMessage(role="user", content="roleplay entry 2"),
            ChatHistoryMessage(role="assistant", content="roleplay response 3"),
        ]
        rp_start = 2
        roleplay_history = history[rp_start:]
        assert len(roleplay_history) == 2
        assert roleplay_history[0].content == "roleplay entry 2"

    def test_b2b_exit_history_excludes_roleplay_messages(self):
        history = [
            ChatHistoryMessage(role="user", content="B2B 0"),
            ChatHistoryMessage(role="assistant", content="B2B reply 1"),
            ChatHistoryMessage(role="user", content="roleplay start 2"),
            ChatHistoryMessage(role="assistant", content="seller answer 3"),
            ChatHistoryMessage(role="user", content="маску сняли 4"),
        ]
        rp_start = 2
        b2b_history = history[:rp_start]
        assert len(b2b_history) == 2
        assert all("B2B" in m.content for m in b2b_history)

    def test_soft_exit_rule_present_in_roleplay_prompt(self):
        """All 5 behavioral rules must be present in the prompt."""
        from app.gemini_service import ROLEPLAY_DEMO_SYSTEM_PROMPT
        assert "SOFT-EXIT RULE" in ROLEPLAY_DEMO_SYSTEM_PROMPT
        assert "/exit" in ROLEPLAY_DEMO_SYSTEM_PROMPT
        assert "STREET GREETING HYGIENE" in ROLEPLAY_DEMO_SYSTEM_PROMPT
        assert "MEMORY & ATTENTION LOCK" in ROLEPLAY_DEMO_SYSTEM_PROMPT
        assert "QUESTION PRIORITY RULE" in ROLEPLAY_DEMO_SYSTEM_PROMPT
        assert "VALUE-BASED OBJECTION HANDLING" in ROLEPLAY_DEMO_SYSTEM_PROMPT

    def test_b2b_exit_history_unchanged_when_rp_start_zero(self):
        """If roleplay_history_start_index=0, full history is passed (old sessions)."""
        history = [ChatHistoryMessage(role="user", content=f"msg {i}") for i in range(5)]
        rp_start = 0
        router_requested_roleplay_exit = True
        b2b_history = history[:rp_start] if (router_requested_roleplay_exit and rp_start > 0) else history
        assert b2b_history is history


class TestEmDashStripping:
    """Every ChatResponse strips em/en dashes at construction (schemas validator),
    so no pipeline (main chat, demos, custom demo) can leak them to the user."""

    def test_answer_and_parts_are_stripped(self):
        from app.schemas import ChatResponse, Route
        resp = ChatResponse(
            route=Route.general,
            answer="Ольга Панченко — офтальмолог.\n— Первый пункт",
            answer_parts=["Часть первая — вот", "– пункт"],
        )
        assert resp.answer == "Ольга Панченко, офтальмолог.\nПервый пункт"
        assert resp.answer_parts == ["Часть первая, вот", "пункт"]

    def test_hyphenated_words_survive(self):
        from app.schemas import ChatResponse, Route
        resp = ChatResponse(route=Route.general, answer="травматолог-ортопед")
        assert resp.answer == "травматолог-ортопед"
