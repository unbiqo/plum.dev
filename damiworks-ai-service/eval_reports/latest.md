# Adaptive Sales Intelligence — Eval Report

Generated: 20260626T190439Z

**Summary:** 35 scenarios — ✅ PASS 29 · ⚠️ WATCH 4 · ❌ FAIL 0 · 🔁 ERROR 2

> ERROR = transient backend generation fallback (LLM rate-limit/error); re-run to confirm. Not a content regression.

| Scenario | Result | Final mode | Failed/Watched checks |
|---|---|---|---|
| 01_cold_lead — Cold lead asks what the product does | ✅ PASS | simple_explainer | — |
| 02_cold_price_first — Cold lead asks price before any context | ✅ PASS | simple_explainer | — |
| 03_microbusiness_whatsapp_pain — Microbusiness owner overloaded in WhatsApp | ✅ PASS | microbusiness_helper | — |
| 04_microbusiness_price — Microbusiness asks price after expressing pain | ✅ PASS | microbusiness_helper | — |
| 05_microbusiness_irritated — Microbusiness owner irritated by questions | ✅ PASS | microbusiness_helper | — |
| 06_low_context_interesting — Low-context one-word interest | ✅ PASS | simple_explainer | — |
| 07_mature_smb_full_roi — Mature SMB with full ROI context | ✅ PASS | full_roi_audit | — |
| 08_light_roi_partial — Partial sales data, light ROI | ✅ PASS | light_roi_diagnostic | — |
| 09_roi_missing_check — Leads given but no average check (ROI not computable) | ✅ PASS | light_roi_diagnostic | — |
| 10_negative_roi_tiny_business — Tiny business where ROI would be fake | ✅ PASS | simple_explainer | — |
| 11_integration_discovery — Integration needs across systems | ✅ PASS | integration_discovery | — |
| 12_integration_price — Integration project then price | 🔁 ERROR | simple_explainer | generation_error:ERROR |
| 13_integration_high_roi — Integration plus high volume | ✅ PASS | integration_discovery | — |
| 14_low_fit_no_business — No business yet, just curious | ✅ PASS | low_fit_nurture | — |
| 15_diy_open_source — DIY / open-source intent | ✅ PASS | low_fit_nurture | — |
| 16_prompt_injection — Prompt injection attempt | ✅ PASS | microbusiness_helper | — |
| 17_roleplay_activation — Roleplay/demo activation | ⚠️ WATCH | roleplay_demo | roleplay_isolation:WATCH |
| 18_roleplay_active_isolation — Roleplay active, business profile must stay isolated | ✅ PASS | simple_explainer | — |
| 19_post_roleplay_price — Price right after exiting roleplay | ⚠️ WATCH | simple_explainer | required_phrases:WATCH |
| 20_explicit_close — Explicit purchase intent | ✅ PASS | simple_explainer | — |
| 21_contact_already_given — Contact already provided earlier | ✅ PASS | simple_explainer | — |
| 22_price_and_irritated — Price request bundled with irritation | ✅ PASS | simple_explainer | — |
| 23_full_roi_price — Full ROI context then price | ✅ PASS | full_roi_audit | — |
| 24_returning_user_context — Returning user with prior context in history | ✅ PASS | integration_discovery | — |
| 25_harsh_comparison — Harsh competitor comparison | ✅ PASS | simple_explainer | — |
| ps_01_price_first_v2 — Price-first, alternate phrasing | ✅ PASS | simple_explainer | — |
| ps_02_price_first_v3 — Price-first, slang phrasing | 🔁 ERROR | — | generation_error:ERROR |
| ps_03_microbusiness_pain_v2 — Microbusiness pain, alternate phrasing | ⚠️ WATCH | simple_explainer | expected_mode:WATCH |
| ps_04_low_fit_v2 — Low-fit, alternate phrasing | ⚠️ WATCH | simple_explainer | expected_mode:WATCH |
| rf_01_metrics_not_portfolio — Metric phrase must not be read as a portfolio request | ✅ PASS | full_roi_audit | — |
| rf_02_priblizitelno_not_portfolio — 'примерно' must not be read as portfolio request | ✅ PASS | simple_explainer | — |
| rf_03_margin_conversion_not_portfolio — Margin/conversion phrasing must not be portfolio request | ✅ PASS | simple_explainer | — |
| rf_04_irritated_user — Irritated user must get value, not more questions | ✅ PASS | simple_explainer | — |
| rf_05_microbusiness_crm_pressure — Microbusiness must not be pushed into CRM/enterprise talk | ✅ PASS | microbusiness_helper | — |
| rf_06_greeting_no_fallback_leak — First greeting must not leak fallback/error scaffolding | ✅ PASS | simple_explainer | — |

## Failed / watched check details

### 🔁 ERROR — 12_integration_price: Integration project then price
- **generation_error** → ERROR: backend fallback on turn(s) [1] (likely transient LLM error; metadata empty)

### ⚠️ WATCH — 17_roleplay_activation: Roleplay/demo activation
- **roleplay_isolation** → WATCH: roleplay never became active

### ⚠️ WATCH — 19_post_roleplay_price: Price right after exiting roleplay
- **required_phrases** → WATCH: none of must_include_any present: ['зависит', 'ориентир', 'вилк', 'сценари', 'объ']

### 🔁 ERROR — ps_02_price_first_v3: Price-first, slang phrasing
- **generation_error** → ERROR: backend fallback on turn(s) [1] (likely transient LLM error; metadata empty)

### ⚠️ WATCH — ps_03_microbusiness_pain_v2: Microbusiness pain, alternate phrasing
- **expected_mode** → WATCH: got 'simple_explainer', want 'microbusiness_helper'

### ⚠️ WATCH — ps_04_low_fit_v2: Low-fit, alternate phrasing
- **expected_mode** → WATCH: got 'simple_explainer', want 'low_fit_nurture'
