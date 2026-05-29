# arabic-authoring-suite

> Long-form Arabic authoring (books, articles, courses, news) with mandatory fact-pack discipline. The fourth and final sibling in the `arabic-*` skill family.

**Status:** **v1.6.0 — stable.** Full outline → draft → humanizer-gate pipeline working, plus cross-LLM swarm drafting, asset_registry compat checks, influence_telemetry tracing in the production path (closes Sonnet A4 killer finding), and `min_consensus` filter on terminology hints (v1.6.0 closes the 4-vendor A5 evaluator convergent pick). Hard dependency on `arabic-corpus-toolkit ≥ v1.5.0` and `arabic-ai-text-humanizer ≥ v2.7.0`.

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
                              │  (v1.12.1 — shared infra)    │
                              └──────────────┬──────────────┘
                                             │ read-only
                  ┌──────────────────────────┼──────────────────────────┐
                  ▼                          ▼                          ▼
   ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
   │ arabic-ai-text-      │  │ arabic-corpus-       │  │ arabic-authoring-    │
   │ humanizer            │  │ translator           │  │ suite                │
   │ (v2.16.0 — live)     │  │ (v1.8.0 — live)      │  │ (v1.6.0 — this repo) │
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

## What v1.x adds (per-release highlights)

- **v1.0.0** — full outline → draft → humanizer-gate pipeline; cross-LLM swarm drafting via `--swarm kimi,minimax`
- **v1.3.x** — `outline.terminology_domain` override (no longer hardcoded to "technology"); language-check bugfix
- **v1.4.0** — G1 arabic_normalize adoption in humanizer-gate language check
- **v1.5.0** — G2 asset_registry adoption + G3 influence_telemetry; `emit_trace=True` returns per-section causal record
- **v1.5.1** — A4 killer-finding fix: production-path `_find_terminology_hits` now actually threads the trace
- **v1.6.0** — **`min_consensus` filter**: pass `generate(..., min_consensus=2)` to restrict Asset G terminology hints to majority-validated only (3-vendor independent consensus tier from toolkit v1.10.0+)

```bash
# List the four schemas
python scripts/validate_outline.py --list-schemas

# Validate an outline (resolves type from outline's "type" field)
python scripts/validate_outline.py my-outline.json

# Author with strict consensus filtering (only majority-validated terminology hints)
python -c "
import generate
result = generate.generate(
    'article', outline_dict, fact_pack_text,
    proxy_name='kimi', emit_trace=True, min_consensus=2)
print(result['influence_trace'])
"
```

Schemas enforce corpus-grounding discipline structurally:
- Article sections need >= 1 source ref; book-chapter sections need >= 2
- Course modules need >= 3 exercises with answer keys
- News pieces need explicit `five_w_h` object (the four mandatory Ws as required fields)

## License

MIT.
