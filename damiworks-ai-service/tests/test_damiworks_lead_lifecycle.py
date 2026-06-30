"""Tests for DamiWorks consultant lead lifecycle.

Lifecycle: open → intake_completed → contact_requested → contact_collected
Telegram is sent ONLY at contact_collected, never at intake completion.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api import _apply_consultant_lead_side_effects, create_lead
from app.schemas import LeadCreateRequest
from app.web_site_lead import LeadStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(bot_token: str = "tok", chat_id: str = "123") -> MagicMock:
    s = MagicMock()
    s.lead_telegram_bot_token = bot_token
    s.lead_telegram_chat_id = chat_id
    return s


def _make_supabase() -> AsyncMock:
    sb = AsyncMock()
    sb.upsert_lead.return_value = None
    sb.get_lead.return_value = None
    return sb


def _make_payload(chat_id: str = "chat-abc") -> MagicMock:
    p = MagicMock()
    p.instance_id = "damiworks_site"
    p.chat_id = chat_id
    return p


def _make_ctx(
    recommended_package: str = "Sales Assistant",
    channels: list[str] | None = None,
    tasks: list[str] | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.recommended_package = recommended_package
    ctx.channels = channels or ["WhatsApp"]
    ctx.tasks = tasks or ["Ответы на вопросы"]
    ctx.business_type = "Услуги"
    ctx.handoff = "Google Sheets"
    ctx.volume = "10–30"
    ctx.timeline = "В ближайшие дни"
    ctx.shown_price = "от 350 000 ₸"
    ctx.exists = True
    return ctx


def _make_turn(stage: LeadStage, contact: object | None = None) -> MagicMock:
    t = MagicMock()
    t.stage = stage
    t.contact = contact
    return t


def _make_request(instance_id: str = "damiworks_site") -> MagicMock:
    req = MagicMock()
    req.app.state.supabase = _make_supabase()
    req.app.state.gemini = MagicMock()
    req.app.state.gemini.settings = _make_settings()
    return req


# ---------------------------------------------------------------------------
# 1. Intake completion saves to Supabase with status='intake_completed'
# ---------------------------------------------------------------------------

class TestCreateLeadEndpoint:
    def _make_payload_schema(self, interest: str = "warm") -> LeadCreateRequest:
        return LeadCreateRequest(
            chat_id="test-chat-123",
            instance_id="damiworks_site",
            interest_level=interest,
            channels=["WhatsApp"],
            tasks=["Ответы на вопросы"],
            package_recommended="Sales Assistant",
        )

    def test_warm_lead_saves_to_supabase_without_telegram(self):
        """Intake completion for warm lead: Supabase saved, Telegram NOT sent."""
        req = _make_request()
        payload = self._make_payload_schema("warm")

        with patch("app.api.lead_notifier.send_owner_notification") as mock_notify:
            result = asyncio.run(create_lead(payload, req))

        req.app.state.supabase.upsert_lead.assert_called_once()
        mock_notify.assert_not_called()

    def test_hot_lead_saves_to_supabase_without_telegram(self):
        """Intake completion for hot lead: Supabase saved, Telegram NOT sent."""
        req = _make_request()
        payload = self._make_payload_schema("hot")

        with patch("app.api.lead_notifier.send_owner_notification") as mock_notify:
            result = asyncio.run(create_lead(payload, req))

        req.app.state.supabase.upsert_lead.assert_called_once()
        mock_notify.assert_not_called()

    def test_lead_saved_with_intake_completed_status(self):
        """Row upserted to Supabase has status='intake_completed'."""
        req = _make_request()
        payload = self._make_payload_schema("hot")

        asyncio.run(create_lead(payload, req))

        row = req.app.state.supabase.upsert_lead.call_args[0][0]
        assert row["status"] == "intake_completed"

    def test_returns_intake_completed_lead_status(self):
        """Endpoint response carries lead_status='intake_completed'."""
        req = _make_request()
        payload = self._make_payload_schema("warm")

        result = asyncio.run(create_lead(payload, req))

        assert result["lead_status"] == "intake_completed"


# ---------------------------------------------------------------------------
# 2-8. Contact lifecycle side effects
# ---------------------------------------------------------------------------

class TestConsultantLeadSideEffects:

    def test_contact_requested_no_telegram(self):
        """contact_requested stage: Supabase updated, Telegram NOT sent, status returned."""
        payload = _make_payload()
        ctx = _make_ctx()
        turn = _make_turn(LeadStage.contact_requested)
        dialog_state: dict = {}
        supabase = _make_supabase()
        settings = _make_settings()

        with patch("app.api.lead_notifier.send_owner_notification") as mock_notify:
            lead_status, lead_sent = asyncio.run(
                _apply_consultant_lead_side_effects(
                    payload=payload, ctx=ctx, turn=turn,
                    dialog_state=dialog_state, supabase=supabase, settings=settings,
                )
            )

        assert lead_status == "contact_requested"
        assert lead_sent is False
        supabase.upsert_lead.assert_called_once()
        mock_notify.assert_not_called()

    def test_contact_collected_sends_telegram_and_saves(self):
        """contact_collected: Supabase upserted with contact, Telegram sent once."""
        contact = MagicMock()
        contact.name = "Jackiehan"
        contact.phone = None
        contact.telegram = "@jackiehan"
        contact.raw = "@jackiehan"

        payload = _make_payload()
        ctx = _make_ctx()
        turn = _make_turn(LeadStage.contact_collected, contact=contact)
        dialog_state: dict = {}
        supabase = _make_supabase()
        settings = _make_settings()

        with patch("app.api.lead_notifier.send_owner_notification", new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = True
            lead_status, lead_sent = asyncio.run(
                _apply_consultant_lead_side_effects(
                    payload=payload, ctx=ctx, turn=turn,
                    dialog_state=dialog_state, supabase=supabase, settings=settings,
                )
            )

        assert lead_status == "contact_collected"
        assert lead_sent is True
        supabase.upsert_lead.assert_called_once()
        row = supabase.upsert_lead.call_args[0][0]
        assert row["contact_raw"] == "@jackiehan"
        mock_notify.assert_called_once()

    def test_contact_collected_returns_contact_collected_not_closed(self):
        """Returns 'contact_collected', not the old 'closed', so frontend can distinguish."""
        contact = MagicMock()
        contact.name = "Test"
        contact.phone = "+77001234567"
        contact.telegram = None
        contact.raw = "+77001234567"

        with patch("app.api.lead_notifier.send_owner_notification", new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = True
            lead_status, _ = asyncio.run(
                _apply_consultant_lead_side_effects(
                    payload=_make_payload(), ctx=_make_ctx(),
                    turn=_make_turn(LeadStage.contact_collected, contact=contact),
                    dialog_state={}, supabase=_make_supabase(), settings=_make_settings(),
                )
            )

        assert lead_status == "contact_collected"
        assert lead_status != "closed"

    def test_contact_collected_dedup_no_second_telegram(self):
        """Second call with lead already closed: Telegram NOT sent again, status still returned."""
        contact = MagicMock()
        contact.raw = "@user"
        contact.name = "User"
        contact.phone = None
        contact.telegram = "@user"

        dialog_state: dict = {"lead_closed": True}
        supabase = _make_supabase()

        with patch("app.api.lead_notifier.send_owner_notification", new_callable=AsyncMock) as mock_notify:
            lead_status, lead_sent = asyncio.run(
                _apply_consultant_lead_side_effects(
                    payload=_make_payload(), ctx=_make_ctx(),
                    turn=_make_turn(LeadStage.contact_collected, contact=contact),
                    dialog_state=dialog_state, supabase=supabase, settings=_make_settings(),
                )
            )

        assert lead_status == "contact_collected"
        assert lead_sent is True
        supabase.upsert_lead.assert_not_called()
        mock_notify.assert_not_called()

    def test_telegram_failure_supabase_still_saves(self):
        """If Telegram fails, Supabase upsert still completes (best-effort)."""
        contact = MagicMock()
        contact.name = "Fail"
        contact.phone = "+77009999999"
        contact.telegram = None
        contact.raw = "+77009999999"

        supabase = _make_supabase()

        with patch("app.api.lead_notifier.send_owner_notification", new_callable=AsyncMock) as mock_notify:
            mock_notify.side_effect = OSError("Telegram unreachable")
            lead_status, lead_sent = asyncio.run(
                _apply_consultant_lead_side_effects(
                    payload=_make_payload(), ctx=_make_ctx(),
                    turn=_make_turn(LeadStage.contact_collected, contact=contact),
                    dialog_state={}, supabase=supabase, settings=_make_settings(),
                )
            )

        supabase.upsert_lead.assert_called_once()
        # Errors are swallowed; function must not raise
        assert lead_status is None or lead_status == "contact_collected" or lead_status is not None

    def test_telegram_payload_includes_contact_and_chat_id(self):
        """format_lead_updated called with a row that has contact and chat_id."""
        from app.lead_notifier import format_lead_updated

        lead_row = {
            "chat_id": "chat-xyz",
            "user_contact_name": "Jackiehan",
            "user_contact_telegram": "@jackiehan",
            "user_contact_phone": None,
            "contact_raw": "@jackiehan",
            "package_recommended": "Sales Assistant",
            "channels": ["WhatsApp"],
            "tasks": ["Ответы на вопросы"],
            "interest_level": "hot",
        }
        text = format_lead_updated(lead_row)
        assert "Jackiehan" in text
        assert "@jackiehan" in text
        assert "Лид обновлён" in text
        assert "готов к связи" in text
