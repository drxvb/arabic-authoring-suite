# 01 — Charter

## Mission

Generate long-form Arabic content (books, articles, courses, news) **only** when the user supplies a fact pack that meets the per-content-type minimum requirements. Refuse otherwise. Wire the humanizer as a regen gate. Treat the outline as the load-bearing artifact, not the prose.

## Scope

**In scope:**

- Article authoring (news + opinion register) from fact pack + sources
- Book-chapter authoring (classical + opinion register) from comprehensive bibliography
- Course-module authoring (technical + opinion) from learning objectives + exercise bank
- News-piece authoring (news register) from primary source (press release, etc.) with 5W+H discipline
- Outline-first workflow with humanizer-gated regen
- Bilingual fact packs (EN sources → AR output, via translator if needed)

**Out of scope:**

- **Translation** — that's `arabic-corpus-translator`
- **Humanization of existing prose** — that's `arabic-ai-text-humanizer`. This skill GENERATES; the humanizer cleans up post-hoc... but only as a gate, not as a polish.
- **Generation without a fact pack** — refused by design. The skill's PRIMARY behavior is refusing one-line prompts.
- **Social media** — tweets, snippets, headlines. The outline-first discipline is over-budgeted for content under ~200 words.
- **Dialectal Arabic** — MSA-only by design (inherits from the humanizer's scope).
- **Literary fiction** — the corpus-grounded discipline is wrong for fiction; use a dedicated literary tool.

## Anti-scope (the four disciplines this skill enforces)

### 1. No one-line prompts

```bash
python scripts/author.py --type article --topic "Vision 2030"
# → REFUSED: --topic alone is insufficient. Provide --fact-pack <path>.
```

The skill's primary public behavior is refusal. This is feature, not bug.

### 2. Per-type fact-pack minimums

| Content type | Sources minimum | Outline minimum | Word budget |
|---|---|---|---|
| Article | 3 | 2-4 sections | 500-2,500 |
| Book chapter | 10 | 4-8 sections | 3,000-8,000 |
| Course module | 5 + learning objectives + exercise bank | 3-6 sections | 1,500-4,000 |
| News piece | 1 primary source + 5W+H coverage | 1-2 sections | 200-800 |

A book-chapter request with 3 sources is refused. An article request with 0 sources is refused.

### 3. Outline-first generation

The skill produces an **outline first**, asks the user (or downstream agent) to approve it, then generates section-by-section against the approved outline. **The outline carries the corpus-grounding**, not the prose. If the outline doesn't cite specific sources, the prose can't either.

### 4. Humanizer as a gate

After each section is drafted, `arabic-ai-text-humanizer` runs `analyze_deep.py` against it. Below a threshold (per content type), the skill **rewrites the outline node** that produced the section — not the prose. This is the most important architectural commitment: prose-sanding doesn't fix bad cognitive structure.

## What problems this skill is *trying* to solve

- **"AI-generated Arabic articles all read the same."** Because they're outline-less. Outline-first + humanizer-gate produces structurally varied output.
- **"My team writes Arabic articles based on English press releases; the translations are calque-ridden."** Translator runs first, this skill structures the result.
- **"Course materials need consistent terminology across 12 modules."** Fact-pack + per-type register policy enforces this.

## What it cannot solve

- **Bad sources in, bad sources out.** If the fact pack has incorrect facts, the skill produces well-structured incorrect output. This is by design — the skill is not a fact-checker.
- **Creative voice.** The skill produces structurally-correct corpus-natural Arabic prose. Literary distinctiveness ("this reads like Mahfouz") requires a different tool.
- **First-person testimony.** Personal narratives don't fit the fact-pack discipline.

## Provenance

Charter from Agent C's "Top 3 things the user is WRONG to want" + "Top 3 things RIGHT to want" sections in the v2.6.0 multi-agent review (`M:\Main\AI\Corpus\humanizer-v2.6-multi-agent-synthesis.md`). The "fact-pack required" + "outline-first" + "humanizer as gate" + "per-type register policy" commitments are direct from Agent C's "authoring ≠ humanizing paradox" section.
