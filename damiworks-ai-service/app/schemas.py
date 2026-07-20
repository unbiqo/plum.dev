from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

_RANGE_DASH_RE = re.compile(r"(?<=\d)\s*[—–]\s*(?=\d)")
_EM_DASH_RE = re.compile(r"\s*[—–]\s*")


def strip_em_dash(text: str) -> str:
    """Remove em/en dashes from an AI-facing answer.

    Prompt rules alone do not hold: writers still emit the dash live, so every
    ChatResponse strips it in code (see the validator on ChatResponse). A
    numeric range ("2–3 раза") keeps its meaning as a hyphen ("2-3"); a dash
    between clauses becomes a comma; a leading dash (a list bullet) becomes
    nothing. Hyphens inside words ("травматолог-ортопед") are untouched.
    """
    if not text:
        return text
    lines = []
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped[:1] in ("—", "–"):
            line = line[: len(line) - len(stripped)] + stripped[1:].lstrip()
        line = _RANGE_DASH_RE.sub("-", line)
        lines.append(_EM_DASH_RE.sub(", ", line))
    return "\n".join(lines)


class Route(str, Enum):
    general = "GENERAL"
    rag_required = "RAG_REQUIRED"
    checkout = "CHECKOUT"
    roleplay = "ROLEPLAY"
    exit_roleplay = "EXIT_ROLEPLAY"


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str = Field(..., min_length=1)


class ChatAttachment(BaseModel):
    filename: str | None = None
    mime_type: str = Field(..., min_length=1)
    base64_data: str | None = None
    url: str | None = None


class ChatRequest(BaseModel):
    channel: Literal["telegram", "whatsapp", "instagram", "web_site"]
    chat_id: str = Field(..., min_length=1)
    instance_id: str = Field(..., min_length=1)
    message: str = ""
    chat_history: list[ChatHistoryMessage] = Field(default_factory=list)
    reset_context: bool = False
    message_id: str | None = None
    response_message_id: str | None = None
    locale: str | None = None
    source: str | None = None
    attachments: list[ChatAttachment] = Field(default_factory=list)
    # Frontend signal: a Calendly booking CTA is visible in the UI, so contact
    # asks may present booking a call as the preferred next step.
    calendly_enabled: bool = False


class ProductCard(BaseModel):
    product_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    dosage: str | None = None
    price_tenge: int | None = Field(default=None, ge=0)
    currency: Literal["KZT"] = "KZT"
    image_url: str | None = None


class ChatResponse(BaseModel):
    route: Route
    routes: list[Route] = Field(default_factory=list)
    answer: str
    # Additive: the same answer split into 1-3 short messenger bubbles.
    # ``answer`` always carries the joined text, so older clients (which never
    # read this field) are unaffected.
    answer_parts: list[str] | None = None
    checkout: bool = False
    product_id: str | None = None
    product: ProductCard | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # DamiWorks consultant lead lifecycle (None on non-consultant channels).
    lead_status: Literal["open", "contact_requested", "contact_collected", "closed"] | None = None
    lead_sent: bool = False

    # Em dashes never reach a user: one choke point for every pipeline (main
    # chat, both vertical demos, custom demo) instead of per-writer stripping.
    @field_validator("answer", "answer_parts", mode="after")
    @classmethod
    def _strip_em_dashes(cls, value: str | list[str] | None) -> str | list[str] | None:
        if isinstance(value, list):
            return [strip_em_dash(part) for part in value]
        return strip_em_dash(value) if value else value


class LeadCreateRequest(BaseModel):
    """Frontend → backend signal that the guided intake completed (a lead is
    'created' and may warrant an owner notification)."""
    chat_id: str = Field(..., min_length=1)
    instance_id: str = "damiworks_site"
    locale: str | None = None
    interest_level: Literal["cold", "warm", "hot"] | None = None
    business_type: str | None = None
    channels: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    handoff_target: str | None = None
    volume: str | None = None
    timeline: str | None = None
    package_recommended: str | None = None
    estimated_setup_price: str | None = None
    estimated_monthly_price: str | None = None
    summary: str | None = None
    transcript: list[ChatHistoryMessage] = Field(default_factory=list)


class ContactFormRequest(BaseModel):
    """Footer / contact-section form submission."""
    name: str = Field(..., min_length=1, max_length=200)
    contact: str = Field(..., min_length=1, max_length=200)
    business_type: str | None = None
    message: str | None = None


class QualityFeedbackCreateRequest(BaseModel):
    """Instance-agnostic quality feedback for one assistant message."""

    instance_id: str = Field(..., min_length=1, max_length=200)
    chat_id: str = Field(..., min_length=1, max_length=200)
    message_id: str = Field(..., min_length=1, max_length=200)
    rating: Literal["positive", "negative"] = "negative"
    issue_type: str = Field(default="other", min_length=1, max_length=100)
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    status: Literal["open", "reviewed", "fixed", "ignored", "added_to_evals"] = "open"
    user_message: str | None = None
    assistant_answer: str = Field(..., min_length=1)
    corrected_answer: str | None = None
    comment: str | None = None
    reviewer_note: str | None = None
    transcript_json: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str | None = None
    client_id: str | None = None
    reviewer_id: str | None = None
    source: str | None = "web_chat"
    environment: str | None = None
    tags: list[str] = Field(default_factory=list)


class QualityFeedbackUpdateRequest(BaseModel):
    issue_type: str | None = Field(default=None, min_length=1, max_length=100)
    severity: Literal["low", "medium", "high", "critical"] | None = None
    status: Literal["open", "reviewed", "fixed", "ignored", "added_to_evals"] | None = None
    corrected_answer: str | None = None
    comment: str | None = None
    reviewer_note: str | None = None
    metadata: dict[str, Any] | None = None
    reviewer_id: str | None = None
    tags: list[str] | None = None


class QualityFeedbackListResponse(BaseModel):
    items: list[dict[str, Any]]
    count: int | None = None
