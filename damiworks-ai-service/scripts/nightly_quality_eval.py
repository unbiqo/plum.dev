"""Weekly offline quality eval.

Takes ALL conversations of the past week (default window: the 7 days ending
yesterday; volume is small, so no sampling), judges each transcript with the
offline JUDGE model (rubric: naturalness, pain_discovery, funnel_progression,
rag_factual_accuracy, guardrail_compliance + verdict + prompt-diff
recommendations), writes rows into eval_runs, and alerts the owner on Telegram
when a rubric mean drops below its threshold.

Runs on the VPS cron inside the app container WEEKLY, e.g. (Mondays 03:00 UTC):

    0 3 * * 1 cd /opt/damiworks && docker compose exec -T api python scripts/nightly_quality_eval.py

Manual runs stay supported (see AGENTS.md — run one after a manual test
session over the demos):

    python scripts/nightly_quality_eval.py                       # past 7 days
    python scripts/nightly_quality_eval.py --date 2026-07-19 --days 1
    python scripts/nightly_quality_eval.py --no-batch --max 50 --dry-run

Batch mode (Gemini Batch API, ~-50% cost) is the default; any batch failure
falls back to sequential judging for the affected conversations.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.gemini_service import GeminiService  # noqa: E402
from app.lead_notifier import send_owner_notification  # noqa: E402
from app.llm_usage import (  # noqa: E402
    begin_llm_usage_context,
    current_llm_calls,
    end_llm_usage_context,
)
from app.quality_eval import (  # noqa: E402
    EVAL_RUBRIC_KEYS,
    JUDGE_SYSTEM_PROMPT,
    build_judge_prompt,
    evaluate_conversation,
    mean_scores,
    parse_eval_result,
)
from app.supabase_service import SupabaseService  # noqa: E402

load_dotenv()

logger = logging.getLogger("nightly_quality_eval")

ALERT_NATURALNESS_MIN = float(os.getenv("EVAL_ALERT_NATURALNESS_MIN", "4.2"))
ALERT_OTHER_MIN = float(os.getenv("EVAL_ALERT_OTHER_MIN", "3.5"))
BATCH_POLL_SECONDS = int(os.getenv("EVAL_BATCH_POLL_SECONDS", "30"))
BATCH_MAX_WAIT_MINUTES = int(os.getenv("EVAL_BATCH_MAX_WAIT_MINUTES", "60"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Weekly quality eval of AI conversations")
    parser.add_argument(
        "--date",
        default=None,
        help="Last day of the window (YYYY-MM-DD, UTC). Default: yesterday.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=int(os.getenv("EVAL_WINDOW_DAYS", "7")),
        help="Window size in days ending on --date (default 7 = weekly run).",
    )
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=float(os.getenv("EVAL_SAMPLE_RATE", "1.0")),
        help="Fraction of conversations to judge (default 1.0 = all of them).",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=int(os.getenv("EVAL_MAX_CONVERSATIONS", "200")),
        help="Hard cap on judged conversations.",
    )
    parser.add_argument(
        "--instance",
        default=os.getenv("EVAL_INSTANCE_ID", ""),
        help="Only evaluate this instance_id (default: all).",
    )
    parser.add_argument(
        "--no-batch",
        action="store_true",
        default=os.getenv("EVAL_USE_BATCH_API", "true").strip().lower() in {"0", "false", "no"},
        help="Disable the Gemini Batch API and judge sequentially.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write eval_runs / send alerts.")
    return parser.parse_args()


def _window(day: date, days: int) -> tuple[str, str]:
    """UTC [start, end) covering ``days`` days that END on ``day`` (inclusive)."""
    end = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(days=1)
    start = end - timedelta(days=max(days, 1))
    return start.isoformat(), end.isoformat()


def _sample_conversations(
    rows: list[dict], sample_rate: float, max_count: int, day: date
) -> list[dict]:
    """Deterministic sample: same day -> same selection (reproducible runs)."""
    rate = min(max(sample_rate, 0.0), 1.0)
    rng = random.Random(day.isoformat())
    chosen = [row for row in rows if rng.random() < rate]
    if not chosen and rows:
        chosen = [rng.choice(rows)]
    return chosen[:max_count]


def _transcript_of(detail: dict) -> list[dict[str, str]]:
    return [
        {"role": str(m.get("role")), "content": str(m.get("content") or "")}
        for m in (detail or {}).get("messages") or []
        if m.get("role") in ("user", "assistant") and str(m.get("content") or "").strip()
    ]


async def _judge_sequential(
    gemini: GeminiService, item: dict
) -> dict | None:
    token = begin_llm_usage_context(
        instance_id=item["instance_id"], chat_id=item.get("chat_id") or "eval"
    )
    try:
        result = await evaluate_conversation(
            gemini,
            transcript=item["transcript"],
            instance_id=item["instance_id"],
        )
        if result is not None:
            calls = current_llm_calls()
            costs = [c.get("total_cost_usd") for c in calls if c.get("total_cost_usd") is not None]
            result["total_cost_usd"] = round(sum(costs), 8) if costs else None
        return result
    finally:
        end_llm_usage_context(token)


async def _judge_batch(gemini: GeminiService, items: list[dict]) -> dict[int, dict]:
    """Judge all items via the Gemini Batch API. Returns {index: result}.

    Raises on any batch-level failure — the caller falls back to sequential.
    """
    from google.genai import types

    client = next(iter(gemini.clients.values()))
    model = gemini.settings.model_profiles.get("quality_eval", ("gemini-3.1-pro",))[0]
    requests = [
        types.GenerateContentRequest(
            model=model,
            contents=build_judge_prompt(
                transcript=item["transcript"], instance_id=item["instance_id"]
            ),
            config=types.GenerateContentConfig(
                system_instruction=JUDGE_SYSTEM_PROMPT,
                temperature=0.1,
                max_output_tokens=700,
                response_mime_type="application/json",
            ),
        )
        for item in items
    ]
    job = client.batches.create(model=model, src=requests)
    logger.info("Batch job created: %s", job.name)

    deadline = time.monotonic() + BATCH_MAX_WAIT_MINUTES * 60
    terminal = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
    while str(job.state) not in terminal:
        if time.monotonic() > deadline:
            raise TimeoutError(f"Batch job {job.name} did not finish in {BATCH_MAX_WAIT_MINUTES}m")
        await asyncio.sleep(BATCH_POLL_SECONDS)
        job = client.batches.get(name=job.name)
    if str(job.state) != "JOB_STATE_SUCCEEDED":
        raise RuntimeError(f"Batch job {job.name} ended in state {job.state}")

    responses = list(getattr(getattr(job, "dest", None), "inlined_responses", None) or [])
    if len(responses) < len(items):
        raise RuntimeError(f"Batch job {job.name} returned {len(responses)}/{len(items)} responses")

    results: dict[int, dict] = {}
    for index, inlined in enumerate(responses):
        text = getattr(getattr(inlined, "response", None), "text", None)
        result = parse_eval_result(text or "")
        if result is not None:
            result["judge_model"] = model
            result["batch_id"] = job.name
            results[index] = result
    return results


def _format_alert(means: dict[str, float], evaluated: int, day: date) -> str:
    lines = [
        f"⚠️ Quality eval degradation — {day.isoformat()}",
        "",
        f"Оценено диалогов: {evaluated}",
    ]
    for key in EVAL_RUBRIC_KEYS:
        if key in means:
            threshold = ALERT_NATURALNESS_MIN if key == "naturalness" else ALERT_OTHER_MIN
            marker = " ⬇️" if means[key] < threshold else ""
            lines.append(f"• {key}: {means[key]:.2f}/5 (порог {threshold}){marker}")
    lines.append("")
    lines.append("См. eval_runs.recommendations для diff к системному промпту.")
    return "\n".join(lines)


async def main() -> int:
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    day = date.fromisoformat(args.date) if args.date else (datetime.now(timezone.utc) - timedelta(days=1)).date()
    date_from, date_to = _window(day, args.days)

    settings = get_settings()
    gemini = GeminiService(settings)
    supabase = SupabaseService(settings)

    rows = await supabase.list_ai_conversations(
        instance_id=args.instance or None,
        date_from=date_from,
        date_to=date_to,
        limit=500,
    )
    logger.info(
        "Conversations in window %s..%s (%dd): %d",
        date_from[:10], day.isoformat(), args.days, len(rows),
    )
    if not rows:
        return 0

    sampled = _sample_conversations(rows, args.sample_rate, args.max, day)
    logger.info("Sampled %d conversations (rate=%.2f)", len(sampled), args.sample_rate)

    items: list[dict] = []
    for row in sampled:
        detail = await supabase.get_ai_conversation_detail(
            instance_id=row["instance_id"], chat_id=row["chat_id"]
        )
        transcript = _transcript_of(detail)
        if len(transcript) >= 2:
            items.append(
                {
                    "instance_id": row["instance_id"],
                    "chat_id": row["chat_id"],
                    "conversation_id": f"{row['instance_id']}:{row['chat_id']}",
                    "transcript": transcript,
                }
            )
    logger.info("With usable transcripts: %d", len(items))
    if not items:
        return 0

    results: dict[int, dict] = {}
    if not args.no_batch:
        try:
            results = await _judge_batch(gemini, items)
            logger.info("Batch judging succeeded for %d/%d", len(results), len(items))
        except Exception:
            logger.exception("Batch judging failed; falling back to sequential")
            results = {}

    for index, item in enumerate(items):
        if index in results:
            continue
        result = await _judge_sequential(gemini, item)
        if result is not None:
            results[index] = result

    evaluated = [results[i] for i in sorted(results)]
    logger.info(
        "Evaluated %d/%d conversations (verdicts: %s)",
        len(evaluated),
        len(items),
        {v: sum(1 for r in evaluated if r["verdict"] == v) for v in ("pass", "warn", "fail")},
    )

    if not args.dry_run:
        for index, result in results.items():
            item = items[index]
            await supabase.insert_eval_run(
                {
                    "run_date": day.isoformat(),
                    "conversation_id": item["conversation_id"],
                    "instance_id": item["instance_id"],
                    "chat_id": item["chat_id"],
                    "scores": result["scores"],
                    "verdict": result["verdict"],
                    "recommendations": result["recommendations"],
                    "judge_model": result.get("judge_model"),
                    "batch_id": result.get("batch_id"),
                    "total_cost_usd": result.get("total_cost_usd"),
                }
            )

    if evaluated:
        means = mean_scores(evaluated)
        logger.info("Mean scores: %s", means)
        degraded = (
            means.get("naturalness", 5.0) < ALERT_NATURALNESS_MIN
            or any(
                means.get(key, 5.0) < ALERT_OTHER_MIN
                for key in EVAL_RUBRIC_KEYS
                if key != "naturalness"
            )
        )
        if degraded and not args.dry_run:
            alert = _format_alert(means, len(evaluated), day)
            await send_owner_notification(
                settings.lead_telegram_bot_token,
                settings.lead_telegram_chat_id,
                alert,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
