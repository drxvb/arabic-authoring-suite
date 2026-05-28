#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_multi_content_type.py — v1.2.0 multi-content-type smoke test.

Runs generate() for article + news + book-chapter content types against their
fixtures. Validates each produces non-empty output that scores well on the
humanizer gate.

Skipped unless ARABIC_AUTHORING_RUN_LLM=1 (LLM-dependent).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from generate import generate


CASES = [
    {
        "type": "article",
        "outline": "evals/fixtures/sample-article-outline.json",
        "fact_pack": "evals/fixtures/sample-article-fact-pack.md",
        "min_words": 100,
        "min_score": 60,
        "max_seconds": 45,
    },
    {
        "type": "news",
        "outline": "evals/fixtures/sample-news-outline.json",
        "fact_pack": "evals/fixtures/sample-news-fact-pack.md",
        "min_words": 80,
        "min_score": 60,
        "max_seconds": 30,
    },
    {
        "type": "book-chapter",
        "outline": "evals/fixtures/sample-book-chapter-outline.json",
        "fact_pack": "evals/fixtures/sample-book-chapter-fact-pack.md",
        "min_words": 300,
        "min_score": 60,
        "max_seconds": 90,
    },
]


def _assert(cond: bool, msg: str) -> bool:
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    return cond


def main() -> int:
    if "ARABIC_AUTHORING_RUN_LLM" not in os.environ:
        print("Skipped: set ARABIC_AUTHORING_RUN_LLM=1 to run LLM-dependent multi-content-type tests.")
        return 0

    print("=== v1.2.0 multi-content-type smoke test ===\n")
    failures = 0
    for case in CASES:
        print(f"━━━ Content type: {case['type']} ━━━")
        outline = json.loads((ROOT / case["outline"]).read_text(encoding="utf-8"))
        fact_pack = (ROOT / case["fact_pack"]).read_text(encoding="utf-8")
        result = generate(case["type"], outline, fact_pack,
                          proxy_name="minimax", humanness_threshold=case["min_score"],
                          max_regen_per_section=1)
        elapsed = result["elapsed_s"]
        full_text = result["full_text_ar"]
        word_count = len(full_text.split())
        # Average humanness score across sections
        scores = [s["humanizer_gate"].get("score", 0) for s in result["sections"]]
        avg_score = sum(scores) / max(1, len(scores))

        if not _assert(word_count >= case["min_words"],
                       f"{case['type']} produced >={case['min_words']} words (got {word_count})"):
            failures += 1
        if not _assert(avg_score >= case["min_score"],
                       f"{case['type']} avg humanness >={case['min_score']} (got {avg_score:.0f})"):
            failures += 1
        if not _assert(elapsed <= case["max_seconds"],
                       f"{case['type']} completed in <{case['max_seconds']}s (got {elapsed:.1f}s)"):
            failures += 1
        print(f"  → {len(result['sections'])} sections, {word_count} words, "
              f"avg humanness {avg_score:.0f}/100, {elapsed:.1f}s")
        print()

    print()
    if failures:
        print(f"FAILED: {failures} assertion(s)")
        return 1
    print(f"OK: all {len(CASES)} content types generated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
