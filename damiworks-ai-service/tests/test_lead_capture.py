"""Tests for lead capture: contact form, English School demo, Telegram dedup."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.lead_notifier import (
    format_contact_form_lead,
    format_english_school_lead,
    send_owner_notification,
)
from app.schemas import ContactFormRequest


# ---------------------------------------------------------------------------
# format_contact_form_lead
# ---------------------------------------------------------------------------

class TestFormatContactFormLead:
    def test_includes_name_contact_business(self):
        lead = {
            "user_contact_name": "Дамир",
            "contact_raw": "+7 701 123 45 67",
            "business_type": "Образование",
            "summary": "Хочу автоматизировать запись",
        }
        text = format_contact_form_lead(lead)
        assert "Дамир" in text
        assert "+7 701 123 45 67" in text
        assert "Образование" in text
        assert "автоматизировать" in text
        assert "Заявка с сайта" in text

    def test_missing_fields_show_dash(self):
        lead = {"user_contact_name": "Аня", "contact_raw": "@anya_tg"}
        text = format_contact_form_lead(lead)
        assert "—" in text  # missing business_type / summary show dash


# ---------------------------------------------------------------------------
# format_english_school_lead
# ---------------------------------------------------------------------------

class TestFormatEnglishSchoolLead:
    def test_includes_contact_and_program(self):
        lead = {
            "contact_raw": "@student_tg",
            "_school_state": {
                "program": "ielts",
                "format_preference": "individual",
                "student_age": "17",
                "city": "Алматы",
                "preferred_schedule": "по вечерам",
            },
        }
        text = format_english_school_lead(lead)
        assert "@student_tg" in text
        assert "ielts" in text
        assert "individual" in text
        assert "Алматы" in text
        assert "English School" in text

    def test_empty_state_shows_dashes(self):
        lead = {"contact_raw": "+77001234567"}
        text = format_english_school_lead(lead)
        assert "+77001234567" in text
        assert "—" in text


# ---------------------------------------------------------------------------
# send_owner_notification — skips gracefully when not configured
# ---------------------------------------------------------------------------

class TestSendOwnerNotification:
    def test_skips_when_no_token(self):
        result = asyncio.run(
            send_owner_notification("", "", "hello")
        )
        assert result is False

    def test_skips_when_no_chat_id(self):
        result = asyncio.run(
            send_owner_notification("token123", "", "hello")
        )
        assert result is False

    def test_returns_false_on_network_error(self):
        with patch("app.lead_notifier._send_sync", side_effect=OSError("timeout")):
            result = asyncio.run(
                send_owner_notification("token", "chat123", "hello")
            )
        assert result is False


# ---------------------------------------------------------------------------
# ContactFormRequest schema
# ---------------------------------------------------------------------------

class TestContactFormRequest:
    def test_valid_minimal(self):
        req = ContactFormRequest(name="Алия", contact="+7 700 000 0000")
        assert req.name == "Алия"
        assert req.business_type is None

    def test_valid_full(self):
        req = ContactFormRequest(
            name="Дамир",
            contact="@damir_tg",
            business_type="Образование",
            message="Хочу автоматизировать WhatsApp",
        )
        assert req.message == "Хочу автоматизировать WhatsApp"

    def test_empty_name_rejected(self):
        import pydantic
        with pytest.raises((ValueError, pydantic.ValidationError)):
            ContactFormRequest(name="", contact="@contact")

    def test_empty_contact_rejected(self):
        import pydantic
        with pytest.raises((ValueError, pydantic.ValidationError)):
            ContactFormRequest(name="Алия", contact="")


# ---------------------------------------------------------------------------
# _save_english_school_lead dedup
# ---------------------------------------------------------------------------

class TestSaveEnglishSchoolLeadDedup:
    """Background task should not save/notify twice for the same chat."""

    def _make_payload(self, chat_id: str = "test-chat-123") -> MagicMock:
        payload = MagicMock()
        payload.instance_id = "damiworks_english_school_demo"
        payload.chat_id = chat_id
        return payload

    def _make_response(self, contact: str = "@user_tg") -> MagicMock:
        response = MagicMock()
        response.lead_status = "contact_collected"
        response.metadata = {"state": {"contact": contact, "program": "ielts"}}
        return response

    def _make_supabase(self, existing_contact: str | None = None) -> AsyncMock:
        sb = AsyncMock()
        existing = {"contact_raw": existing_contact} if existing_contact else None
        sb.get_lead.return_value = existing
        sb.upsert_lead.return_value = None
        return sb

    def _make_settings(self) -> MagicMock:
        s = MagicMock()
        s.lead_telegram_bot_token = ""
        s.lead_telegram_chat_id = ""
        return s

    def test_saves_on_first_contact(self):
        from app.api import _save_english_school_lead
        payload = self._make_payload()
        response = self._make_response()
        supabase = self._make_supabase(existing_contact=None)
        settings = self._make_settings()

        asyncio.run(
            _save_english_school_lead(
                payload=payload, response=response,
                supabase=supabase, settings=settings,
            )
        )
        supabase.upsert_lead.assert_called_once()
        call_kwargs = supabase.upsert_lead.call_args[0][0]
        assert call_kwargs["contact_raw"] == "@user_tg"
        assert call_kwargs["source"] == "english_school_demo"
        assert call_kwargs["status"] == "contact_collected"

    def test_skips_if_contact_already_saved(self):
        from app.api import _save_english_school_lead
        payload = self._make_payload()
        response = self._make_response()
        supabase = self._make_supabase(existing_contact="@user_tg")
        settings = self._make_settings()

        asyncio.run(
            _save_english_school_lead(
                payload=payload, response=response,
                supabase=supabase, settings=settings,
            )
        )
        supabase.upsert_lead.assert_not_called()

    def test_skips_when_no_contact_in_state(self):
        from app.api import _save_english_school_lead
        payload = self._make_payload()
        response = MagicMock()
        response.lead_status = "contact_collected"
        response.metadata = {"state": {"contact": "", "program": "ielts"}}
        supabase = self._make_supabase()
        settings = self._make_settings()

        asyncio.run(
            _save_english_school_lead(
                payload=payload, response=response,
                supabase=supabase, settings=settings,
            )
        )
        supabase.upsert_lead.assert_not_called()

    def test_supabase_failure_does_not_raise(self):
        from app.api import _save_english_school_lead
        payload = self._make_payload()
        response = self._make_response()
        supabase = AsyncMock()
        supabase.get_lead.return_value = None
        supabase.upsert_lead.side_effect = RuntimeError("Supabase down")
        settings = self._make_settings()

        # Must not raise
        asyncio.run(
            _save_english_school_lead(
                payload=payload, response=response,
                supabase=supabase, settings=settings,
            )
        )
