#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_generate.py — v1.0.0 eval suite for the authoring-suite generator.
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

from generate import (
    SECTION_SYSTEM_PROMPT_BY_TYPE,
    PROXIES,
    _build_section_prompt,
    draft_section,
    humanizer_gate,
    generate,
)


def _assert(cond: bool, msg: str) -> bool:
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    return cond


def main() -> int:
    print("=== arabic-authoring-suite v1.0.0 eval suite ===\n")
    failures = 0

    # T1: System prompts present for all four content types
    for ctype in ("article", "book-chapter", "course-module", "news"):
        if not _assert(ctype in SECTION_SYSTEM_PROMPT_BY_TYPE,
                       f"system prompt defined for content type {ctype!r}"):
            failures += 1

    # T2: Each system prompt warns against AI-tells
    AI_TELLS_TO_BAN = ["من المهم ملاحظة", "علاوة على ذلك", "تجدر الإشارة"]
    for ctype, prompt in SECTION_SYSTEM_PROMPT_BY_TYPE.items():
        present = any(tell in prompt for tell in AI_TELLS_TO_BAN)
        if not _assert(present or ctype == "course-module",
                       f"{ctype} system prompt includes AI-tell warnings (or course-module exempt)"):
            failures += 1

    # T3: Four proxies registered
    if not _assert(set(PROXIES.keys()) == {"kimi", "codex", "gemini", "minimax"},
                   f"all four proxies registered (got {sorted(PROXIES.keys())})"):
        failures += 1

    # T4: _build_section_prompt produces a non-trivial prompt
    fake_outline = {"title_ar": "اختبار", "register": "news"}
    fake_section = {"heading_ar": "قسم", "intent": "اختبار توليد", "word_budget": 150}
    prompt = _build_section_prompt("article", fake_outline, fake_section, "fact pack body")
    if not _assert(len(prompt) > 100,
                   f"section prompt is non-trivial (got {len(prompt)} chars)"):
        failures += 1
    if not _assert("fact pack body" in prompt,
                   "section prompt includes the fact pack text"):
        failures += 1
    if not _assert("150" in prompt,
                   "section prompt includes the word budget"):
        failures += 1

    # T5: humanizer_gate runs on clean text → high score
    clean = "أعلنت الحكومة عن خطة جديدة. تشمل الخطة عدة محاور."
    g = humanizer_gate(clean, threshold=60)
    if not _assert(g.get("score", 0) >= 60,
                   f"humanizer_gate clean text score >= 60 (got {g.get('score')})"):
        failures += 1
    if not _assert(g.get("passes_gate") is True,
                   "clean text passes humanizer gate"):
        failures += 1

    # T6: humanizer_gate catches AI-tells
    sloppy = ("من المهم ملاحظة أن النظام مهم. علاوة على ذلك، تجدر الإشارة إلى أن "
              "الفائدة كبيرة. في غاية الأهمية. بشكل عام، الأمر جيد.")
    g_bad = humanizer_gate(sloppy, threshold=60)
    if not _assert(g_bad.get("ai_tell_hits", 0) >= 3,
                   f"humanizer_gate catches >=3 AI-tells in sloppy text (got {g_bad.get('ai_tell_hits')})"):
        failures += 1

    # T7: full generation if LLM is reachable (smoke test)
    if "ARABIC_AUTHORING_RUN_LLM" in os.environ:
        outline = json.loads((ROOT / "evals/fixtures/sample-article-outline.json").read_text(encoding="utf-8"))
        fact_pack = (ROOT / "evals/fixtures/sample-article-fact-pack.md").read_text(encoding="utf-8")
        result = generate("article", outline, fact_pack, proxy_name="minimax",
                          humanness_threshold=60, max_regen_per_section=0)
        if not _assert(len(result["sections"]) == 2,
                       f"generate produced 2 sections (got {len(result['sections'])})"):
            failures += 1
        if not _assert(len(result["full_text_ar"]) > 200,
                       f"full_text_ar is non-trivial (got {len(result['full_text_ar'])} chars)"):
            failures += 1
        if not _assert(any(s["humanizer_gate"]["passes_gate"] for s in result["sections"]),
                       "at least one section passes humanizer gate"):
            failures += 1
    else:
        print("  [SKIP] T7 LLM smoke test (set ARABIC_AUTHORING_RUN_LLM=1 to enable)")

    print()
    if failures:
        print(f"FAILED: {failures} test(s)")
        return 1
    print("OK: all eval-suite tests pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
