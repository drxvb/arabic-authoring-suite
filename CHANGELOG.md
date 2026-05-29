# Changelog

Long-form Arabic authoring with fact-pack discipline. Versions track the SKILL.md status banner; this file
is the auditable per-version history.
Hard dependencies: `arabic-corpus-toolkit` (calque dictionary + register policies + safe_llm_call) and
`arabic-ai-text-humanizer` (post-pass humanness gate).

## v1.8.0 — Humanizer-gate teeth (3-of-4 A7 convergent must-have)
**Released:** 2026-05-29
Closes the "gate-not-polish" trust failure (minimax+gemini+deepseek): sections were appended even after
`max_regen_per_section` exhausted without passing the humanness threshold. Adds `humanizer_gate_block=True`
(default ON): any section still failing the gate triggers structured refusal `{ok:False, refused:True,
refusal_reason:"humanizer_gate_failed", failed_sections:[...]}` listing each section's gate_score/threshold/
regen_attempts. Bypass with `humanizer_gate_block=False`. The charter is now structurally enforced.

## v1.7.0 — Fact-pack pre-flight validator (3-of-3 A6 convergent gap)
**Released:** 2026-05-29
`validate_fact_pack(outline, fact_pack_text, content_type, min_coverage_ratio)` → `FactPackValidationReport`.
Tokenizes each claim into content keywords (Arabic+Latin, stopwords filtered, ≥3 chars); claim grounded if
≥`min_keywords_per_claim=2` appear in the fact pack. Per-type thresholds (article 0.5, book-chapter 0.7,
course-module 0.6, news 0.5). Invoked by default in `generate()` (`validate_fact_pack_first=True`) — refuses
ungrounded briefs BEFORE spending tokens. Bypass `force_generate=True`. 14/14 tests across 6 fixtures.

## v1.6.0 — `min_consensus` filtering on terminology hints
`generate(..., min_consensus=1)` filters Asset G hits by `n_independent_agree` (1/2/3). Threaded via
`outline["min_consensus"]` so `_build_section_prompt` picks it up without signature churn.

## v1.5.1 — A4 killer-finding fix: thread `trace=` to `_find_terminology_hits` in the production path
## v1.5.0 — Adopted G2 `asset_registry` + G3 `influence_telemetry` (`emit_trace=True`)
## v1.4.0 — Adopted G1 `arabic_normalize` (gate language-check via `arabic_char_ratio()`); status-drift fix
## v1.3.1 — `outline.terminology_domain` override (escape hardcoded `technology` default)
## v1.3.0 — Cross-LLM swarm drafting (`--swarm minimax,gemini`) + language-check bugfix
## v1.2.0 — News + book-chapter fixtures + multi-content-type smoke tests
## v1.1.0 — Humanizer `score_text()` as primary gate backend (67 AI-tells, was 6-tell heuristic)
## v1.0.1 — Consume toolkit Asset G for corpus-grounded terminology hints in section prompts

## v1.0.0 — STABLE: full outline→draft→humanizer-gate pipeline
`scripts/generate.py` reads an approved outline + fact pack, drafts each section via LAN-local LLM proxies,
runs a per-content-type humanness gate, regenerates failed sections with tightened anti-AI-tell prompts.
Per-type system prompts ban the AI-tell list. Refusal logic preserved — empty briefs refused.

### Pre-1.0
- **v0.1.1** scaffold + architecture + refusal logic + per-content-type outline JSON Schemas + stdlib validator.
