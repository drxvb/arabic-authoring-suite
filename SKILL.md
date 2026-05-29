---
name: arabic-authoring-suite
description: "Long-form Arabic authoring skill (books, articles, courses, news) with mandatory fact-pack discipline. Per Agent C's v2.6.0 multi-agent review recommendation: naive LLM authoring produces the exact AI-slop the humanizer is designed to clean up; the fix is to corpus-ground authoring from the OUTLINE stage, not the prose stage. This skill REFUSES one-line prompts. Requires: (a) a fact pack (sources file + claims to support), (b) an outline-first generation step, (c) the humanizer running as a gate (not a polish), (d) per-content-type register policies (book ≠ article ≠ course ≠ news). v1.8.0 STABLE: full outline→draft→humanizer-gate pipeline. Mandatory fact-pack pre-flight validation (`validate_fact_pack` refuses ungrounded briefs before spending tokens) + BLOCKING humanizer gate (`humanizer_gate_block=True` refuses output when any section fails the humanness threshold after max_regen — the gate-not-polish charter is now structurally enforced) + per-content-type register policies + min_consensus terminology filtering. RTL/Arabic-first. Uses arabic-corpus-toolkit (calque dictionary + register policies) + arabic-ai-text-humanizer (post-pass humanness gate). Triggers on 'write an Arabic article', 'create a course in Arabic', 'author a book chapter in MSA', 'تأليف مقال', 'إنشاء كورس'. Do NOT use for: prose REWRITING (use arabic-ai-text-humanizer), translation (use arabic-corpus-translator), social-media snippets (under-budgeted; uses long-form discipline), generation without a fact pack (REFUSED)."
---

# arabic-authoring-suite — Long-Form Arabic Authoring with Fact-Pack Discipline

**Status:** **v1.8.0 — STABLE.** Full outline→draft→humanizer-gate pipeline with mandatory fact-pack discipline. `validate_fact_pack` refuses ungrounded briefs before spending tokens; `humanizer_gate_block=True` refuses output when any section fails the humanness threshold after `max_regen_per_section` (the gate-not-polish charter is structurally enforced); `min_consensus` filters Asset G terminology; per-content-type register policies (book / article / course / news). Hard deps: arabic-corpus-toolkit (calque dictionary + register policies + `safe_llm_call`) and arabic-ai-text-humanizer (post-pass humanness gate). **Full version history → [`CHANGELOG.md`](CHANGELOG.md).**

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

## What ships in v1.8.0

- **Outline-first generation** — `generate()` drafts each section from an approved outline; one-line prompts are refused.
- **Mandatory fact-pack pre-flight** — `validate_fact_pack()` refuses ungrounded briefs before spending tokens (`refusal_reason: fact_pack_validation_failed`, per-claim coverage diagnostics).
- **Blocking humanizer gate** — `humanizer_gate_block=True` (default) refuses output when any section fails the humanness threshold after `max_regen_per_section` (`refusal_reason: humanizer_gate_failed`, with each failed section's score/threshold/attempts).
- **Per-content-type register policies** — book / article / course / news each carry their own threshold, length budget, and fact-pack rules.
- **`min_consensus` terminology filtering** — restrict Asset G hints to majority/unanimous cross-vendor-validated pairs.
- **G3 influence telemetry** — every Asset G term hint injected into a section prompt is causally recorded.

## Dependencies

- **`arabic-corpus-toolkit`** (≥ v1.13.0) — register policies + calque dictionary + `safe_llm_call` resilience contract.
- **`arabic-ai-text-humanizer`** (≥ v2.17.0) — humanness-gate scorer (the diagnostic becomes the regen trigger).
- **`arabic-corpus-translator`** (optional) — EN source → Arabic delivery before the gate.

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

Architecture from the v2.6.0 multi-agent design review of the humanizer family — Agent C's "Scope discipline and product architecture" recommendation (the "authoring ≠ humanizing paradox": a slop generator with a slop cleaner glued on is still a slop generator unless the *outline* is corpus-grounded).
