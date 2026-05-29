#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_refusal_contract.py — refusal-first contract regression suite for author.py.

The skill's v0.1 primary feature is REFUSAL: a thin/one-line brief is rejected,
a missing fact pack is rejected, and each content type enforces its own
source-count threshold (article >=3, book-chapter >=10, course-module >=5,
news >=1). All checks here exercise the deterministic, importable helpers
(_validate_fact_pack, _count_sources_in_pack) — NO LLM, NO network.

Fact packs are written to a tempdir because _validate_fact_pack takes a Path.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from author import (
    _validate_fact_pack,
    _count_sources_in_pack,
    CONTENT_TYPE_REQUIREMENTS,
)

PASS, FAIL = "[PASS]", "[FAIL]"
failures = 0


def check(cond, label):
    global failures
    print(f"  {PASS if cond else FAIL} {label}")
    if not cond:
        failures += 1


def section(t):
    print(f"\n--- {t} ---")


def too_few_sources(refusals):
    """True if any refusal reason is about an insufficient source count."""
    return any("requires >=" in r and "sources" in r for r in refusals)


# Make an N-source pack (each numbered citation line counts as one source).
def make_pack(tmp: Path, name: str, n_sources: int) -> Path:
    lines = ["# Fact pack", "", "## Sources", ""]
    for i in range(1, n_sources + 1):
        lines.append(f"[{i}] Author {i}, 2024, Title {i}")
    p = tmp / name
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="refusal_contract_"))

    # ---------- A: source counter is deterministic ----------
    section("A: deterministic source counter")
    check(_count_sources_in_pack("") == 0,
          "empty text -> 0 sources")
    check(_count_sources_in_pack("[1] one\n[2] two\n[3] three") == 3,
          "three numbered citations -> 3 sources")

    # ---------- B: empty / one-line brief is refused ----------
    section("B: empty / one-line brief refused")
    empty = tmp / "empty.md"
    empty.write_text("", encoding="utf-8")
    r = _validate_fact_pack("article", empty)
    check(len(r) > 0, "empty fact pack -> refused (non-empty refusal list)")
    check(too_few_sources(r), "empty fact pack -> refused for too few sources")

    oneline = tmp / "oneline.md"
    oneline.write_text("Write me an article about Vision 2030.", encoding="utf-8")
    r = _validate_fact_pack("article", oneline)
    check(len(r) > 0, "one-line brief (0 sources) -> refused")

    # ---------- C: missing fact pack file is refused ----------
    section("C: missing fact pack refused")
    missing = tmp / "does-not-exist.md"
    r = _validate_fact_pack("article", missing)
    check(len(r) > 0, "missing fact pack file -> refused")
    check(any("not found" in reason.lower() for reason in r),
          "missing fact pack -> refusal_reason mentions 'not found'")

    # ---------- D: unknown content type is refused ----------
    section("D: unknown content type refused")
    any_pack = make_pack(tmp, "any.md", 12)
    r = _validate_fact_pack("listicle", any_pack)
    check(any("unknown content type" in reason.lower() for reason in r),
          "unknown content type -> refusal_reason mentions 'unknown content type'")

    # ---------- E: book-chapter needs >=10 sources ----------
    section("E: book-chapter source threshold (>=10)")
    bc_min = CONTENT_TYPE_REQUIREMENTS["book-chapter"]["sources_min"]
    check(bc_min == 10, f"book-chapter sources_min == 10 (got {bc_min})")

    bc_few = make_pack(tmp, "bc-few.md", 5)
    r = _validate_fact_pack("book-chapter", bc_few)
    check(too_few_sources(r),
          "book-chapter with 5 sources -> refused (too few)")

    bc_ok = make_pack(tmp, "bc-ok.md", 11)
    r = _validate_fact_pack("book-chapter", bc_ok)
    check(not too_few_sources(r),
          "book-chapter with 11 sources -> NOT refused for source count")

    # ---------- F: article needs >=3 sources (lower bar) ----------
    section("F: article source threshold (>=3)")
    art_min = CONTENT_TYPE_REQUIREMENTS["article"]["sources_min"]
    check(art_min == 3, f"article sources_min == 3 (got {art_min})")

    art_few = make_pack(tmp, "art-few.md", 2)
    r = _validate_fact_pack("article", art_few)
    check(too_few_sources(r),
          "article with 2 sources -> refused (too few)")

    art_ok = make_pack(tmp, "art-ok.md", 3)
    r = _validate_fact_pack("article", art_ok)
    check(len(r) == 0,
          "article with 3 sources -> accepted (no refusals)")

    # ---------- G: threshold is genuinely per-type ----------
    section("G: thresholds are per-content-type")
    # A 5-source pack: passes article (>=3) but fails book-chapter (>=10).
    five = make_pack(tmp, "five.md", 5)
    r_art = _validate_fact_pack("article", five)
    r_bc = _validate_fact_pack("book-chapter", five)
    check(len(r_art) == 0 and too_few_sources(r_bc),
          "5-source pack: article accepts, book-chapter refuses")

    # ---------- Verdict ----------
    print()
    print("-" * 60)
    if failures == 0:
        print("All refusal-contract assertions PASS")
        print("-" * 60)
        return 0
    print(f"{failures} refusal-contract assertions FAIL")
    print("-" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
