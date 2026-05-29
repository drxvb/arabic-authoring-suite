---
name: arabic-authoring-suite
description: "Long-form Arabic authoring skill (books, articles, courses, news) with mandatory fact-pack discipline. Per Agent C's v2.6.0 multi-agent review recommendation: naive LLM authoring produces the exact AI-slop the humanizer is designed to clean up; the fix is to corpus-ground authoring from the OUTLINE stage, not the prose stage. This skill REFUSES one-line prompts. Requires: (a) a fact pack (sources file + claims to support), (b) an outline-first generation step, (c) the humanizer running as a gate (not a polish), (d) per-content-type register policies (book ≠ article ≠ course ≠ news). v0.1 scaffold ships the architecture spec + CLI shape + refusal logic. v0.2+ implements the outline→draft→revise loop. RTL/Arabic-first. Uses arabic-corpus-toolkit (calque dictionary + register policies) + arabic-ai-text-humanizer (post-pass humanness gate). Triggers on 'write an Arabic article', 'create a course in Arabic', 'author a book chapter in MSA', 'تأليف مقال', 'إنشاء كورس'. Do NOT use for: prose REWRITING (use arabic-ai-text-humanizer), translation (use arabic-corpus-translator), social-media snippets (under-budgeted; uses long-form discipline), generation without a fact pack (REFUSED)."
---

# arabic-authoring-suite — Long-Form Arabic Authoring with Fact-Pack Discipline

**Status:** **v1.7.0 — STABLE + fact-pack pre-flight validator (3-of-3 A6 convergent gap closed).** `validate_fact_pack(outline, fact_pack_text, content_type, min_coverage_ratio)` ships in `scripts/validate_fact_pack.py` with a structured `FactPackValidationReport` (`.ok`, `.errors[]`, `.warnings[]`, `.section_coverage[]`, `.overall_coverage`, `.ungrounded_claims[]`). Algorithm: tokenize each `outline.sections[*].claims[*]` into content keywords (Arabic + Latin, stopwords filtered, ≥3 chars), check each keyword's presence in fact_pack_text (case-insensitive Latin, exact Arabic), claim grounded if ≥`min_keywords_per_claim=2` of its keywords appear. Per-content-type thresholds: article 0.5, book-chapter 0.7, course-module 0.6, news 0.5. **Now invoked by default** in `generate()` via `validate_fact_pack_first=True` — generates refuses with structured `refusal_reason: "fact_pack_validation_failed"` + per-claim diagnostics BEFORE spending LLM tokens. Bypass with `force_generate=True` (NOT recommended). CLI: `python scripts/validate_fact_pack.py --outline o.json --fact-pack fp.md --content-type book-chapter --json`. 14/14 regression tests pass across 6 fixtures (empty/malformed inputs, full grounding, partial grounding, zero-coverage-section blocking error, content-type threshold enforcement, Arabic + Latin mixed claims). Closes the strongest convergent A6 audit signal: kimi + minimax-M2 + deepseek-v4-pro **ALL THREE** independently flagged this as the missing P0. **v1.6.0 — STABLE + min_consensus filtering on terminology hints.** Closes the convergent A5 roadmap-challenge pick (Codex + Kimi + Minimax all upgraded this to P0; Sonnet aligned). `generate(content_type, outline, fact_pack, min_consensus=1)` filters Asset G terminology hits by `n_independent_agree` (toolkit v1.10.0+ 3-vendor cross-validation tier). Default=1 preserves prior behavior; =2 keeps majority-validated; =3 keeps unanimous. `_find_terminology_hits(text, domain, trace=, min_consensus=)` is the per-call hook; `generate()` threads `min_consensus` through `outline["min_consensus"]` so `_build_section_prompt` picks it up without signature churn. Pairs lacking the field (G.technology, G.news) pass through unchanged. Smoke-verified: business text yields 6 hits at default, narrows to 1 ("board of directors" — the only 3/3 unanimous-consensus business pair) at min_consensus=3. **v1.5.1 — STABLE.** Sonnet A4 killer finding closure: `generate.py:294` now threads `trace=` to `_find_terminology_hits` in the production path (was: only smoke test passed trace, production prompt builder created hits without trace, so emit_trace=True returned an empty influence_trace despite the consumer wiring being correct). One-line fix; verified 3 trace records emitted via production path on the canonical fact pack. **v1.5.0 — STABLE.** Third-audit consensus closure (all 3 evaluators: "adopt G2 and G3 in authoring"). v1.5.0 ships both: (a) `_registry_is_compatible()` helper routes Asset G loader's compat check through toolkit `asset_registry.is_compatible(f"G.{domain}", observed)` with legacy major-version fallback — eliminating the inline `schema_major == "1"` hardcoded check; (b) `_new_authoring_trace()` instantiates `InfluenceTrace` when toolkit v1.7.0+ available; `generate()` accepts `emit_trace=True` kwarg, threads the trace through `_build_section_prompt → _find_terminology_hits` so every Asset G term hint is causally recorded with `asset_version` pulled from the actual asset metadata; result dict includes `influence_trace: [...]`. Verified end-to-end: tech sentence with "artificial intelligence" + "cloud computing" emits 2 trace records each citing G.technology v1.4.0. **v1.4.0 — STABLE.** Sonnet re-audit (77/100, +15 from baseline) flagged this status line as stuck at v1.3.1 while code had reached v1.4.0; this corrects the drift. **v1.4.0** adopted the toolkit's `arabic_normalize` contract (Gap G1 first consumer): `humanizer_gate`'s language-check now routes through `arabic_normalize.arabic_char_ratio()` with ad-hoc fallback when toolkit absent. **v1.3.1** added `outline.terminology_domain` override — `book-chapter`/`course-module` no longer hardcoded to `technology` domain — outline can declare `terminology_domain: "legal"` etc. to escape the default. **v1.3.0** added cross-LLM swarm drafting (`--swarm minimax,gemini`) + language-check bugfix (prevents English drafts from trivially scoring 100). **v1.2.0** added news + book-chapter fixtures + multi-content-type smoke tests. **v1.1.0** wired in humanizer's `score_text()` as primary gate backend (67 AI-tells, replacing v1.0's 6-tell heuristic). **v1.0.1** consumed toolkit Asset G for corpus-grounded terminology hints in section prompts. **v1.0.0 — STABLE.** Full outline→draft→humanizer-gate pipeline working. `scripts/generate.py` reads an approved outline + fact pack, drafts each section via LAN-local LLM proxies (kimi/minimax/codex/gemini — `M:\Main\DevTools\AI\config\llm-proxies.md`), runs a humanness gate (per-content-type threshold), and regenerates failed sections with tightened anti-AI-tell prompts. Smoke-tested on a sample article: 2 sections drafted in 14.9 seconds via minimax-proxy, both passed humanness gate score 100/100 with 0 AI-tells. Eval suite covers system-prompt discipline, humanizer-gate behavior, prompt builder. Per-type system prompts explicitly ban the AI-tell list (من المهم ملاحظة، علاوة على ذلك، تجدر الإشارة، في غاية الأهمية). Refusal logic from v0.1 preserved — empty briefs still refused. v0.1.1 — scaffold + architecture + refusal logic + per-content-type outline JSON Schemas + stdlib validator. The outline→draft→revise loop (with LLM integration and humanizer gate) is deferred to v0.2.

## Why this skill exists

Per Agent C's review of the original v2.6.0 multi-agent design for the humanizer family:

> "Yes, you are about to build a slop generator with a slop cleaner glued on. That's exactly what will happen if you do it naively. An LLM asked to 'write a book chapter in MSA' produces the most archetypal AI-slop in your corpus: mechanical connectors, ring-composition openers, hyper-formal hedges, the whole 16-dimension failure mode. Running the humanizer over it post-hoc masks the surface but not the cognitive structure — because the *outline* the slop came from was also slop."

The escape is to **make authoring corpus-grounded from the outline stage, not the prose stage.** Four disciplines:

1. **Outline must cite real sources** or a user-supplied fact pack. No fact pack = the skill refuses.
2. **Each section is drafted against a register policy *before* the LLM sees it** (structural constraint, not post-filter).
3. **The humanizer runs as a *gate*, not a polish** — if humanness score < threshold, this skill rewrites the *outline node*, not the prose. Drafting again from a better skeleton beats sanding the same bad skeleton.
4. **"Better than the shared data" is achievable only if the authoring step is allowed to refuse** — to say "this brief is too thin, give me sources" — the same way the humanizer refuses already-human text.

## The four content types (each with its own register policy)

| Content type | Source register | Length budget | Fact-pack requirement |
|---|---|---|---|
| **Book chapter** | classical / opinion | 3,000-8,000 words | Bibliography minimum 10 sources; outline 4-8 sections |
| **Article** | news / opinion | 500-2,500 words | Sources minimum 3; outline 2-4 sections |
| **Course module** | technical / opinion | 1,500-4,000 words | Learning objectives + prerequisite list + exercises bank |
| **News piece** | news | 200-800 words | Source documents (press release, primary source) minimum 1; 5W+H |

Each content type has its own:
- Outline schema (`templates/<type>.outline.json`)
- Section-by-section drafting prompt template
- Humanness-gate threshold (book is stricter than news)
- Fact-pack verification rules

## v0.1.1 scope (this release)

- SKILL.md declaring the architecture + four content types + four disciplines
- `references/01-charter.md` with explicit anti-scope (what this skill REFUSES)
- `scripts/author.py` CLI with refusal logic for empty-brief prompts and missing fact packs
- **NEW in v0.1.1:** `templates/{article,book-chapter,course-module,news}.outline.json` — JSON Schema draft-2020-12 schemas for the four content types
- **NEW in v0.1.1:** `scripts/validate_outline.py` — stdlib JSON Schema validator (subset that covers the schemas)
- **NEW in v0.1.1:** `author.py --validate-outline <path>` flag — delegates to the validator
- **NEW in v0.1.1:** `scripts/smoke_test_schemas.py` — release gate (4 positive + 9 negative cases)

## v0.2 plan

- `scripts/author.py` real implementation: outline → per-section draft → humanizer gate → optional regen
- LLM integration (provider-agnostic via env vars, same pattern as translator)
- Adversarial eval: 5 "bad brief" samples that should be refused + 5 "good brief" samples that should produce output

## Dependencies

- **`arabic-corpus-toolkit`** (v0.4+) — register policies + calque dictionary
- **`arabic-ai-text-humanizer`** (v2.7.0+) — humanness-gate scorer (the analyze_deep.py 16-dimension report becomes the regen trigger)
- **`arabic-corpus-translator`** (optional) — for content authored in English that needs Arabic delivery, the translator runs first, then the humanizer gate

## What this skill is NOT (anti-scope)

Per Agent C's discipline — these are the temptations the skill must refuse:

- **Generate from a one-line prompt.** `"Write an article about Vision 2030"` → REFUSED. The skill demands a fact pack.
- **Polish AI-generated prose.** That's the humanizer's job. This skill generates; the humanizer cleans.
- **Translate.** That's the translator's job. This skill consumes a fact pack in either language and produces Arabic output via its own pipeline.
- **Social-media snippets / tweets.** Under-budgeted for the outline-first discipline. Use a different tool.
- **Dialectal Arabic.** MSA-only by design.

## The refusal-first contract

```bash
# This will REFUSE:
python scripts/author.py --type article --topic "Vision 2030"
# Output: "REFUSED: --type article requires --fact-pack <path>. See references/01-charter.md."

# This will REFUSE:
python scripts/author.py --type book-chapter --fact-pack ./brief.md
# Output: "REFUSED: book-chapter fact pack needs >=10 sources; got 0. ..."

# This will proceed:
python scripts/author.py --type article --fact-pack ./brief-with-sources.md \
    --outline-file ./outline.json --output article-ar.md
```

The refusal is **the product**, not the failure mode. Agent C's design depends on it.

## Provenance

Architecture from Agent C's recommendation in `M:\Main\AI\Corpus\humanizer-v2.6-multi-agent-synthesis.md` ("Scope discipline and product architecture" section, "The authoring ≠ humanizing paradox" subsection).
