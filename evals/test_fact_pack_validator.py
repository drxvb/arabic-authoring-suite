#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_fact_pack_validator.py -- v1.7.0 regression suite for validate_fact_pack.

Closes the 3-of-3 A6 multi-vendor convergent gap. 14 assertions across 6 fixtures:
  A. Empty / malformed input edge cases
  B. Full grounding (all claims supported)
  C. Partial grounding (some claims ungrounded)
  D. Zero-coverage section (blocking error)
  E. Content-type threshold enforcement (book-chapter stricter)
  F. Arabic + Latin mixed claims
"""
from __future__ import annotations
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_fact_pack import validate_fact_pack

PASS, FAIL = "[PASS]", "[FAIL]"
failures = 0
def check(cond, label):
    global failures
    print(f"  {PASS if cond else FAIL} {label}")
    if not cond: failures += 1
def section(t): print(f"\n--- {t} ---")


# ---------- A: empty / malformed input ----------
section("A: empty / malformed input edge cases")
r = validate_fact_pack({}, "any text")
check(r.ok is False, "empty outline -> ok=False")
check(any("empty" in e.lower() or "sections" in e.lower() for e in r.errors),
      "empty outline -> error mentions sections/empty")

r = validate_fact_pack({"sections": [{"claims": ["x"]}]}, "")
check(r.ok is False, "empty fact_pack -> ok=False")

r = validate_fact_pack({"sections": []}, "any text")
check(r.ok is False, "outline.sections=[] -> ok=False")


# ---------- B: full grounding ----------
section("B: full grounding (all claims supported)")
outline_b = {
    "title_ar": "تقرير",
    "sections": [
        {"intent": "intro",
         "claims": ["Riyadh hosted the GCC summit in November",
                    "Vision 2030 emphasizes economic diversification"]},
        {"intent": "body",
         "claims": ["The Saudi Central Bank raised interest rates to 4 percent"]},
    ]
}
fact_pack_b = (
    "Source 1: Riyadh hosted the GCC summit in November 2024 with all six "
    "GCC member states attending.\n"
    "Source 2: Saudi Arabia's Vision 2030 strategic plan emphasizes economic "
    "diversification and reduced oil dependency.\n"
    "Source 3: The Saudi Central Bank announced interest rates raised to "
    "4 percent in Q3 2024."
)
r = validate_fact_pack(outline_b, fact_pack_b, content_type="article")
check(r.ok is True, f"full grounding -> ok=True (got coverage {r.overall_coverage:.0%})")
check(r.overall_coverage >= 0.99, f"coverage 100% (got {r.overall_coverage:.0%})")
check(r.total_claims == 3, f"3 claims counted (got {r.total_claims})")
check(r.grounded_claims == 3, f"3 grounded (got {r.grounded_claims})")


# ---------- C: partial grounding (one ungrounded) ----------
section("C: partial grounding (one ungrounded)")
outline_c = {
    "sections": [
        {"intent": "intro",
         "claims": ["Riyadh hosted the GCC summit",                        # grounded
                    "Mars colony landed three astronauts in 2024"]},        # ungrounded
        {"intent": "body",
         "claims": ["Saudi Central Bank policy news"]},                     # partially grounded
    ]
}
fact_pack_c = "Riyadh hosted the GCC summit in November 2024. Saudi Central Bank issued policy news."
r = validate_fact_pack(outline_c, fact_pack_c, content_type="article",
                       min_coverage_ratio=0.5)
check(r.overall_coverage >= 0.5, f"partial grounding meets 50% (got {r.overall_coverage:.0%})")
check(any("Mars" in u["claim"] for u in r.ungrounded_claims),
      "Mars claim correctly flagged as ungrounded")


# ---------- D: zero-coverage section ----------
section("D: zero-coverage section (blocking error)")
outline_d = {
    "sections": [
        {"intent": "intro",
         "claims": ["Riyadh hosted the GCC summit"]},                       # grounded
        {"intent": "deep dive",
         "claims": ["Quantum cryptography breakthrough in Pyongyang labs",  # ungrounded
                    "Antimatter telescope launched from Antarctica"]},      # ungrounded
    ]
}
fact_pack_d = "Riyadh hosted the GCC summit in November."
r = validate_fact_pack(outline_d, fact_pack_d, content_type="article")
check(r.ok is False,
      "section with 0/2 grounded claims -> ok=False (blocking error)")
check(any("0/" in e for e in r.errors),
      "errors include '0/N claims grounded' message")


# ---------- E: content-type threshold ----------
section("E: book-chapter raises the bar")
# Two-section outline. Section 1 grounded; section 2 has one grounded + one ungrounded
# claim. Overall 2/3 = 66.7%. Article threshold (50%) passes; book-chapter (70%) fails.
outline_e = {
    "sections": [
        {"intent": "intro",
         "claims": ["Riyadh hosted the GCC summit in November 2024"]},
        {"intent": "body",
         "claims": ["Saudi Central Bank raised interest rates to 4 percent",
                    "Mars colony program landed three astronauts in October 2024"]},
    ]
}
fact_pack_e = (
    "Source 1: Riyadh hosted the GCC summit in November 2024.\n"
    "Source 2: The Saudi Central Bank raised interest rates to 4 percent."
)
r_art = validate_fact_pack(outline_e, fact_pack_e, content_type="article",
                            min_coverage_ratio=0.5)
check(r_art.ok is True,
      f"article 50% threshold met by 2/3 grounded (got {r_art.overall_coverage:.0%})")
r_book = validate_fact_pack(outline_e, fact_pack_e, content_type="book-chapter")
check(r_book.ok is False,
      f"book-chapter 70% threshold NOT met by 2/3 grounded (got {r_book.overall_coverage:.0%})")


# ---------- F: Arabic + Latin mixed ----------
section("F: Arabic + Latin mixed claims")
outline_f = {
    "sections": [
        {"intent": "intro",
         "claims": [
             "زار الرئيس العاصمة الرياض",     # Arabic, should be grounded
             "Saudi Vision 2030 plan",         # Latin, should be grounded
         ]},
    ]
}
fact_pack_f = (
    "بحسب الوكالة، زار الرئيس العاصمة الرياض في نوفمبر.\n"
    "Saudi Vision 2030 plan covers economic diversification."
)
r = validate_fact_pack(outline_f, fact_pack_f, content_type="article")
check(r.ok is True, f"Arabic + Latin mixed -> ok=True (got {r.overall_coverage:.0%})")
check(r.grounded_claims == 2, f"both Arabic and Latin claims grounded (got {r.grounded_claims})")


# ---------- Verdict ----------
print()
print("─" * 60)
if failures == 0:
    print("✓ All 14 fact-pack validator assertions PASS")
    print("─" * 60)
    sys.exit(0)
else:
    print(f"✗ {failures} fact-pack validator assertions FAIL")
    print("─" * 60)
    sys.exit(1)
