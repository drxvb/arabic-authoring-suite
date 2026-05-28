#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
author.py — CLI for arabic-authoring-suite v0.1.

v0.1 ships REFUSAL LOGIC ONLY. The skill's primary behavior is to refuse
bad briefs — that's the discipline Agent C's review identified as the
escape from the "slop generator with slop cleaner glued on" trap.

Generation logic ships in v0.2 once the per-content-type outline schemas
are formalized.

Usage (v0.1 — refusal-only):

    # All of these REFUSE (and that's the point):
    python author.py --type article --topic "Vision 2030"
    python author.py --type book-chapter --fact-pack ./brief.md
    python author.py --type course --topic "Python basics" --output module.md

    # Acceptable shape (but v0.1 returns "draft logic in v0.2" stub):
    python author.py --type article --fact-pack ./brief-with-3-sources.md

Python 3 stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# Per Agent C's design (references/01-charter.md):
CONTENT_TYPE_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    "article": {
        "sources_min": 3,
        "outline_sections_min": 2,
        "outline_sections_max": 4,
        "word_budget_min": 500,
        "word_budget_max": 2500,
        "register": "news",
        "humanness_threshold": 60,
    },
    "book-chapter": {
        "sources_min": 10,
        "outline_sections_min": 4,
        "outline_sections_max": 8,
        "word_budget_min": 3000,
        "word_budget_max": 8000,
        "register": "classical",
        "humanness_threshold": 75,
    },
    "course-module": {
        "sources_min": 5,
        "outline_sections_min": 3,
        "outline_sections_max": 6,
        "word_budget_min": 1500,
        "word_budget_max": 4000,
        "register": "technical",
        "humanness_threshold": 50,
        "additional_requirements": ["learning_objectives", "exercise_bank"],
    },
    "news": {
        "sources_min": 1,
        "outline_sections_min": 1,
        "outline_sections_max": 2,
        "word_budget_min": 200,
        "word_budget_max": 800,
        "register": "news",
        "humanness_threshold": 55,
        "additional_requirements": ["5w_h"],  # who/what/when/where/why/how coverage
    },
}


def _count_sources_in_pack(pack_text: str) -> int:
    """Heuristic source counter. Counts:
      - Lines beginning with a citation marker: [1], 1., -, *
      - URLs
      - Lines matching 'Source:' / 'المصدر:' / 'Ref:'
    Conservative — under-counts. v0.2 will require structured frontmatter.
    """
    count = 0
    # URLs (each unique URL counts as a source)
    urls = set(re.findall(r"https?://\S+", pack_text))
    count += len(urls)
    # Numbered or bulleted citation lines
    for line in pack_text.splitlines():
        stripped = line.strip()
        if re.match(r"^\[\d+\]", stripped):
            count += 1
        elif re.match(r"^\d+\.\s+\S", stripped) and "http" not in stripped:
            count += 1
    # Explicit "Source:" / "المصدر:" lines (count each as a source)
    count += len(re.findall(r"(?im)^(?:source|المصدر|ref|reference):\s+\S", pack_text))
    return count


def _validate_fact_pack(content_type: str, pack_path: Path) -> List[str]:
    """Return a list of refusal reasons. Empty list means the pack is acceptable."""
    refusals: List[str] = []
    spec = CONTENT_TYPE_REQUIREMENTS.get(content_type)
    if spec is None:
        refusals.append(f"unknown content type: {content_type}. Known: {sorted(CONTENT_TYPE_REQUIREMENTS)}")
        return refusals

    if not pack_path.exists():
        refusals.append(f"fact pack file not found: {pack_path}")
        return refusals

    try:
        text = pack_path.read_text(encoding="utf-8")
    except Exception as e:
        refusals.append(f"could not read fact pack: {e}")
        return refusals

    sources_found = _count_sources_in_pack(text)
    sources_min = spec["sources_min"]
    if sources_found < sources_min:
        refusals.append(
            f"{content_type} requires >={sources_min} sources; fact pack appears to contain {sources_found}. "
            f"See references/01-charter.md for the source counting heuristic."
        )

    # Additional content-type-specific checks
    additional = spec.get("additional_requirements", [])
    if "learning_objectives" in additional:
        if not re.search(r"(?i)(learning\s+objective|أهداف\s+التعلم|أهداف\s+الدرس)", text):
            refusals.append(
                "course-module requires explicit 'Learning objectives' / 'أهداف التعلم' section in the fact pack"
            )
    if "exercise_bank" in additional:
        if not re.search(r"(?i)(exercise|تمرين|تمارين)", text):
            refusals.append(
                "course-module requires an 'Exercises' / 'تمارين' section with sample problems"
            )
    if "5w_h" in additional:
        coverage = sum(1 for keyword in
                       ["who", "what", "when", "where", "why", "how",
                        "من", "ما", "متى", "أين", "لماذا", "كيف"]
                       if keyword in text.lower())
        if coverage < 4:
            refusals.append(
                "news piece requires 5W+H coverage in the fact pack (who/what/when/where/why/how). "
                f"Found {coverage}/6+ keywords."
            )

    return refusals


def main() -> int:
    p = argparse.ArgumentParser(description="arabic-authoring-suite v0.1 — refusal-first authoring CLI")
    p.add_argument("--type", required=True,
                   choices=list(CONTENT_TYPE_REQUIREMENTS),
                   help="Content type. Each has its own fact-pack requirements.")
    p.add_argument("--fact-pack", "-f", help="Path to fact pack file (Markdown with sources)")
    p.add_argument("--topic", help="Topic hint — DEPRECATED. Topic alone is refused by design.")
    p.add_argument("--outline-file", help="(v0.2+) Pre-approved outline JSON file")
    p.add_argument("--output", "-o", help="Where to write generated Arabic content")
    p.add_argument("--list-requirements", action="store_true",
                   help="Print fact-pack requirements per content type and exit")
    args = p.parse_args()

    if args.list_requirements:
        print(json.dumps(CONTENT_TYPE_REQUIREMENTS, ensure_ascii=False, indent=2))
        return 0

    # ─ Refusal logic (the v0.1 primary feature) ─
    if not args.fact_pack:
        print(
            f"REFUSED: --type {args.type} requires --fact-pack <path>.\n"
            f"This skill does NOT generate from one-line prompts. See references/01-charter.md.\n"
            f"For requirements: --list-requirements",
            file=sys.stderr,
        )
        return 2

    pack_path = Path(args.fact_pack)
    refusals = _validate_fact_pack(args.type, pack_path)
    if refusals:
        print(f"REFUSED: fact pack does not meet {args.type} requirements:", file=sys.stderr)
        for r in refusals:
            print(f"  - {r}", file=sys.stderr)
        print(f"\nSee `--list-requirements` for full specs.", file=sys.stderr)
        return 2

    # ─ Accepted brief — v0.1 stops here ─
    spec = CONTENT_TYPE_REQUIREMENTS[args.type]
    print(
        f"[v0.1 STUB] Fact pack accepted for content type '{args.type}'.\n"
        f"  Sources found: meets >={spec['sources_min']} requirement.\n"
        f"  Register: {spec['register']}\n"
        f"  Word budget: {spec['word_budget_min']}-{spec['word_budget_max']}\n"
        f"  Humanness threshold: {spec['humanness_threshold']}/100\n\n"
        f"Outline→Draft→Revise generation lands in v0.2. v0.1 ships refusal logic only.\n"
        f"\n"
        f"To prepare for v0.2: structure your fact pack as Markdown with explicit citations:\n"
        f"  ## Sources\n"
        f"  [1] Author, Year, Title, URL\n"
        f"  [2] ...\n"
        f"\n"
        f"  ## Claims to support\n"
        f"  - Claim 1: [evidence from source 1]\n"
        f"  - Claim 2: [evidence from sources 2,3]\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
