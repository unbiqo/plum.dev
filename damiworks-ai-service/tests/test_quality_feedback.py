from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api import (
    create_quality_feedback,
    get_quality_conversation,
    list_quality_conversations,
    list_quality_feedback,
    update_quality_feedback,
)
from app.schemas import QualityFeedbackCreateRequest, QualityFeedbackUpdateRequest
from app.schemas import Route
from app.supabase_service import SupabaseService


def _make_request(token: str = "") -> MagicMock:
    req = MagicMock()
    req.app.state.supabase = AsyncMock()
    req.app.state.gemini = MagicMock()
    req.app.state.gemini.settings = MagicMock()
    req.app.state.gemini.settings.quality_console_admin_token = token
    return req


def _payload() -> QualityFeedbackCreateRequest:
    return QualityFeedbackCreateRequest(
        instance_id="damiworks_medical_center_demo",
        chat_id="chat-1",
        message_id="msg-1",
        rating="negative",
        issue_type="unsafe_medical_answer",
        severity="high",
        user_message="болит голова",
        assistant_answer="пример ответа",
        transcript_json=[
            {"role": "user", "content": "болит голова", "message_id": "u1"},
            {"role": "assistant", "content": "пример ответа", "message_id": "msg-1"},
        ],
        metadata={"component": "MedicalCenterChat"},
    )


def test_create_quality_feedback_is_instance_message_keyed():
    req = _make_request()
    stored = {"id": "fb-1", "instance_id": "damiworks_medical_center_demo"}
    req.app.state.supabase.create_quality_feedback.return_value = stored

    result = asyncio.run(create_quality_feedback(_payload(), req))

    assert result["ok"] is True
    assert result["item"] == stored
    row = req.app.state.supabase.create_quality_feedback.call_args[0][0]
    assert row["instance_id"] == "damiworks_medical_center_demo"
    assert row["chat_id"] == "chat-1"
    assert row["message_id"] == "msg-1"
    assert row["issue_type"] == "unsafe_medical_answer"
    assert row["metadata"]["component"] == "MedicalCenterChat"


def test_list_quality_feedback_filters_and_allows_when_token_unset():
    req = _make_request(token="")
    req.app.state.supabase.list_quality_feedback.return_value = [{"id": "fb-1"}]

    result = asyncio.run(
        list_quality_feedback(
            request=req,
            instance_id="damiworks_site",
            chat_id="chat-1",
            rating="negative",
            issue_type="wrong_price",
            severity="medium",
            status="open",
            created_from=None,
            created_to=None,
            limit=50,
            x_admin_token=None,
            admin_token=None,
        )
    )

    assert result.count == 1
    req.app.state.supabase.list_quality_feedback.assert_called_once()
    kwargs = req.app.state.supabase.list_quality_feedback.call_args.kwargs
    assert kwargs["instance_id"] == "damiworks_site"
    assert kwargs["chat_id"] == "chat-1"
    assert kwargs["issue_type"] == "wrong_price"
    assert kwargs["limit"] == 50


def test_list_quality_feedback_requires_admin_token_when_configured():
    req = _make_request(token="secret")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            list_quality_feedback(
                request=req,
                instance_id=None,
                chat_id=None,
                rating=None,
                issue_type=None,
                severity=None,
                status=None,
                created_from=None,
                created_to=None,
                limit=100,
                x_admin_token="wrong",
                admin_token=None,
            )
        )

    assert exc.value.status_code == 401


def test_update_quality_feedback_saves_status_and_corrected_answer():
    req = _make_request(token="secret")
    req.app.state.supabase.update_quality_feedback.return_value = {
        "id": "fb-1",
        "status": "fixed",
        "corrected_answer": "исправленный ответ",
    }

    result = asyncio.run(
        update_quality_feedback(
            feedback_id="fb-1",
            payload=QualityFeedbackUpdateRequest(
                status="fixed",
                corrected_answer="исправленный ответ",
            ),
            request=req,
            x_admin_token="secret",
            admin_token=None,
        )
    )

    assert result["ok"] is True
    req.app.state.supabase.update_quality_feedback.assert_called_once_with(
        "fb-1",
        {"status": "fixed", "corrected_answer": "исправленный ответ"},
    )


def test_list_quality_conversations_returns_chats_without_feedback():
    req = _make_request(token="")
    req.app.state.supabase.list_ai_conversations.return_value = [
        {
            "instance_id": "damiworks_site",
            "chat_id": "chat-without-feedback",
            "feedback_count": 0,
        }
    ]

    result = asyncio.run(
        list_quality_conversations(
            request=req,
            instance_id="damiworks_site",
            chat_id=None,
            has_feedback="false",
            lead_status=None,
            date_from=None,
            date_to=None,
            limit=100,
            offset=0,
            x_admin_token=None,
            admin_token=None,
        )
    )

    assert result["count"] == 1
    assert result["items"][0]["chat_id"] == "chat-without-feedback"
    kwargs = req.app.state.supabase.list_ai_conversations.call_args.kwargs
    assert kwargs["has_feedback"] is False


def test_conversation_detail_returns_messages_and_feedback():
    req = _make_request(token="")
    req.app.state.supabase.get_ai_conversation_detail.return_value = {
        "conversation": {"instance_id": "damiworks_site", "chat_id": "chat-1"},
        "messages": [
            {"message_id": "u1", "role": "user", "content": "hi", "feedback": []},
            {
                "message_id": "a1",
                "role": "assistant",
                "content": "hello",
                "feedback": [{"message_id": "a1", "issue_type": "bad_tone"}],
            },
        ],
        "feedback": [{"message_id": "a1", "issue_type": "bad_tone"}],
    }

    result = asyncio.run(
        get_quality_conversation(
            instance_id="damiworks_site",
            chat_id="chat-1",
            request=req,
            x_admin_token=None,
            admin_token=None,
        )
    )

    assert result["conversation"]["chat_id"] == "chat-1"
    assert result["messages"][1]["feedback"][0]["message_id"] == "a1"
    req.app.state.supabase.get_ai_conversation_detail.assert_called_once_with(
        instance_id="damiworks_site",
        chat_id="chat-1",
    )


def test_log_chat_failure_still_attempts_conversation_logging():
    service = object.__new__(SupabaseService)
    service.client = MagicMock()
    service.client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("chat_logs down")
    service._log_ai_conversation_turn_sync = MagicMock()

    service.log_chat_sync(
        channel="web_site",
        chat_id="chat-1",
        instance_id="damiworks_site",
        message="hello",
        ai_response="hi",
        routes=[Route.general],
        user_message_id="u1",
        assistant_message_id="a1",
    )

    service._log_ai_conversation_turn_sync.assert_called_once()
    kwargs = service._log_ai_conversation_turn_sync.call_args.kwargs
    assert kwargs["user_message_id"] == "u1"
    assert kwargs["assistant_message_id"] == "a1"


def test_conversation_migration_has_unique_message_keys():
    sql = Path("sql/ai_conversations.sql").read_text(encoding="utf-8")

    assert "unique (instance_id, chat_id)" in sql
    assert "unique (instance_id, chat_id, message_id)" in sql
