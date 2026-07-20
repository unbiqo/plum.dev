from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


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
