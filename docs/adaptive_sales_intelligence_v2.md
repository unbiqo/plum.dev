# Adaptive Sales Intelligence — Implemented Architecture (Phases 1–9)

> This document describes the **actually implemented** state of the `sales_intelligence`
> layer. `project_specs.md` (v1.2) remains the **target spec / source of truth**; where this
> doc and the spec differ, the spec wins for *intent*, this doc wins for *current code*.

The layer lives in `damiworks-ai-service/app/sales_intelligence/` and is wired into
`damiworks-ai-service/app/api.py`. Master kill-switch: `INTELLIGENCE_SHADOW_ENABLED` (env, default
`true`) — when off, the whole layer is a no-op and legacy behavior is restored.

---

## 1. Current request pipeline (`POST /api/v1/chat`)

```
1.  Typing indicator (fire-and-forget)
2.  Load tenant settings
3.  reset_context → clear_conversation_state (full server-side wipe) if requested
4.  Load logged history + session_metadata
5.  ensure_intelligence_metadata(session_metadata)         # idempotent migration, non-destructive
6.  apply_intelligence_timeouts(...)                       # roleplay 6h / B2B 72h
7.  client_facts (legacy) + dialog_state (legacy) build
8.  M1B legacy roleplay clear (6h) + rate-limit (mode-aware)
9.  roleplay detection + context gate (may early-return)
10. run_intelligence_turn(...)  →  { debug, persist_blocks, roi_result, prev_mode_preserved }
       - signal_analyzer (heuristic, NO LLM) → profile_merger → scoring → strategy_engine
         (conversation_mode, wow_mechanism, next_best_action, bot_guidance, question_budget)
       - roi_engine.build_roi_result (deterministic, NO LLM)
       - roleplay turn → isolated: only roleplay_state persisted, business_profile untouched
11. apply persist_blocks → session_metadata (business_profile / qualification_state /
       conversation_behavior / roi_state ; roleplay turn → roleplay_state only)
12. Deterministic early-exits (greeting / portfolio / explicit Dami Works price override)  # UNCHANGED
13. response_instruction assembled (legacy stage instructions)
14. prompt_composer.compose_safe_mode_instruction(... roi_result ...) → append (enabled modes)
15. question_budget: must_give_value_now → append budget instruction
16. commercial_policy.build_commercial_policy(...) → append price guidance (price turns only)
17. Route assembly → RAG / commercial context load (legacy)
18. LLM generation (single combined route+answer JSON; roleplay path separate)
19. Output filters (see §9): always-on safety + mode-aware sales (gated)
20. update_question_budget_after_answer(...)               # post-answer counter
21. persist session_metadata + log_chat(metadata)          # intelligence debug logged here only
22. async memory refresh
```

Steps 5–6, 10–11, 14–16, 20 are the new layer. Everything else is legacy and largely
untouched. The deterministic price override (step 12) early-returns **before** 14–16, so it is
never affected by the new guidance.

---

## 2. Metadata schema (`chat_sessions.metadata`)

Top-level blocks (created by `ensure_intelligence_metadata`, non-destructive):

- `business_profile` — wrapped fields `{value, confidence, source_text, extraction_type,
  last_updated_at, conflict, conflict_notes}` (niche, lead_volume, average_check, conversion,
  margin, operators, crm, channels[], pains[], integrations[], …).
- `qualification_state` — `conversation_mode`, `wow_mechanism`, `scores{8}`, `question_budget`,
  `last_*`, `logging_reasons`.
- `roi_state` — `roi_depth`, `can_show_to_user`, `calculation_confidence`, `missing_fields`,
  `assumptions`, `last_roi_result{scenarios, user_safe_summary}`, `computed_at`.
- `conversation_behavior` — friction/asked_* latched flags.
- `roleplay_state` — `roleplay_demo_*`, `previous_b2b_conversation_mode`, timestamps.
- `migration` — `schema_version`.
- **Legacy (preserved):** `dialog_state` (drives legacy stage machine / checkout) and
  `client_facts` (backward compat; one-way mirrored from `business_profile`).

---

## 3. Enabled conversation modes (prompt behavior active)

`simple_explainer`, `low_fit_nurture`, `microbusiness_helper`, `integration_discovery`,
`light_roi_diagnostic`, `full_roi_audit`.

## 4. Fallback / special modes

`roleplay_demo` — intentionally **legacy fallback** for prompts. It is the *shadow*
classification of explicit roleplay intent; the live simulation is owned by the roleplay state
machine, not the composer.

---

## 5. Roleplay isolation

- `run_intelligence_turn` is a no-op for the B2B profile when roleplay is active: it never
  reads roleplay messages and never writes `business_profile` (only `roleplay_state`).
- `previous_b2b_conversation_mode` preserved on entry; `roleplay_demo` never overwrites the
  persisted B2B `conversation_mode` (so there is always a real mode to return to).
- `_clear_roleplay_state(dialog_state, session_metadata)` clears only roleplay keys + the
  `roleplay_state` block, never the B2B blocks.
- Two-level timeout: `roleplay_state` resets at 6h; B2B blocks reset at 72h (legacy
  `dialog_state`/`client_facts` keep their existing lifetime to avoid generation changes).

---

## 6. ROI Engine (`roi_readiness.py` + `roi_engine.py`)

- Readiness gate → `none | rough_estimate | light_roi | full_roi` + confidence + missing_fields.
- Formulas (Python only, never LLM): `lost_revenue = leads/mo × leakage × conversion × check`;
  `lost_margin = lost_revenue × margin`; `recoverable = lost_margin × recoverability`;
  `monthly_net = recoverable + time_savings − ai_cost`; `payback = setup/net` (net>0);
  `roi% = net/ai_cost×100` (ai_cost>0). Invalid/negative → `None`.
- Scenarios: conservative / realistic / aggressive (vary leakage/recoverability/conversion).
- `can_show_to_user` = `True` only for light(medium)/full(high) confidence. Rough/none hidden.
- Defaults recorded as explicit `assumptions`; safe phrasing only ("грубая прикидка",
  "порядок цифр", "если предположить"); forbidden: "вы точно теряете", "гарантированно".
- No SaaS pricing hardcoded — `ai_monthly_cost`/`setup_cost` come from tenant `config`;
  without them payback/roi% are `None`.

---

## 7. Commercial policy (`commercial_policy.py`)

- `detect_price_intent` vs `detect_close_intent` are distinct.
- Mode-aware price framing: cold=scenarios, micro=time-saving, integration=scope, ROI modes=
  payback-from-ROI (only if `can_show_to_user`, safe, no guarantees) else metric-gap,
  low_fit=no pressure, post-roleplay="такой AI под ваш бизнес", close=proceed via legacy.
- Checkout/card safety: `should_show_checkout_card` is **advisory** (logging) — the real card
  is still owned by the legacy `stage_transition.checkout_intent` path. Card allowed only on
  explicit close intent or existing legacy close state. Bare "сколько стоит?" → no card.
- Guidance is appended on the **generation path only**, never in roleplay, never on the
  deterministic price-override early-return.

---

## 8. Question budget

- `qualification_questions_asked_since_last_value` per `qualification_state.question_budget`.
- **Counts** only main qualification questions (niche/channel/volume/CRM/team/check/conversion/
  margin/pain/integration/budget/decision-maker). **Excludes** confirmations
  ("правильно понимаю?"), roleplay/context-gate, price-scope questions.
- **Resets** to 0 on delivered value (give_value / offer / price_orientation / value markers).
- `must_give_value_now` (budget exhausted) → inject "give value first" instruction + suppress
  the forced sales-initiative filter. Computed, persisted, enforced — but never breaks roleplay
  or the deterministic price override.

---

## 9. Output filter policy (audit)

**Always-on safety filters** (global; only skipped inside roleplay where noted):
`_sanitize_prompt_leakage_answer`, `_checkout_contact_guard_answer`,
`_sanitize_roleplay_output`, `_cleanup_damiworks_cta_from_roleplay_answer`,
`_repair_forbidden_roleplay_gate_answer`, `_repair_completed_function_qualification_answer`,
`_cleanup_contact_cta_after_phone_collected`, `_final_contact_confirmation_answer`,
`_format_messenger_answer`.

**Mode-aware sales filters:**
- `_ensure_sales_initiative_answer` — **gated** (Phase 5 + 9): suppressed when
  `must_give_value_now`, or (without a close context) in soft modes / on price turns /
  `low_fit_nurture`. Preserved whenever a real close context exists (explicit buy intent or
  legacy `close_consented`/contact) so the legacy close flow is intact.
- `_repair_which_option_better_answer`, `_repair_stage_3_price_answer`,
  `_build_acknowledgement_continuation_answer` — naturally gated by their legacy triggers
  (`sales_stage`, specific question shapes), which do not fire in the new safe modes. Left as-is.
- `_remove_forbidden_traffic_question_after_milestone` — removal filter that *helps* the new
  layer (strips a forced traffic question). Left as-is.

**Legacy/dead:** none removed in Phase 9 (nothing proven dead). `_ensure_sales_initiative_answer`
is downgraded (gated), not deleted.

---

## 10. How to add a new conversation_mode safely

1. Add the value to `ConversationMode` (`schemas.py`) and to mode maps in `strategy_engine.py`
   (`_TONE_BY_MODE`, `_AVOID_BY_MODE`, `_ANGLE_BY_MODE`, `_TARGET_FIELD_BY_MODE`,
   `_DEFAULT_NBA_BY_MODE`) + `MODE_QUESTION_LIMITS` (`question_budget.py`) + `_MODE_WOW_FALLBACK`
   / `_ALLOWED` (`wow_router.py`).
2. Add a selection rule in `strategy_engine._select_mode` (keep it shadow-only first).
3. Validate in shadow (logs) before enabling prompts.
4. To enable prompt behavior: add the mode to `prompt_composer.ENABLED_MODES` and an
   instruction (short behavioral constraints; tenant override key `prompt_mode_<mode>`).
5. Add commercial framing in `commercial_policy.build_commercial_policy` if price-relevant.
6. Add tests in a new `tests/test_sales_intelligence_phaseN.py` and an E2E row.

---

## 11. Test suites

- `tests/test_sales_intelligence_shadow.py` — Phase 1 (metadata + shadow).
- `tests/test_sales_intelligence_phase2.py` — persistence + two-level timeout + isolation.
- `tests/test_sales_intelligence_phase3.py` — scoring/strategy/wow (14 client types).
- `tests/test_sales_intelligence_phase4.py` — prompt composer (safe modes).
- `tests/test_sales_intelligence_phase5.py` — question_budget enforcement.
- `tests/test_sales_intelligence_phase6.py` — micro/integration prompt behavior.
- `tests/test_sales_intelligence_phase7.py` — ROI engine + readiness + composer gating.
- `tests/test_sales_intelligence_phase8.py` — commercial policy.
- `tests/test_sales_intelligence_phase9_e2e.py` — end-to-end eval scenarios.
- `tests/test_smoke.py` — legacy safety filters + rate-limit + roleplay helpers.

Run from `damiworks-ai-service/`: `pytest tests/ -q`.
