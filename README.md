# arabic-authoring-suite

> Long-form Arabic authoring (books, articles, courses, news) with mandatory fact-pack discipline. The fourth and final sibling in the `arabic-*` skill family.

**Status:** v0.1.1 — scaffold + refusal logic + per-type outline JSON Schemas + stdlib validator. Real generation loop in v0.2.

## Why

Per Agent C's review of the v2.6.0 multi-agent design:

> Naive LLM authoring produces the exact AI-slop the humanizer is designed to clean up. The fix is to corpus-ground authoring from the **outline** stage, not the prose stage. The humanizer runs as a **gate** (rewrite the outline node when it fails), not a polish (sand the same bad skeleton).

Four disciplines this skill enforces:

1. **Fact-pack required.** No one-line prompts. No "write me an article about X." Empty brief = REFUSED.
2. **Outline-first.** Source citations + section structure before any prose generation.
3. **Humanizer as a gate.** Failed humanness → rewrite the outline, not the prose.
4. **Per-content-type register policies.** Book ≠ article ≠ course ≠ news; each gets its own template + threshold.

## Family map (complete)

```
                              ┌─────────────────────────────┐
                              │  arabic-corpus-toolkit       │
                              │  (v0.6 — shared infra)       │
                              └──────────────┬──────────────┘
                                             │ read-only
                  ┌──────────────────────────┼──────────────────────────┐
                  ▼                          ▼                          ▼
   ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
   │ arabic-ai-text-      │  │ arabic-corpus-       │  │ arabic-authoring-    │
   │ humanizer            │  │ translator           │  │ suite                │
   │ (v2.7.0 — live)      │  │ (v0.2.1 — live)      │  │ (v0.1 — this repo)   │
   └──────────────────────┘  └──────────────────────┘  └──────────────────────┘
            ▲                                                     │
            │              gate (not polish)                      │
            └─────────────────────────────────────────────────────┘
```

This is the **complete four-sibling family** that Agent C recommended in the v2.6.0 multi-agent review.

## Refusal-first

The skill refuses by design:

```bash
# REFUSED — no fact pack
python scripts/author.py --type article --topic "Vision 2030"

# REFUSED — fact pack too thin for content type
python scripts/author.py --type book-chapter --fact-pack ./brief.md  # needs >=10 sources

# Accepted
python scripts/author.py --type article \
    --fact-pack ./brief-with-sources.md \
    --output article-ar.md
```

## v0.1.1 adds

```bash
# List the four schemas
python scripts/validate_outline.py --list-schemas

# Validate an outline (resolves type from outline's "type" field)
python scripts/validate_outline.py my-outline.json

# Or via author.py
python scripts/author.py --type article --validate-outline my-outline.json
```

The schemas enforce the corpus-grounding discipline structurally:
- Article sections need >= 1 source ref; book-chapter sections need >= 2
- Course modules need >= 3 exercises with answer keys
- News pieces need explicit `five_w_h` object (the four mandatory Ws as required fields)

## v0.2 plan

- Real outline → draft → revise loop
- LLM integration via `LLM_API_URL` / `LLM_API_KEY` / `LLM_MODEL` env vars
- Humanizer-gate integration (`analyze_deep.py` from arabic-ai-text-humanizer)
- Adversarial eval suite

## License

MIT.
