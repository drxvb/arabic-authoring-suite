#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_fact_pack.py -- v1.7.0 pre-flight fact-pack completeness validator.

Closes the 3-of-3 A6 multi-vendor convergent gap: kimi + minimax-M2 + deepseek-v4-pro
ALL THREE independently flagged "fact-pack completeness validation" as the missing
P0 item for arabic-authoring-suite. The strongest convergent signal in the A6 audit.

Contract: BEFORE generate() spends LLM tokens drafting sections, this validator
verifies that every claim listed in outline['sections'][*]['claims'] has supporting
content in fact_pack_text. Hallucinated claims (claims with no fact-pack evidence)
are surfaced as errors so the author can fix the fact-pack OR remove the unsupported
claim before generation.

API:
    report = validate_fact_pack(outline, fact_pack_text, content_type="article",
                                min_coverage_ratio=0.5, min_keywords_per_claim=2)
    # report.ok                -> bool
    # report.errors            -> list[str] (blocking — generate() refuses unless force=True)
    # report.warnings          -> list[str] (non-blocking signals)
    # report.section_coverage  -> list[dict] per-section breakdown
    # report.overall_coverage  -> float in [0,1]

Algorithm:
  1. For each section, extract claims (outline['sections'][i]['claims']).
  2. For each claim, tokenize into content keywords (Arabic OR Latin, >=3 chars,
     filter out stopwords from a small curated list).
  3. A claim is "grounded" if >= min_keywords_per_claim of its keywords appear
     in fact_pack_text (case-insensitive for Latin; exact for Arabic).
  4. Section coverage = grounded_claims / total_claims.
  5. Overall coverage = sum(grounded_claims) / sum(total_claims) across all sections.
  6. ok = overall_coverage >= min_coverage_ratio AND no section has 0% coverage.

Python 3 stdlib only.
"""
from __future__ import annotations
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# Minimal stopword sets. The list is intentionally short -- we want false-positives
# (claim with stopwords-only that grounds against stopwords-only fact_pack) to be
# blocked by the >=2 keyword threshold instead.
ARABIC_STOPWORDS = {
    "في", "من", "إلى", "على", "عن", "مع", "هذا", "هذه", "ذلك", "تلك", "التي", "الذي",
    "هو", "هي", "هم", "أن", "أو", "كل", "ما", "لا", "إن", "كان", "كانت", "قد", "ثم",
}
ENGLISH_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "by", "for",
    "is", "are", "was", "were", "be", "been", "being", "this", "that", "these",
    "those", "it", "its", "as", "with", "from", "into", "but", "not",
}
STOPWORDS = ARABIC_STOPWORDS | ENGLISH_STOPWORDS


# Arabic block: U+0600 - U+06FF; we also accept Latin word chars
_TOKEN_RE = re.compile(r"[؀-ۿ\w][؀-ۿ\w'-]*", re.UNICODE)


@dataclass
class FactPackValidationReport:
    """Result of validate_fact_pack(). Mirrors the kimi A6 proposal's ValidationReport
    shape but stdlib-only (no pydantic dependency)."""
    ok: bool
    overall_coverage: float
    section_coverage: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    total_claims: int = 0
    grounded_claims: int = 0
    ungrounded_claims: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __bool__(self) -> bool:
        return self.ok


def _keywords_of(text: str) -> List[str]:
    """Extract content keywords from a claim string. Returns lowercased Latin
    and original-form Arabic tokens of length >=3 that aren't stopwords."""
    if not isinstance(text, str):
        return []
    out: List[str] = []
    seen: set = set()
    for tok in _TOKEN_RE.findall(text):
        # Detect Arabic by character range
        is_arabic = any("؀" <= ch <= "ۿ" for ch in tok)
        norm = tok if is_arabic else tok.lower()
        if norm in STOPWORDS or len(norm) < 3:
            continue
        if norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


def _ground_claim(claim_keywords: List[str], fact_pack_lower: str, fact_pack_raw: str,
                  min_keywords: int) -> int:
    """Count how many of the claim's keywords appear in the fact pack.
    Latin keywords case-insensitive (via fact_pack_lower); Arabic exact."""
    hits = 0
    for kw in claim_keywords:
        is_arabic = any("؀" <= ch <= "ۿ" for ch in kw)
        haystack = fact_pack_raw if is_arabic else fact_pack_lower
        # Use word-ish boundary: surrounding chars should not be the same alphabet.
        # For Arabic we use simple substring; for Latin we use \b boundary.
        if is_arabic:
            if kw in haystack:
                hits += 1
        else:
            if re.search(r"\b" + re.escape(kw) + r"\b", haystack):
                hits += 1
    return hits


def validate_fact_pack(outline: Dict[str, Any],
                       fact_pack_text: str,
                       content_type: str = "article",
                       min_coverage_ratio: float = 0.5,
                       min_keywords_per_claim: int = 2) -> FactPackValidationReport:
    """Pre-flight validation: does the fact_pack have evidence for the outline's claims?

    Args:
        outline: dict with `sections: list[dict]`; each section may have `claims: list[str]`.
        fact_pack_text: raw fact-pack text (sources + claims + evidence).
        content_type: 'article' | 'book-chapter' | 'course-module' | 'news'. Stricter
            content types raise the bar (book-chapter requires higher coverage).
        min_coverage_ratio: minimum overall grounded/total ratio for ok=True.
        min_keywords_per_claim: a claim is grounded if >= this many of its keywords
            appear in the fact pack. 2 is conservative; 1 catches more borderline.

    Returns:
        FactPackValidationReport. report.ok=True if both the overall coverage ratio
        meets the threshold AND no section has 0% claim coverage.
    """
    rep = FactPackValidationReport(ok=False, overall_coverage=0.0)

    if not isinstance(outline, dict):
        rep.errors.append("outline is not a dict")
        return rep
    if not isinstance(fact_pack_text, str) or not fact_pack_text.strip():
        rep.errors.append("fact_pack_text is empty or not a string")
        return rep

    # Per-content-type minimum coverage adjustment
    # Acceptance from deepseek's per-content-type proposal: stricter types raise the bar.
    type_threshold_override = {
        "book-chapter": max(min_coverage_ratio, 0.7),  # books need richer sourcing
        "course-module": max(min_coverage_ratio, 0.6),
        "news": max(min_coverage_ratio, 0.5),
        "article": min_coverage_ratio,
    }
    effective_threshold = type_threshold_override.get(content_type, min_coverage_ratio)

    sections = outline.get("sections") or []
    if not sections:
        rep.errors.append("outline.sections is empty — nothing to validate")
        return rep

    fp_lower = fact_pack_text.lower()
    fp_raw = fact_pack_text

    total_claims = 0
    total_grounded = 0
    ungrounded: List[Dict[str, Any]] = []
    section_breakdown: List[Dict[str, Any]] = []

    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            rep.warnings.append(f"section[{i}] is not a dict — skipped")
            continue
        section_name = section.get("title_ar") or section.get("intent") or f"section[{i}]"
        claims = section.get("claims") or []
        if not isinstance(claims, list):
            rep.warnings.append(f"section[{i}].claims is not a list — treated as empty")
            claims = []

        sec_grounded = 0
        for j, claim in enumerate(claims):
            if not isinstance(claim, str) or not claim.strip():
                rep.warnings.append(f"section[{i}].claims[{j}] is empty or not a string — skipped")
                continue
            kws = _keywords_of(claim)
            if not kws:
                rep.warnings.append(
                    f"section[{i}].claims[{j}] has no content keywords (all stopwords or <3 chars): "
                    f"{claim[:80]!r}")
                continue
            total_claims += 1
            hits = _ground_claim(kws, fp_lower, fp_raw, min_keywords_per_claim)
            if hits >= min_keywords_per_claim:
                sec_grounded += 1
                total_grounded += 1
            else:
                ungrounded.append({
                    "section_index": i,
                    "section_name": section_name,
                    "claim": claim[:200],
                    "keywords_extracted": kws[:12],
                    "keywords_found_in_factpack": hits,
                    "keywords_required": min_keywords_per_claim,
                })

        sec_total = sum(1 for c in claims if isinstance(c, str) and _keywords_of(c))
        sec_ratio = (sec_grounded / sec_total) if sec_total else None
        section_breakdown.append({
            "index": i,
            "name": section_name,
            "claims_total": sec_total,
            "claims_grounded": sec_grounded,
            "ratio": sec_ratio,
        })
        if sec_total == 0 and content_type in ("book-chapter", "news"):
            rep.warnings.append(
                f"section[{i}] '{section_name}' has 0 claims — "
                f"{content_type} typically needs >= 1")
        elif sec_total > 0 and sec_grounded == 0:
            rep.errors.append(
                f"section[{i}] '{section_name}': 0/{sec_total} claims grounded — "
                "fact_pack provides NO support for this section")

    rep.total_claims = total_claims
    rep.grounded_claims = total_grounded
    rep.section_coverage = section_breakdown
    rep.ungrounded_claims = ungrounded

    if total_claims == 0:
        rep.errors.append(
            "No claims with extractable content keywords found across any section — "
            "the outline has no testable claims")
        rep.overall_coverage = 0.0
        rep.ok = False
        return rep

    rep.overall_coverage = total_grounded / total_claims

    # Content-type specific thresholds
    if rep.overall_coverage < effective_threshold:
        rep.errors.append(
            f"overall coverage {rep.overall_coverage:.1%} < required {effective_threshold:.0%} "
            f"for content_type={content_type!r} "
            f"(grounded {total_grounded}/{total_claims} claims)")

    # Pass condition: no blocking errors AND coverage meets threshold
    rep.ok = (not rep.errors) and (rep.overall_coverage >= effective_threshold)

    if rep.ok and ungrounded:
        rep.warnings.append(
            f"{len(ungrounded)} claims are ungrounded but overall coverage "
            f"still meets threshold — review the fact_pack or remove these claims")

    return rep


# CLI: --validate-only flag per kimi's A6 proposal
def main() -> int:
    import argparse, json
    p = argparse.ArgumentParser(description="Pre-flight fact-pack validation for arabic-authoring-suite")
    p.add_argument("--outline", required=True, help="Path to outline JSON")
    p.add_argument("--fact-pack", required=True, help="Path to fact-pack text file")
    p.add_argument("--content-type", default="article",
                   choices=["article", "book-chapter", "course-module", "news"])
    p.add_argument("--min-coverage", type=float, default=0.5,
                   help="Minimum overall grounded/total ratio (default 0.5)")
    p.add_argument("--min-keywords-per-claim", type=int, default=2)
    p.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable")
    args = p.parse_args()

    outline = json.loads(open(args.outline, encoding="utf-8").read())
    fact_pack = open(args.fact_pack, encoding="utf-8").read()
    rep = validate_fact_pack(outline, fact_pack, args.content_type,
                             args.min_coverage, args.min_keywords_per_claim)
    if args.json:
        print(json.dumps(rep.as_dict(), ensure_ascii=False, indent=2))
    else:
        status = "OK" if rep.ok else "REJECTED"
        print(f"Fact-pack validation: {status}")
        print(f"  overall coverage: {rep.overall_coverage:.1%} ({rep.grounded_claims}/{rep.total_claims} claims grounded)")
        for sec in rep.section_coverage:
            r = sec["ratio"]
            r_s = f"{r:.0%}" if r is not None else "n/a"
            print(f"  section[{sec['index']}] '{sec['name']}': {sec['claims_grounded']}/{sec['claims_total']} = {r_s}")
        if rep.errors:
            print(f"\n  ERRORS ({len(rep.errors)}):")
            for e in rep.errors: print(f"    - {e}")
        if rep.warnings:
            print(f"\n  WARNINGS ({len(rep.warnings)}):")
            for w in rep.warnings[:10]: print(f"    - {w}")
        if rep.ungrounded_claims:
            print(f"\n  UNGROUNDED claims ({len(rep.ungrounded_claims)}):")
            for u in rep.ungrounded_claims[:5]:
                print(f"    - section[{u['section_index']}] '{u['section_name']}': "
                      f"{u['claim']!r}")
                print(f"      keywords: {u['keywords_extracted']}")
                print(f"      found in fact_pack: {u['keywords_found_in_factpack']}/"
                      f"{u['keywords_required']} required")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
