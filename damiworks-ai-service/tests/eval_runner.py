"""Automated eval runner for Adaptive Sales Intelligence.

Black-box harness: drives multi-turn Telegram-like conversations through the real
POST /api/v1/chat pipeline (mode -> ROI -> commercial policy -> prompt -> Gemini),
captures the bot's answer + response metadata, applies deterministic checks, and
emits a PASS / WATCH / FAIL report.

This is eval-only code. It does not touch production behaviour, prompts, filters,
ROI or commercial logic — it only calls the existing endpoint and inspects results.

Run from damiworks-ai-service/ (needs a populated .env with GEMINI_API_KEY + SUPABASE_*):

    python -m tests.eval_runner --cases tests/eval_cases --out eval_reports/latest.md
    python -m tests.eval_runner --cases tests/eval_cases/core_25.yaml --case 02_cold_price_first
    python -m tests.eval_runner --cases tests/eval_cases --fail-fast
    python -m tests.eval_runner --cases tests/eval_cases --update-golden
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:  # load .env so app settings resolve when run standalone
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass

# Status ordering for aggregation: ERROR > FAIL > WATCH > PASS/SKIP.
# ERROR is a transient infra/generation failure (kept separate from content FAILs so the
# report stays trustworthy and reproducible).
PASS, WATCH, FAIL, SKIP, ERROR = "PASS", "WATCH", "FAIL", "SKIP", "ERROR"
_RANK = {PASS: 0, SKIP: 0, WATCH: 1, FAIL: 2, ERROR: 3}

# User-facing fallback string the backend returns when generation errors. If it appears
# with EMPTY intelligence metadata, the turn errored server-side (treated as ERROR/retry).
# If it appears WITH populated metadata, it genuinely leaked (caught by forbidden_phrases).
_FALLBACK_MARKERS = ("ИИ сейчас не ответил", "Подробная причина записана в логах")

# Fallback globals if no globals: block is found in the case files. The YAML is the
# source of truth; these only exist so the runner still works without globals.yaml.
_FALLBACK_GLOBALS: dict[str, Any] = {
    "forbidden_phrases_all": [
        "ИИ сейчас не ответил",
        "Подробная причина записана в логах",
        "your-portfolio.dev",
        "В проект добавим:",
        "[РЕЖИМ",
        "[КОММЕРЧЕСКАЯ ПОЛИТИКА",
        "shadow_",
        "conversation_mode",
        "predicted_route",
        "text_response",
        "system prompt",
    ],
    "default_max_questions_per_answer": 2,
    "default_max_total_questions": 6,
}

# Structural prompt/scaffolding leakage markers (always FAIL).
_LEAK_MARKERS = (
    "system prompt",
    "системный промпт",
    "[режим",
    "[коммерческая политика",
    "predicted_route",
    "text_response",
    '"contact_phone"',
    "```json",
    "shadow_conversation_mode",
)
# ROI claims that are never allowed regardless of computability.
_ROI_GUARANTEE = ("вы точно теряете", "вы гарантированно теряете")
# Money/ROI number pattern used only to WATCH when ROI cannot be shown.
_ROI_NUMBER = re.compile(
    r"(окуп\w*\s*(за|через)?\s*\d)|(сэконом\w*\s*\d+\s*(тыс|руб|тенге|₽))|(\d+\s*%[^а-я]*окуп)",
    re.IGNORECASE,
)
_ENTERPRISE_VOCAB = ("маржинальн", "воронк", "аудит", "конверси", "юнит-эконом", "unit-эконом")
_PORTFOLIO_PIVOT = ("портфолио", "наши кейс", "примеры наших работ", "покажу примеры работ")
_CONTACT_REQUEST = ("ваш телефон", "оставьте контакт", "номер телефона", "как с вами связаться", "оставьте номер")
_HARD_CLOSE = ("оформить заказ", "вот ссылка на оплату", "реквизиты для оплаты", "перейдите к оплате")


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str = ""


@dataclass
class CaseResult:
    case_id: str
    title: str
    status: str = PASS
    final_mode: str | None = None
    checks: list[CheckResult] = field(default_factory=list)
    transcript: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


# --------------------------------------------------------------------------- loading


def load_cases(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load a single YAML file or every *.yaml in a directory.

    Returns (globals, cases). The first globals: block found wins; otherwise the
    built-in fallback is used.
    """
    files = sorted(path.glob("*.yaml")) if path.is_dir() else [path]
    if not files:
        raise SystemExit(f"No YAML case files found at {path}")

    merged_globals: dict[str, Any] | None = None
    cases: list[dict[str, Any]] = []
    for fp in files:
        data = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
        if isinstance(data, dict):
            if merged_globals is None and isinstance(data.get("globals"), dict):
                merged_globals = data["globals"]
            file_cases = data.get("cases", [])
        elif isinstance(data, list):
            file_cases = data
        else:
            file_cases = []
        cases.extend(c for c in file_cases if isinstance(c, dict) and c.get("id"))

    return (merged_globals or dict(_FALLBACK_GLOBALS)), cases


# --------------------------------------------------------------------------- helpers


def _meta(turn: dict[str, Any], *keys: str, default: Any = None) -> Any:
    node: Any = turn.get("metadata") or {}
    for k in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(k)
    return default if node is None else node


def _count_questions(text: str) -> int:
    return text.count("?")


def _contains_any(text: str, needles) -> str | None:
    low = text.lower()
    for n in needles:
        if n.lower() in low:
            return n
    return None


def _severity(expected: dict[str, Any], key: str, default: str) -> str:
    val = str(expected.get(key, default)).upper()
    return FAIL if val == FAIL else WATCH


# --------------------------------------------------------------------------- checks


def _is_generation_error(turn: dict[str, Any]) -> bool:
    """True when a turn is a server-side generation fallback (empty metadata)."""
    ans = turn.get("answer", "")
    has_marker = any(m in ans for m in _FALLBACK_MARKERS)
    mode = _meta(turn, "intelligence_shadow", "shadow_conversation_mode")
    return has_marker and not mode


def run_checks(case: dict[str, Any], transcript: list[dict[str, Any]], gconf: dict[str, Any]) -> list[CheckResult]:
    exp = case.get("expected") or {}

    # Short-circuit: a transient generation fallback is an infra ERROR, not a content
    # result. Running content checks on a fallback answer would be misleading noise.
    err_turns = [i + 1 for i, t in enumerate(transcript) if _is_generation_error(t)]
    if err_turns:
        return [CheckResult("generation_error", ERROR, f"backend fallback on turn(s) {err_turns} (likely transient LLM error; metadata empty)")]

    answers = [t.get("answer", "") for t in transcript]
    joined = "\n".join(answers).lower()
    results: list[CheckResult] = []

    # 1. forbidden phrases (global + per-case) — always FAIL
    forbidden = list(gconf.get("forbidden_phrases_all", [])) + list(exp.get("must_not_include", []))
    hit = None
    for ans in answers:
        hit = _contains_any(ans, forbidden)
        if hit:
            break
    results.append(CheckResult("forbidden_phrases", FAIL if hit else PASS, f"matched: {hit!r}" if hit else ""))

    # 2. required phrases — WATCH by default, FAIL when required_phrases_severity: FAIL
    req_sev = _severity(exp, "required_phrases_severity", WATCH)
    missing: list[str] = []
    any_list = exp.get("must_include_any") or []
    all_list = exp.get("must_include_all") or []
    if any_list and not any(p.lower() in joined for p in any_list):
        missing.append(f"none of must_include_any present: {any_list}")
    for p in all_list:
        if p.lower() not in joined:
            missing.append(f"missing required: {p!r}")
    if any_list or all_list:
        results.append(
            CheckResult("required_phrases", req_sev if missing else PASS, "; ".join(missing))
        )

    # 3. question count — always FAIL
    per = int(exp.get("max_questions_per_answer", gconf.get("default_max_questions_per_answer", 2)))
    total_cap = int(exp.get("max_total_questions", gconf.get("default_max_total_questions", 6)))
    per_violations = [f"turn {i+1}: {_count_questions(a)}>{per}" for i, a in enumerate(answers) if _count_questions(a) > per]
    total_q = sum(_count_questions(a) for a in answers)
    detail = "; ".join(per_violations)
    if total_q > total_cap:
        detail = (detail + "; " if detail else "") + f"total {total_q}>{total_cap}"
    results.append(CheckResult("question_count", FAIL if (per_violations or total_q > total_cap) else PASS, detail))

    # 4. price safety — checkout-card on a bare price request is FAIL; hard-close wording is WATCH
    if exp.get("price_safe", True):
        card_fail = None
        close_wording = None
        applicable = False
        for i, t in enumerate(transcript):
            price = bool(_meta(t, "commercial_policy", "price_intent_detected"))
            close = bool(_meta(t, "commercial_policy", "close_intent_detected"))
            if price and not close:
                applicable = True
                if t.get("checkout") or _meta(t, "commercial_policy", "should_show_checkout_card"):
                    card_fail = f"turn {i+1}: checkout card on price request"
                if _contains_any(t.get("answer", ""), _HARD_CLOSE):
                    close_wording = f"turn {i+1}: hard-close wording"
        if not applicable:
            results.append(CheckResult("price_safety", SKIP, "no bare price-intent turn"))
        elif card_fail:
            results.append(CheckResult("price_safety", FAIL, card_fail))
        elif close_wording:
            results.append(CheckResult("price_safety", WATCH, close_wording))
        else:
            results.append(CheckResult("price_safety", PASS))

    # 5. ROI safety — guarantee phrase FAIL; fabricated numbers when ROI not showable WATCH
    if exp.get("roi_safe", True):
        guarantee = _contains_any("\n".join(answers), _ROI_GUARANTEE)
        fabricated = None
        for t in transcript:
            can_show = bool(_meta(t, "roi", "can_show_to_user"))
            if not can_show and _ROI_NUMBER.search(t.get("answer", "")):
                fabricated = "ROI numbers while can_show_to_user is false"
                break
        if guarantee:
            results.append(CheckResult("roi_safety", FAIL, f"guarantee phrase: {guarantee!r}"))
        elif fabricated:
            results.append(CheckResult("roi_safety", WATCH, fabricated))
        else:
            results.append(CheckResult("roi_safety", PASS))

    # 6. prompt leakage — always FAIL
    if exp.get("no_prompt_leakage", True):
        leak = None
        for ans in answers:
            leak = _contains_any(ans, _LEAK_MARKERS)
            if leak:
                break
        results.append(CheckResult("prompt_leakage", FAIL if leak else PASS, f"marker: {leak!r}" if leak else ""))

    # 7. no checkout card — always FAIL when expected absent
    if exp.get("no_checkout_card", True):
        bad = None
        for i, t in enumerate(transcript):
            if t.get("checkout") or t.get("product") or _meta(t, "commercial_policy", "should_show_checkout_card"):
                bad = f"turn {i+1}: checkout card / product shown"
                break
        results.append(CheckResult("no_checkout_card", FAIL if bad else PASS, bad or ""))

    # 8. roleplay isolation — checkout during roleplay FAIL; own-product CTA push WATCH
    if exp.get("roleplay_isolated"):
        active_turns = [
            i for i, t in enumerate(transcript)
            if _meta(t, "roleplay_demo_active") or _meta(t, "intelligence_shadow", "shadow_roleplay_isolation_active")
        ]
        if not active_turns:
            results.append(CheckResult("roleplay_isolation", WATCH, "roleplay never became active"))
        else:
            card = next((i for i in active_turns if transcript[i].get("checkout")), None)
            cta = next((i for i in active_turns if _contains_any(transcript[i].get("answer", ""), _HARD_CLOSE)), None)
            if card is not None:
                results.append(CheckResult("roleplay_isolation", FAIL, f"turn {card+1}: checkout during roleplay"))
            elif cta is not None:
                results.append(CheckResult("roleplay_isolation", WATCH, f"turn {cta+1}: CTA push during roleplay"))
            else:
                results.append(CheckResult("roleplay_isolation", PASS))

    # 9. microbusiness enterprise-pressure — WATCH heuristic
    if exp.get("microbusiness_no_enterprise_pressure"):
        user_text = " ".join(m for t in transcript for m in [t.get("message", "")]).lower()
        offenders: list[str] = []
        for i, t in enumerate(transcript):
            mode = _meta(t, "intelligence_shadow", "shadow_conversation_mode")
            if mode != "microbusiness_helper" and exp.get("expected_mode") != "microbusiness_helper":
                continue
            for vocab in _ENTERPRISE_VOCAB:
                if vocab in t.get("answer", "").lower() and vocab not in user_text:
                    offenders.append(f"turn {i+1}: {vocab!r}")
        results.append(CheckResult("microbusiness_pressure", WATCH if offenders else PASS, "; ".join(offenders)))

    # 10. portfolio false-positive — WATCH heuristic
    if exp.get("portfolio_false_positive_guard"):
        pivot = None
        for i, t in enumerate(transcript):
            hitp = _contains_any(t.get("answer", ""), _PORTFOLIO_PIVOT)
            if hitp:
                pivot = f"turn {i+1}: {hitp!r}"
                break
        results.append(CheckResult("portfolio_false_positive", WATCH if pivot else PASS, pivot or ""))

    # 11. contact re-request after contact already given — WATCH heuristic
    if exp.get("no_contact_re_request"):
        re_ask = None
        for i, t in enumerate(transcript[1:], start=2):  # only later turns
            hitc = _contains_any(t.get("answer", ""), _CONTACT_REQUEST)
            if hitc:
                re_ask = f"turn {i}: {hitc!r}"
                break
        results.append(CheckResult("no_contact_re_request", WATCH if re_ask else PASS, re_ask or ""))

    # 12. expected mode (final turn) — WATCH by default, FAIL when expected_mode_severity: FAIL
    if exp.get("expected_mode") and transcript:
        mode_sev = _severity(exp, "expected_mode_severity", WATCH)
        final_mode = _meta(transcript[-1], "intelligence_shadow", "shadow_conversation_mode")
        ok = final_mode == exp["expected_mode"]
        results.append(
            CheckResult("expected_mode", PASS if ok else mode_sev, "" if ok else f"got {final_mode!r}, want {exp['expected_mode']!r}")
        )

    return results


# --------------------------------------------------------------------------- running


def run_case(client, case: dict[str, Any], gconf: dict[str, Any], run_ts: str, retries: int = 1) -> CaseResult:
    case_id = case["id"]
    chat_id = f"eval_{case_id}_{run_ts}"
    reset = bool(case.get("reset_before", True))
    history: list[dict[str, str]] = []
    transcript: list[dict[str, Any]] = []

    for idx, message in enumerate(case.get("messages", [])):
        payload = {
            "channel": case.get("channel") or gconf.get("default_channel") or "telegram",
            "chat_id": chat_id,
            "instance_id": case.get("instance_id") or gconf.get("default_instance_id") or "eval_harness",
            "message": message,
            "chat_history": list(history),
            "reset_context": reset and idx == 0,
        }
        # Retry a turn that returns a transient generation fallback, to keep the report
        # reproducible under sporadic LLM rate-limits.
        body: dict[str, Any] = {}
        for attempt in range(retries + 1):
            try:
                resp = client.post("/api/v1/chat", json=payload)
            except Exception as exc:  # pragma: no cover - network/runtime failure
                return CaseResult(case_id, case.get("title", case_id), ERROR, transcript=transcript, error=f"request raised: {exc}")
            if resp.status_code != 200:
                return CaseResult(
                    case_id, case.get("title", case_id), ERROR, transcript=transcript,
                    error=f"turn {idx+1} HTTP {resp.status_code}: {resp.text[:400]}",
                )
            body = resp.json()
            is_fallback = any(m in body.get("answer", "") for m in _FALLBACK_MARKERS) and not (
                (body.get("metadata") or {}).get("intelligence_shadow", {}).get("shadow_conversation_mode")
            )
            if not is_fallback or attempt == retries:
                break
            time.sleep(2.5)  # brief backoff before retrying the same turn
        answer = body.get("answer", "")
        transcript.append(
            {
                "message": message,
                "answer": answer,
                "route": body.get("route"),
                "checkout": bool(body.get("checkout")),
                "product": body.get("product"),
                "metadata": body.get("metadata", {}),
            }
        )
        history.append({"role": "user", "content": message})
        if answer:
            history.append({"role": "assistant", "content": answer})

    checks = run_checks(case, transcript, gconf)
    status = PASS
    for c in checks:
        if _RANK[c.status] > _RANK[status]:
            status = c.status
    final_mode = _meta(transcript[-1], "intelligence_shadow", "shadow_conversation_mode") if transcript else None
    return CaseResult(case_id, case.get("title", case_id), status, final_mode, checks, transcript)


# --------------------------------------------------------------------------- reports


def _summary_counts(results: list[CaseResult]) -> dict[str, int]:
    counts = {PASS: 0, WATCH: 0, FAIL: 0, ERROR: 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return counts


def write_json(results: list[CaseResult], path: Path, run_ts: str) -> None:
    payload = {
        "generated_at": run_ts,
        "summary": _summary_counts(results),
        "cases": [
            {
                "id": r.case_id,
                "title": r.title,
                "status": r.status,
                "final_mode": r.final_mode,
                "error": r.error,
                "checks": [{"name": c.name, "status": c.status, "detail": c.detail} for c in r.checks],
                "transcript": r.transcript,
            }
            for r in results
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown(results: list[CaseResult], path: Path, run_ts: str) -> None:
    counts = _summary_counts(results)
    lines: list[str] = []
    lines.append("# Adaptive Sales Intelligence — Eval Report")
    lines.append("")
    lines.append(f"Generated: {run_ts}")
    lines.append("")
    lines.append(f"**Summary:** {len(results)} scenarios — "
                 f"✅ PASS {counts[PASS]} · ⚠️ WATCH {counts[WATCH]} · ❌ FAIL {counts[FAIL]} · 🔁 ERROR {counts[ERROR]}")
    lines.append("")
    lines.append("> ERROR = transient backend generation fallback (LLM rate-limit/error); re-run to confirm. Not a content regression.")
    lines.append("")
    lines.append("| Scenario | Result | Final mode | Failed/Watched checks |")
    lines.append("|---|---|---|---|")
    icon = {PASS: "✅ PASS", WATCH: "⚠️ WATCH", FAIL: "❌ FAIL", ERROR: "🔁 ERROR"}
    for r in results:
        flagged = [f"{c.name}:{c.status}" for c in r.checks if c.status in (FAIL, WATCH, ERROR)]
        note = ", ".join(flagged) if flagged else ("error" if r.error else "—")
        lines.append(f"| {r.case_id} — {r.title} | {icon.get(r.status, r.status)} | {r.final_mode or '—'} | {note} |")
    lines.append("")

    flagged_cases = [r for r in results if r.status in (FAIL, WATCH, ERROR)]
    if flagged_cases:
        lines.append("## Failed / watched check details")
        lines.append("")
        for r in flagged_cases:
            lines.append(f"### {icon.get(r.status, r.status)} — {r.case_id}: {r.title}")
            if r.error:
                lines.append(f"- **error:** {r.error}")
            for c in r.checks:
                if c.status in (FAIL, WATCH, ERROR):
                    lines.append(f"- **{c.name}** → {c.status}: {c.detail}")
            lines.append("")

    failed = [r for r in results if r.status == FAIL]
    if failed:
        lines.append("## Full transcripts for FAILED cases")
        lines.append("")
        for r in failed:
            lines.append(f"### {r.case_id}: {r.title}")
            if r.error:
                lines.append(f"_{r.error}_")
                lines.append("")
            for i, t in enumerate(r.transcript, start=1):
                lines.append(f"**Turn {i} · user:** {t.get('message','')}")
                lines.append("")
                lines.append(f"**bot ({_meta(t, 'intelligence_shadow', 'shadow_conversation_mode') or '?'}):** {t.get('answer','')}")
                lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adaptive Sales Intelligence eval runner")
    parser.add_argument("--cases", required=True, help="YAML file or directory of *.yaml case files")
    parser.add_argument("--out", default="eval_reports/latest.md", help="Markdown report path (JSON written alongside)")
    parser.add_argument("--case", help="Run a single case by id")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first FAIL")
    parser.add_argument("--update-golden", action="store_true", help="Save current transcripts as golden baseline")
    parser.add_argument("--retries", type=int, default=1, help="Retries for a transient generation-fallback turn (default 1)")
    args = parser.parse_args(argv)

    gconf, cases = load_cases(Path(args.cases))
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            raise SystemExit(f"No case with id {args.case!r}")

    # Build the app + TestClient once. Import here so --help works without env/keys.
    from fastapi.testclient import TestClient

    from app.main import create_app

    run_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results: list[CaseResult] = []
    with TestClient(create_app()) as client:
        for i, case in enumerate(cases):
            print(f"[eval] running {case['id']} ...", flush=True)
            result = run_case(client, case, gconf, run_ts, retries=args.retries)
            results.append(result)
            print(f"       -> {result.status}" + (f" ({result.error})" if result.error else ""), flush=True)
            if args.fail_fast and result.status == FAIL:
                print("[eval] --fail-fast: stopping after first FAIL", flush=True)
                break
            if i + 1 < len(cases):
                time.sleep(0.5)  # gentle pacing to avoid LLM rate-limit bursts

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json_path = out_path.with_suffix(".json")
    write_markdown(results, out_path, run_ts)
    write_json(results, json_path, run_ts)

    if args.update_golden:
        golden = Path("tests/eval_cases/golden_transcripts.json")
        golden.write_text(
            json.dumps({r.case_id: r.transcript for r in results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[eval] golden baseline written to {golden}", flush=True)

    counts = _summary_counts(results)
    print(f"\n[eval] DONE — PASS {counts[PASS]} · WATCH {counts[WATCH]} · FAIL {counts[FAIL]} · ERROR {counts[ERROR]}")
    print(f"[eval] reports: {out_path} | {json_path}")
    if counts[FAIL]:
        return 1
    return 2 if counts[ERROR] else 0  # 2 = only transient errors; re-run to confirm


if __name__ == "__main__":
    sys.exit(main())
