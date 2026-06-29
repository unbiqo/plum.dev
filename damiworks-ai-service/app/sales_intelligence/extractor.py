"""LLM structured extractor — STUB (lands in canonical Phase 3, §10).

Phase 1 does NOT call the LLM. Heuristic, no-LLM extraction lives in ``signal_analyzer``.
This module reserves the canonical entry point. When implemented it must use
``gemini-2.5-flash-lite`` with strict JSON schema and MUST NOT run on roleplay turns (§10.3.6).
"""
from __future__ import annotations

from typing import Any


def extract_business_facts(*args: Any, **kwargs: Any) -> dict[str, Any]:
    raise NotImplementedError("LLM extractor is implemented in Phase 3 (see project_specs.md §10).")
