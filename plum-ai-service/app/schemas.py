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
    attachments: list[ChatAttachment] = Field(default_factory=list)


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
    checkout: bool = False
    product_id: str | None = None
    product: ProductCard | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
