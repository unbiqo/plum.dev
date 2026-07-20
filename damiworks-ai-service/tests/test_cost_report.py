"""Tests for scripts/cost_report.build_report — lead-cost SLO aggregation on a
synthetic llm_call_logs fixture. No Supabase calls."""

from __future__ import annotations

from scripts.cost_report import build_report


def _row(
    conversation_id: str,
    task_type: str,
    cost: float | None,
    latency: int,
    *,
    fallback: bool = False,
    created: str = "2026-07-17T10:00:00+00:00",
) -> dict:
    return {
        "instance_id": "damiworks_site",
        "conversation_id": conversation_id,
        "task_type": task_type,
        "model_profile": task_type,
        "selected_model": "gemini-3.1-flash-lite",
        "provider": "gemini",
        "input_tokens": 500,
        "output_tokens": 120,
        "total_cost_usd": cost,
        "latency_ms": latency,
        "success": True,
        "fallback_used": fallback,
        "created_at": created,
    }


def _fixture() -> list[dict]:
    rows: list[dict] = []
    # 100 leads: 99 cheap ones + 1 over-budget outlier is tested separately.
    for n in range(99):
        conv = f"damiworks_site:lead-{n:03d}"
        rows.extend(
            [
                _row(conv, "router", 0.0002, 400),
                _row(conv, "classifier", 0.0003, 500),
                _row(conv, "rag_writer", 0.004, 3200),
                _row(conv, "sales_writer", 0.003, 2800),
                _row(conv, "insight_extractor", 0.0004, 600),
                _row(conv, "memory_summary", 0.0003, 700),
            ]
        )
    return rows


def test_lead_cost_slo_met_on_typical_distribution() -> None:
    report = build_report(_fixture(), budget=0.15, limit_leads=100)
    slo = report["lead_cost_slo"]
    assert slo["leads_measured"] == 99
    assert slo["slo_met"] is True
    assert slo["leads_over_budget"] == 0
    assert slo["mean_cost_usd"] is not None and slo["mean_cost_usd"] < 0.01


def test_lead_cost_slo_flags_over_budget_lead() -> None:
    rows = _fixture()
    rows.append(_row("damiworks_site:whale", "sales_writer", 0.5, 2000, created="2026-07-17T11:00:00+00:00"))
    report = build_report(rows, budget=0.15, limit_leads=100)
    slo = report["lead_cost_slo"]
    assert slo["leads_measured"] == 100
    assert slo["slo_met"] is False
    assert slo["leads_over_budget"] == 1


def test_writer_latency_slo_computed_from_writer_calls_only() -> None:
    report = build_report(_fixture(), budget=0.15, limit_leads=100)
    lat = report["writer_latency_slo"]
    # 99 leads * 2 writer calls each; router/classifier latencies excluded.
    assert lat["writer_calls_measured"] == 198
    assert lat["slo_met"] is True
    assert lat["p95_latency_ms"] <= 8000


def test_by_feature_aggregation() -> None:
    report = build_report(_fixture(), budget=0.15, limit_leads=100)
    features = report["by_feature"]
    assert set(features) == {
        "router", "classifier", "rag_writer", "sales_writer", "insight_extractor", "memory_summary",
    }
    assert features["rag_writer"]["calls"] == 99
    assert features["rag_writer"]["avg_cost_usd"] is not None
    assert features["router"]["fallback_rate"] == 0.0


def test_unknown_cost_rows_are_excluded_from_slo() -> None:
    rows = [_row("damiworks_site:lead-x", "router", None, 300)]
    report = build_report(rows, budget=0.15, limit_leads=100)
    assert report["lead_cost_slo"]["leads_measured"] == 0
    assert report["lead_cost_slo"]["slo_met"] is False
