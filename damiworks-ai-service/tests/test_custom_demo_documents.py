from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import api
from app.custom_demo_documents import (
    clear_custom_demo_documents,
    format_custom_demo_document_context,
    get_custom_demo_document,
    retrieve_custom_demo_chunks,
    store_custom_demo_document,
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def setup_function() -> None:
    clear_custom_demo_documents()


def teardown_function() -> None:
    clear_custom_demo_documents()


def test_store_replaces_document_per_chat_and_retrieves_relevant_chunks() -> None:
    store_custom_demo_document(
        chat_id="chat-a",
        filename="old.txt",
        text="Old catalog. Delivery only on Mondays.",
    )
    document = store_custom_demo_document(
        chat_id="chat-a",
        filename="new.txt",
        text=(
            "Premium plan includes Instagram support and WhatsApp handoff.\n\n"
            "Delivery terms: same-day delivery inside Almaty, next-day delivery outside the city.\n\n"
            "Warranty terms: 14 days for unopened products."
        ),
    )

    assert get_custom_demo_document("chat-a") == document
    assert document.filename == "new.txt"

    chunks = retrieve_custom_demo_chunks("chat-a", "What are the delivery terms?")
    assert chunks
    assert any("Delivery terms" in chunk.text for chunk in chunks)

    context = format_custom_demo_document_context("chat-a", "delivery")
    assert "[UPLOADED BUSINESS DOCUMENT CONTEXT]" in context
    assert "new.txt" in context
    assert "Delivery terms" in context


def test_upload_rejects_non_custom_demo_instance() -> None:
    response = _client().post(
        "/api/v1/custom-demo/documents",
        data={"chat_id": "chat-a", "instance_id": api.CONSULTANT_INSTANCE_ID},
        files={"file": ("catalog.txt", b"Catalog text", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["ok"] is False
    assert get_custom_demo_document("chat-a") is None


def test_upload_rejects_unsupported_type_and_oversized_file() -> None:
    client = _client()
    unsupported = client.post(
        "/api/v1/custom-demo/documents",
        data={"chat_id": "chat-a", "instance_id": api.CUSTOM_DEMO_INSTANCE_ID},
        files={"file": ("catalog.docx", b"Catalog text", "application/octet-stream")},
    )
    oversized = client.post(
        "/api/v1/custom-demo/documents",
        data={"chat_id": "chat-a", "instance_id": api.CUSTOM_DEMO_INSTANCE_ID},
        files={"file": ("catalog.txt", b"x" * (api.CUSTOM_DEMO_MAX_FILE_BYTES + 1), "text/plain")},
    )

    assert unsupported.status_code == 400
    assert unsupported.json()["ok"] is False
    assert oversized.status_code == 400
    assert oversized.json()["ok"] is False
    assert get_custom_demo_document("chat-a") is None


def test_upload_stores_text_document_by_chat_id() -> None:
    response = _client().post(
        "/api/v1/custom-demo/documents",
        data={"chat_id": "chat-a", "instance_id": api.CUSTOM_DEMO_INSTANCE_ID},
        files={
            "file": (
                "faq.md",
                "# FAQ\n\nPrices start from 25,000 KZT. Delivery is available daily.",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["filename"] == "faq.md"

    document = get_custom_demo_document("chat-a")
    assert document is not None
    assert document.filename == "faq.md"
    assert "Prices start" in document.chunks[0].text


def test_upload_pdf_uses_extracted_text(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "_extract_pdf_document",
        lambda data: "PDF catalog: orthodontic consultation costs 15,000 KZT.",
    )

    response = _client().post(
        "/api/v1/custom-demo/documents",
        data={"chat_id": "chat-pdf", "instance_id": api.CUSTOM_DEMO_INSTANCE_ID},
        files={"file": ("catalog.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    context = format_custom_demo_document_context("chat-pdf", "orthodontic consultation")
    assert "orthodontic consultation costs 15,000 KZT" in context
