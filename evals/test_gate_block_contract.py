#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_gate_block_contract.py -- v1.8.0 blocking-gate + fact-pack refusal contract.

Deterministic, NO live LLM. Verifies the two structured-refusal paths of
generate() introduced/hardened across v1.7.0 (fact-pack pre-flight) and
v1.8.0 (humanizer-as-gate teeth):

  A. Fact-pack pre-flight refusal: generate() with ungrounded claims must
     refuse with refusal_reason == "fact_pack_validation_failed" BEFORE any
     LLM call. (The pre-flight runs first, so this path never touches the
     network even without monkeypatching.)
  B. Humanizer gate-block refusal: with humanizer_gate_block=True, if every
     drafted section scores below threshold after regen, generate() must
     refuse the ENTIRE output with refusal_reason == "humanizer_gate_failed"
     and a populated failed_sections list. draft_section + humanizer_gate are
     monkeypatched to deterministic stubs so NO proxy network call happens.
  C. Gate-block disabled (v1.7.0 permissive): humanizer_gate_block=False with
     the same failing stubs must NOT refuse — output ships with per-section
     gate metadata flagging the failure.
  D. validate_fact_pack helper in isolation: ungrounded outline -> ok False.

stdlib only. Network failure paths use monkeypatched stubs (never live).
"""
from __future__ import annotations
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate as generate_mod
from generate import generate
from validate_fact_pack import validate_fact_pack

PASS, FAIL = "[PASS]", "[FAIL]"
failures = 0


def check(cond, label):
    global failures
    print(f"  {PASS if cond else FAIL} {label}")
    if not cond:
        failures += 1


def section(t):
    print(f"\n--- {t} ---")


# A claim deliberately unsupported by the fact pack below.
UNGROUNDED_OUTLINE = {
    "title_ar": "تقرير",
    "sections": [
        {"intent": "intro",
         "heading_ar": "مقدمة",
         "claims": [
             "Mars colony landed three astronauts on the red planet in 2024",
             "Quantum teleportation network spans Pyongyang and Antarctica",
         ]},
    ],
}
# Fact pack contains NOTHING about the claims above.
UNGROUNDED_FACT_PACK = (
    "Source 1: Riyadh hosted the GCC summit in November 2024.\n"
    "Source 2: The Saudi Central Bank raised interest rates to 4 percent.\n"
)

# A grounded outline so we can get PAST the fact-pack pre-flight and exercise
# the humanizer gate path.
GROUNDED_OUTLINE = {
    "title_ar": "تقرير اقتصادي",
    "sections": [
        {"intent": "intro",
         "heading_ar": "مقدمة",
         "claims": ["Riyadh hosted the GCC summit in November 2024"]},
        {"intent": "body",
         "heading_ar": "التفاصيل",
         "claims": ["The Saudi Central Bank raised interest rates to 4 percent"]},
    ],
}
GROUNDED_FACT_PACK = (
    "Source 1: Riyadh hosted the GCC summit in November 2024 with all six GCC states.\n"
    "Source 2: The Saudi Central Bank raised interest rates to 4 percent in Q3 2024.\n"
)


# ---------- A: fact-pack pre-flight refusal via generate() (no LLM) ----------
section("A: fact-pack pre-flight refusal (generate, no LLM)")

# Guard: if generate() somehow reaches drafting, draft_section would hit the
# network. Replace it with a tripwire that fails the test loudly instead.
_orig_draft = generate_mod.draft_section


def _tripwire_draft(*a, **k):
    raise AssertionError(
        "draft_section called during fact-pack pre-flight path — pre-flight "
        "should have refused BEFORE any LLM/network call")


generate_mod.draft_section = _tripwire_draft
try:
    res_a = generate("article", dict(UNGROUNDED_OUTLINE), UNGROUNDED_FACT_PACK,
                     validate_fact_pack_first=True,
                     fact_pack_min_coverage=0.5)
finally:
    generate_mod.draft_section = _orig_draft

check(res_a.get("ok") is False, "ungrounded fact pack -> ok=False")
check(res_a.get("refused") is True, "ungrounded fact pack -> refused=True")
check(res_a.get("refusal_reason") == "fact_pack_validation_failed",
      f"refusal_reason == 'fact_pack_validation_failed' (got {res_a.get('refusal_reason')!r})")
check("fact_pack_validation" in res_a and res_a["fact_pack_validation"].get("ok") is False,
      "result carries fact_pack_validation report with ok=False")
check("full_text_ar" not in res_a,
      "refused result emits no full_text_ar (nothing was drafted)")


# ---------- B: humanizer gate-block refusal (monkeypatched, no LLM) ----------
section("B: humanizer gate-block refusal (humanizer_gate_block=True)")

draft_calls = {"n": 0}


def _stub_draft(content_type, outline, sec, fact_pack_text, proxy_name="kimi"):
    # Deterministic Arabic prose; never touches the network.
    draft_calls["n"] += 1
    return "هذا نص عربي تجريبي للقسم الحالي يحتوي على محتوى ثابت."


def _stub_gate_fail(text_ar, threshold=60, register="news"):
    # Always sub-threshold -> gate fails deterministically.
    return {
        "available": True,
        "score": 12,
        "ai_tell_hits": 7,
        "total_words": len(text_ar.split()),
        "threshold": threshold,
        "passes_gate": False,
        "backend": "stub_fail",
    }


_orig_draft2 = generate_mod.draft_section
_orig_gate = generate_mod.humanizer_gate
generate_mod.draft_section = _stub_draft
generate_mod.humanizer_gate = _stub_gate_fail
try:
    res_b = generate("article", dict(GROUNDED_OUTLINE), GROUNDED_FACT_PACK,
                     validate_fact_pack_first=True,
                     fact_pack_min_coverage=0.5,
                     max_regen_per_section=1,
                     humanizer_gate_block=True)
finally:
    generate_mod.draft_section = _orig_draft2
    generate_mod.humanizer_gate = _orig_gate

check(res_b.get("ok") is False, "failing gate + block -> ok=False")
check(res_b.get("refused") is True, "failing gate + block -> refused=True")
check(res_b.get("refusal_reason") == "humanizer_gate_failed",
      f"refusal_reason == 'humanizer_gate_failed' (got {res_b.get('refusal_reason')!r})")
fs = res_b.get("failed_sections")
check(isinstance(fs, list) and len(fs) == 2,
      f"failed_sections populated for both sections (got {len(fs) if isinstance(fs, list) else 'n/a'})")
check(all(s.get("gate_score") == 12 and s.get("threshold") == 60 for s in (fs or [])),
      "each failed section records sub-threshold gate_score and threshold")
check(draft_calls["n"] >= len(GROUNDED_OUTLINE["sections"]),
      f"draft stub invoked (no live LLM); calls={draft_calls['n']}")


# ---------- C: gate-block disabled -> permissive ship (v1.7.0 behavior) ----------
section("C: humanizer_gate_block=False -> no refusal, ships with metadata")

draft_calls["n"] = 0
generate_mod.draft_section = _stub_draft
generate_mod.humanizer_gate = _stub_gate_fail
try:
    res_c = generate("article", dict(GROUNDED_OUTLINE), GROUNDED_FACT_PACK,
                     validate_fact_pack_first=True,
                     fact_pack_min_coverage=0.5,
                     max_regen_per_section=1,
                     humanizer_gate_block=False)
finally:
    generate_mod.draft_section = _orig_draft2
    generate_mod.humanizer_gate = _orig_gate

check(res_c.get("refused") is not True,
      "gate_block=False -> not refused even though gate failed")
check("full_text_ar" in res_c and res_c["full_text_ar"],
      "gate_block=False -> output ships with full_text_ar")
check(all(s["humanizer_gate"]["passes_gate"] is False for s in res_c["sections"]),
      "shipped sections still carry failing gate metadata (gate-not-silent)")


# ---------- D: validate_fact_pack helper in isolation ----------
section("D: validate_fact_pack helper (isolation)")
rep_d = validate_fact_pack(UNGROUNDED_OUTLINE, UNGROUNDED_FACT_PACK,
                           content_type="article", min_coverage_ratio=0.5)
check(rep_d.ok is False, "ungrounded outline -> report.ok=False")
check(len(rep_d.ungrounded_claims) >= 1, "ungrounded claims surfaced in report")


# ---------- Verdict ----------
print()
print("=" * 60)
if failures == 0:
    print("OK: All gate-block + fact-pack refusal contract assertions PASS")
    print("=" * 60)
    sys.exit(0)
else:
    print(f"FAIL: {failures} gate-block contract assertions FAILED")
    print("=" * 60)
    sys.exit(1)
