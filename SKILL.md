---
name: arabic-authoring-suite
description: "Long-form Arabic authoring skill (books, articles, courses, news) with mandatory fact-pack discipline. Per Agent C's v2.6.0 multi-agent review recommendation: naive LLM authoring produces the exact AI-slop the humanizer is designed to clean up; the fix is to corpus-ground authoring from the OUTLINE stage, not the prose stage. This skill REFUSES one-line prompts. Requires: (a) a fact pack (sources file + claims to support), (b) an outline-first generation step, (c) the humanizer running as a gate (not a polish), (d) per-content-type register policies (book ≠ article ≠ course ≠ news). v0.1 scaffold ships the architecture spec + CLI shape + refusal logic. v0.2+ implements the outline→draft→revise loop. RTL/Arabic-first. Uses arabic-corpus-toolkit (calque dictionary + register policies) + arabic-ai-text-humanizer (post-pass humanness gate). Triggers on 'write an Arabic article', 'create a course in Arabic', 'author a book chapter in MSA', 'تأليف مقال', 'إنشاء كورس'. Do NOT use for: prose REWRITING (use arabic-ai-text-humanizer), translation (use arabic-corpus-translator), social-media snippets (under-budgeted; uses long-form discipline), generation without a fact pack (REFUSED)."
---

# arabic-authoring-suite — Long-Form Arabic Authoring with Fact-Pack Discipline

**Status:** v0.1.1 — scaffold + architecture + refusal logic + per-content-type outline JSON Schemas + stdlib validator. The outline→draft→revise loop (with LLM integration and humanizer gate) is deferred to v0.2.

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
