"""Cost-per-lead telemetry report built from llm_call_logs.

Aggregates LLM spend per conversation (a "lead"), per feature (task_type) and
per provider/model over a date window, and checks the two live SLOs:

- full lead processing cost <= LEAD_COST_BUDGET_USD (default $0.15);
- p95 live answer latency < 8 s on writer calls while the primary provider works.

Usage:

    python scripts/cost_report.py                      # last 7 days
    python scripts/cost_report.py --days 1             # yesterday only
    python scripts/cost_report.py --limit-leads 100    # SLO check on latest 100 leads
    python scripts/cost_report.py --json report.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supabase import create_client  # noqa: E402

load_dotenv()

PAGE_SIZE = 1000
WRITER_TASK_TYPES = {"sales_writer", "rag_writer", "custom_demo_writer", "sales_writer_escalated"}
P95_LATENCY_SLO_MS = 8000


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM cost-per-lead report from llm_call_logs")
    parser.add_argument("--days", type=int, default=7, help="Window size in days (default 7).")
    parser.add_argument("--instance", default="", help="Filter by instance_id.")
    parser.add_argument(
        "--budget",
        type=float,
        default=float(os.getenv("LEAD_COST_BUDGET_USD", "0.15")),
        help="Lead cost budget in USD (default 0.15).",
    )
    parser.add_argument(
        "--limit-leads",
        type=int,
        default=100,
        help="Evaluate the lead-cost SLO on the N most recent leads (default 100).",
    )
    parser.add_argument("--json", default="", help="Optional path to dump the report as JSON.")
    return parser.parse_args()


def _fetch_rows(client, *, date_from: str, instance: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        query = (
            client.table("llm_call_logs")
            .select(
                "instance_id,conversation_id,task_type,model_profile,selected_model,provider,"
                "input_tokens,output_tokens,total_cost_usd,latency_ms,success,fallback_used,created_at"
            )
            .gte("created_at", date_from)
            .order("created_at", desc=False)
            .range(offset, offset + PAGE_SIZE - 1)
        )
        if instance:
            query = query.eq("instance_id", instance)
        page = list(query.execute().data or [])
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((pct / 100) * (len(ordered) - 1))))
    return ordered[index]


def build_report(rows: list[dict], *, budget: float, limit_leads: int) -> dict:
    by_lead: dict[str, dict] = defaultdict(
        lambda: {"cost": 0.0, "known_cost": False, "calls": 0, "features": set(), "latest": ""}
    )
    by_feature: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "cost": 0.0, "known_cost": False, "latencies": [], "fallbacks": 0}
    )
    writer_latencies: list[float] = []

    for row in rows:
        cost = row.get("total_cost_usd")
        latency = row.get("latency_ms") or 0
        task = row.get("task_type") or "unknown"

        lead_key = row.get("conversation_id") or f"{row.get('instance_id')}:unknown"
        lead = by_lead[lead_key]
        lead["calls"] += 1
        lead["features"].add(task)
        if cost is not None:
            lead["cost"] += float(cost)
            lead["known_cost"] = True
        created = str(row.get("created_at") or "")
        if created > lead["latest"]:
            lead["latest"] = created

        feature = by_feature[task]
        feature["calls"] += 1
        feature["latencies"].append(float(latency))
        feature["fallbacks"] += 1 if row.get("fallback_used") else 0
        if cost is not None:
            feature["cost"] += float(cost)
            feature["known_cost"] = True

        if task in WRITER_TASK_TYPES and row.get("success"):
            writer_latencies.append(float(latency))

    # SLO: cost per lead on the most recent N leads with known pricing.
    recent_leads = sorted(by_lead.items(), key=lambda kv: kv[1]["latest"], reverse=True)[:limit_leads]
    lead_costs = [lead["cost"] for _, lead in recent_leads if lead["known_cost"] and lead["calls"] > 0]
    lead_slo = {
        "leads_measured": len(lead_costs),
        "budget_usd": budget,
        "mean_cost_usd": round(statistics.fmean(lead_costs), 6) if lead_costs else None,
        "p95_cost_usd": _percentile(lead_costs, 95),
        "max_cost_usd": max(lead_costs) if lead_costs else None,
        "leads_over_budget": sum(1 for c in lead_costs if c > budget),
        "slo_met": bool(lead_costs) and all(c <= budget for c in lead_costs),
    }

    features = {
        task: {
            "calls": f["calls"],
            "total_cost_usd": round(f["cost"], 6) if f["known_cost"] else None,
            "avg_cost_usd": round(f["cost"] / f["calls"], 8) if f["known_cost"] and f["calls"] else None,
            "avg_latency_ms": round(statistics.fmean(f["latencies"]), 1) if f["latencies"] else None,
            "p95_latency_ms": _percentile(f["latencies"], 95),
            "fallback_rate": round(f["fallbacks"] / f["calls"], 4) if f["calls"] else 0.0,
        }
        for task, f in sorted(by_feature.items())
    }

    latency_slo = {
        "writer_calls_measured": len(writer_latencies),
        "p95_latency_ms": _percentile(writer_latencies, 95),
        "slo_ms": P95_LATENCY_SLO_MS,
        "slo_met": bool(writer_latencies)
        and (_percentile(writer_latencies, 95) or 0) < P95_LATENCY_SLO_MS,
    }

    return {
        "rows": len(rows),
        "leads_total": len(by_lead),
        "lead_cost_slo": lead_slo,
        "writer_latency_slo": latency_slo,
        "by_feature": features,
    }


def _print_report(report: dict, *, date_from: str) -> None:
    print(f"LLM cost report since {date_from}")
    print(f"  llm_call_logs rows: {report['rows']}, leads: {report['leads_total']}")

    slo = report["lead_cost_slo"]
    print(
        f"\nLead cost SLO (latest {slo['leads_measured']} leads, budget ${slo['budget_usd']}): "
        f"{'OK' if slo['slo_met'] else 'VIOLATED'}"
    )
    print(
        f"  mean=${slo['mean_cost_usd']} p95=${slo['p95_cost_usd']} "
        f"max=${slo['max_cost_usd']} over_budget={slo['leads_over_budget']}"
    )

    lat = report["writer_latency_slo"]
    print(
        f"Writer latency SLO (p95 < {lat['slo_ms']}ms): {'OK' if lat['slo_met'] else 'VIOLATED/NO DATA'} "
        f"(p95={lat['p95_latency_ms']}ms over {lat['writer_calls_measured']} calls)"
    )

    print("\nBy feature (task_type):")
    for task, stats in report["by_feature"].items():
        print(
            f"  {task:28s} calls={stats['calls']:<5d} cost={stats['total_cost_usd']} "
            f"avg_lat={stats['avg_latency_ms']}ms p95={stats['p95_latency_ms']}ms "
            f"fallback={stats['fallback_rate']:.1%}"
        )


def main() -> int:
    args = _parse_args()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required", file=sys.stderr)
        return 1

    date_from = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()
    client = create_client(url, key)
    rows = _fetch_rows(client, date_from=date_from, instance=args.instance)
    report = build_report(rows, budget=args.budget, limit_leads=args.limit_leads)
    _print_report(report, date_from=date_from)

    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON report written to {args.json}")

    return 0 if report["lead_cost_slo"]["slo_met"] or not rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
