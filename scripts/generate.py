#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate.py — v1.0.0 outline→draft→revise loop.

Given an approved outline + fact pack, calls the LAN-local LLM proxy fleet
(`M:\\Main\\DevTools\\AI\\config\\llm-proxies.md`) to draft each section.
Optional humanizer-gate post-pass rewrites sections whose humanness score
falls below the per-type threshold (a "gate," not a "polish" — per Agent C's
v2.6.0 multi-agent review architecture).

Python 3 stdlib only (urllib.request for HTTP).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# Proxy registry — matches arabic-corpus-toolkit/scripts/pair_terminology.py.
# All four are LAN-local and free at runtime.
PROXIES = {
    "kimi":    {"url": "http://192.168.80.107:11435", "key": "U6hI7j57HpRpz9QaafTJLsJw5PlTXtxBM4pVNTknohE", "model": "kimi-cli"},
    "codex":   {"url": "http://192.168.80.107:11436", "key": "VJyi6yQDhEGNDE999FkHTqBAG21KdzmW",     "model": "gpt-5.5"},
    "gemini":  {"url": "http://192.168.80.107:11437", "key": "6fjc4jGwIhXQn7NejizvFVKR7Ps1SXES",     "model": "gemini-2.5-flash"},
    "minimax": {"url": "http://192.168.80.107:11438", "key": "xL5jUNR9A2lhN5HfLt1ulp9gE2CnBKf4",     "model": "MiniMax-M2.7"},
}


SECTION_SYSTEM_PROMPT_BY_TYPE = {
    "article": (
        "You are a professional Arabic news writer for Saudi/Gulf publications. "
        "Write naturally in MSA (modern standard Arabic), in the news register. "
        "Avoid AI-typical phrases: من المهم ملاحظة، علاوة على ذلك، تجدر الإشارة. "
        "Use specific facts from the provided sources; do not invent quotes or statistics. "
        "Output ONLY the Arabic prose — no English commentary, no markdown headings, "
        "no introduction like 'here is the article'."
    ),
    "book-chapter": (
        "You are a scholarly Arabic writer in classical/فصحى register. "
        "Write at the level of academic Arabic publishing. "
        "Use precise terminology, classical sentence structures, varied connectors. "
        "Avoid AI-typical mechanical hedges (من المهم ملاحظة، تجدر الإشارة، "
        "علاوة على ذلك) and ring-composition openers. "
        "Cite sources by reference number in brackets [N]. Output ONLY Arabic prose."
    ),
    "course-module": (
        "You are an Arabic technical-education writer. "
        "Write clear instructional Arabic — define terms, give examples, "
        "use the technical register without being stiff. "
        "Avoid AI-typical hedges (من المهم ملاحظة، تجدر الإشارة). "
        "Output ONLY Arabic prose."
    ),
    "news": (
        "You are an Arabic newswire journalist. "
        "Inverted-pyramid structure: who/what/when/where in the lede, "
        "supporting details after. Active voice. "
        "Avoid AI-typical phrases (من المهم ملاحظة، علاوة على ذلك، تجدر الإشارة، "
        "في غاية الأهمية). "
        "Output ONLY Arabic prose, no English."
    ),
}


# v1.0.1: Asset G (toolkit's paired EN<->AR terminology) consumption.
# When drafting, scan the fact pack + section intent for English terms whose
# AR translation is corpus-attested, and inject as terminology hints in the
# prompt so the LLM uses consistent terminology across sections.

def _toolkit_root() -> Optional[Path]:
    override = os.environ.get("ARABIC_CORPUS_TOOLKIT_ROOT")
    candidates = []
    if override:
        candidates.append(Path(override))
    candidates.append(Path(__file__).resolve().parent.parent.parent / "arabic-corpus-toolkit")
    for c in candidates:
        if (c / "corpus" / "domain-terminology.json").exists():
            return c
    return None


_asset_g_cache: Dict[str, Optional[Dict[str, Any]]] = {}


# v1.5.0: Gap G2 adoption — route compat checks through toolkit asset_registry
# with legacy major-version fallback.
def _registry_is_compatible(asset_id: str, observed_version: str) -> bool:
    """Route to toolkit asset_registry.is_compatible() (v1.6.0+) with
    legacy major-version fallback when registry import fails."""
    tk = _toolkit_root()
    if tk is None:
        return observed_version.split(".")[0] == "1"
    try:
        scripts_dir = tk / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from asset_registry import is_compatible  # type: ignore
        return is_compatible(asset_id, observed_version)
    except Exception:
        return observed_version.split(".")[0] == "1"


# v1.5.0: Gap G3 adoption — create InfluenceTrace if toolkit v1.7.0+ available.
def _new_authoring_trace():
    """Returns a fresh InfluenceTrace or None."""
    tk = _toolkit_root()
    if tk is None:
        return None
    try:
        scripts_dir = tk / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from influence_telemetry import InfluenceTrace  # type: ignore
        return InfluenceTrace()
    except Exception:
        return None


def _load_asset_g(domain: str = "technology") -> Optional[Dict[str, Any]]:
    """Load paired EN<->AR terminology for the given domain. None if unavailable.
    Same domain-keyed pattern as translator v1.0.1."""
    if domain in _asset_g_cache:
        return _asset_g_cache[domain]
    tk = _toolkit_root()
    if tk is None:
        _asset_g_cache[domain] = None
        return None
    fname = "domain-terminology.json" if domain == "technology" else f"domain-terminology-{domain}.json"
    p = tk / "corpus" / fname
    if not p.exists():
        _asset_g_cache[domain] = None
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        _asset_g_cache[domain] = None
        return None
    # v1.5.0: route through toolkit asset_registry (G2 adoption) with legacy
    # major-version fallback when registry import fails (toolkit pre-v1.6.0).
    observed = data.get("$schema_version", "0.0.0")
    if not _registry_is_compatible(f"G.{domain}", observed):
        _asset_g_cache[domain] = None
        return None
    by_en = {p.get("en", "").strip().lower(): p for p in data.get("pairs", []) if p.get("en")}
    data["_by_en"] = by_en
    _asset_g_cache[domain] = data
    return data


def _find_terminology_hits(text: str, domain: str,
                            trace=None) -> List[Dict[str, Any]]:
    """Whole-word EN scan of text against Asset G for the given domain.
    v1.5.0: if a trace is provided, record each term hit as an influence
    record citing G.{domain} + the term_hint_injected trigger."""
    data = _load_asset_g(domain)
    if data is None or not text:
        return []
    text_lower = text.lower()
    by_en = data.get("_by_en", {})
    asset_version = data.get("$schema_version", "unknown")
    hits = []
    seen = set()
    for en in sorted(by_en.keys(), key=len, reverse=True):
        if en in seen:
            continue
        if re.search(r"\b" + re.escape(en) + r"\b", text_lower):
            pair = by_en[en]
            hits.append(pair)
            seen.add(en)
            if trace is not None:
                trace.record(
                    asset_id=f"G.{domain}", asset_version=asset_version,
                    trigger="term_hint_injected",
                    evidence={"en": pair.get("en"), "ar": pair.get("ar")},
                    stage="prompt_construction",
                )
    return hits


# Map content type -> terminology domain.
# v1.3.1: defaults preserved for backward compat, but consumers can override
# per-call via the outline's `terminology_domain` field. Sonnet's evaluator
# audit flagged this hardcoding: "A book chapter on Saudi labor law gets
# injected with 5G/IoT terminology hints because article/book-chapter both
# default to technology domain."
CONTENT_TYPE_TO_DOMAIN = {
    "article": "technology",       # most authored articles are tech in our corpus
    "book-chapter": "technology",  # override via outline.terminology_domain="legal" etc.
    "course-module": "technology",
    "news": "news",
}


def _resolve_terminology_domain(content_type: str, outline: Dict[str, Any]) -> str:
    """v1.3.1: explicit outline override beats per-content-type default.
    Outline can carry `terminology_domain: "legal"` etc. to escape the
    hardcoded technology default."""
    explicit = (outline or {}).get("terminology_domain")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    return CONTENT_TYPE_TO_DOMAIN.get(content_type, "technology")


def _call_proxy(proxy_name: str, system_prompt: str, user_prompt: str,
                timeout: int = 180, temperature: float = 0.3) -> Optional[str]:
    """POST to a proxy; return assistant content or None."""
    p = PROXIES.get(proxy_name)
    if p is None:
        return None
    body = json.dumps({
        "model": p["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": temperature,
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        url=p["url"] + "/v1/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {p['key']}",
            "Content-Type":  "application/json; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as e:
        sys.stderr.write(f"  [{proxy_name}] error: {e}\n")
        return None


def _build_section_prompt(content_type: str, outline: Dict[str, Any],
                          section: Dict[str, Any], fact_pack_text: str) -> str:
    """Build the user prompt for drafting one section.
    v1.0.1: injects Asset G terminology hints for any EN tech/news term that
    appears in the fact pack."""
    parts = []
    parts.append(f"# Outline context")
    parts.append(f"Content type: {content_type}")
    if outline.get("title_ar"):
        parts.append(f"Title: {outline['title_ar']}")
    if outline.get("register"):
        parts.append(f"Register: {outline['register']}")
    parts.append("")
    parts.append("# This section")
    if section.get("heading_ar"):
        parts.append(f"Heading: {section['heading_ar']}")
    parts.append(f"Intent: {section.get('intent', '')}")
    parts.append(f"Word budget: ~{section.get('word_budget', 300)} words")
    if section.get("source_refs"):
        parts.append(f"Source refs to draw from: {', '.join(section['source_refs'])}")
    if section.get("claims"):
        parts.append("Specific claims to support:")
        for c in section["claims"]:
            parts.append(f"  - {c}")
    parts.append("")

    # v1.0.1: terminology hints from Asset G
    # v1.3.1: domain resolution prefers outline.terminology_domain override
    # v1.5.1: thread the trace from outline so emit_trace=True actually
    # produces influence records on the production code path (A4 Sonnet
    # killer finding: smoke test passed trace explicitly; production path
    # didn't; result was empty trace for the primary use case).
    domain = _resolve_terminology_domain(content_type, outline)
    scan_text = f"{outline.get('title_ar','')} {section.get('intent','')} {fact_pack_text[:6000]}"
    trace = outline.get("_trace") if isinstance(outline, dict) else None
    term_hits = _find_terminology_hits(scan_text, domain, trace=trace)
    if term_hits:
        parts.append(f"# Corpus-grounded terminology (use these exact AR forms — domain={domain})")
        for h in term_hits[:20]:  # cap to 20 hints
            parts.append(f"  - {h['en']} → {h['ar']}")
        parts.append("")

    parts.append("# Fact pack")
    parts.append(fact_pack_text[:6000])
    parts.append("")
    parts.append(f"Write this section in MSA Arabic, ~{section.get('word_budget', 300)} words, "
                 "drawing only from the fact pack above. "
                 "Use the corpus-grounded terminology mappings above for any term that appears in the prose. "
                 "Output Arabic prose only.")
    return "\n".join(parts)


def draft_section(content_type: str, outline: Dict[str, Any],
                  section: Dict[str, Any], fact_pack_text: str,
                  proxy_name: str = "kimi") -> str:
    """Draft a single section. Returns the Arabic prose."""
    system_prompt = SECTION_SYSTEM_PROMPT_BY_TYPE.get(
        content_type, SECTION_SYSTEM_PROMPT_BY_TYPE["article"]
    )
    user_prompt = _build_section_prompt(content_type, outline, section, fact_pack_text)
    response = _call_proxy(proxy_name, system_prompt, user_prompt)
    return (response or f"[GENERATION FAILED for section: {section.get('heading_ar', '')}]").strip()


def _arabic_char_ratio_via_toolkit(text: str) -> Optional[float]:
    """v1.4.0: route language detection through the toolkit's canonical
    arabic_normalize contract. Falls back to ad-hoc count if toolkit absent."""
    try:
        # Toolkit at sibling path; same resolution _toolkit_root uses
        tk = _toolkit_root()
        if tk is None:
            # Fallback: ad-hoc count (preserves v1.3.0 behavior when toolkit
            # is unavailable). Matches the formula in arabic_normalize.py.
            ar_chars = sum(1 for c in text if "؀" <= c <= "ۿ" and c.isalpha())
            total_letters = sum(1 for c in text if c.isalpha())
            return (ar_chars / total_letters) if total_letters > 0 else 0.0
        scripts_dir = tk / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from arabic_normalize import arabic_char_ratio  # type: ignore
        return arabic_char_ratio(text)
    except Exception:
        return None


def humanizer_gate(text_ar: str, threshold: int = 60, register: str = "news") -> Dict[str, Any]:
    """Score Arabic text via the humanizer's score_text() function (v2.9.0+).
    Falls back to a 6-tell heuristic if the humanizer isn't importable.

    Returns:
      {available, score, ai_tell_hits, ai_tell_density_per_1k, total_words,
       register, ai_phrases_caught, sample_size, threshold, passes_gate, backend}

    v1.1.0: uses humanizer.score_text (67 AI-phrases + 8 intensifier patterns).
    v1.0.0: used a hard-coded 6-tell heuristic.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent / "arabic-ai-text-humanizer"
    override = os.environ.get("ARABIC_HUMANIZER_ROOT")
    if override:
        repo_root = Path(override)
    humanizer_scripts = repo_root / "scripts"
    humanizer_module = humanizer_scripts / "humanize_v2.py"

    # v1.3.0: language sanity check — the score_text heuristic only counts
    # Arabic AI-tells, so an English output trivially scores 100 (false positive
    # surfaced by swarm mode). Penalize outputs that aren't predominantly Arabic.
    # v1.4.0: route through toolkit's arabic_normalize.is_arabic_dominant
    # (Gap G1 shared contract) instead of the ad-hoc inline ratio check.
    if text_ar:
        ratio = _arabic_char_ratio_via_toolkit(text_ar)
        if ratio is not None and ratio < 0.5:
            return {
                "available": True,
                "score": 0,
                "ai_tell_hits": 0,
                "total_words": len(text_ar.split()),
                "threshold": threshold,
                "passes_gate": False,
                "backend": "language_check_failed (via arabic_normalize)",
                "language_mismatch": True,
                "ar_char_ratio": round(ratio, 2),
                "reason": "output is not predominantly Arabic — likely English or mixed",
            }

    # Try the real humanizer first
    if humanizer_module.exists():
        try:
            if str(humanizer_scripts) not in sys.path:
                sys.path.insert(0, str(humanizer_scripts))
            from humanize_v2 import score_text as _score_text  # type: ignore
            result = _score_text(text_ar, register=register)
            result["threshold"] = threshold
            result["passes_gate"] = result.get("score", 0) >= threshold
            result["backend"] = "humanize_v2.score_text"
            result["available"] = True
            return result
        except Exception as e:
            # Fall through to heuristic
            sys.stderr.write(f"  humanizer import failed ({e}); falling back to heuristic\n")

    # Fallback: 6-tell heuristic (v1.0.0 behavior preserved when humanizer unavailable)
    AI_TELLS = ["من المهم ملاحظة", "علاوة على ذلك", "تجدر الإشارة",
                "في غاية الأهمية", "بشكل عام", "في الواقع"]
    hits = sum(text_ar.count(t) for t in AI_TELLS)
    total_words = max(1, len(text_ar.split()))
    score = max(0, 100 - int(hits * 1000 / total_words))
    return {
        "available": True,
        "score": score,
        "ai_tell_hits": hits,
        "total_words": total_words,
        "threshold": threshold,
        "passes_gate": score >= threshold,
        "backend": "heuristic_fallback (humanizer not importable)",
        "sample_size": len(AI_TELLS),
    }


def draft_section_swarm(content_type: str, outline: Dict[str, Any],
                         section: Dict[str, Any], fact_pack_text: str,
                         proxies: List[str]) -> Dict[str, Any]:
    """v1.3.0 cross-LLM swarm drafting: draft the section with each proxy,
    score each via the humanizer, return the best draft + all candidates.

    Returns {best_draft, best_proxy, best_score, candidates: [...]}.
    """
    candidates: List[Dict[str, Any]] = []
    for prx in proxies:
        d = draft_section(content_type, outline, section, fact_pack_text, prx)
        g = humanizer_gate(d, threshold=60)
        candidates.append({
            "proxy": prx,
            "draft_ar": d,
            "score": g.get("score", 0),
            "gate": g,
            "word_count": len(d.split()),
        })
    # Pick highest score, break ties on word count (longer ≈ more content)
    best = max(candidates, key=lambda c: (c["score"], c["word_count"]))
    return {
        "best_draft": best["draft_ar"],
        "best_proxy": best["proxy"],
        "best_score": best["score"],
        "candidates": candidates,
    }


# v1.5.0: hook for callers to opt into influence telemetry on generate().
# generate() will attach a fresh InfluenceTrace to outline["_trace"] and
# return its as_json() in the result under "influence_trace".
def generate(content_type: str, outline: Dict[str, Any], fact_pack_text: str,
             proxy_name: str = "kimi",
             humanness_threshold: int = 60,
             max_regen_per_section: int = 1,
             swarm_proxies: Optional[List[str]] = None,
             emit_trace: bool = False) -> Dict[str, Any]:
    """Full outline → draft → gate → optional regen loop.
    v1.5.0: when emit_trace=True, instantiates InfluenceTrace and threads it
    through prompt construction so every Asset G term hint is causally
    recorded. The serialized trace is returned in the result dict's
    influence_trace field."""
    started = time.time()
    sections_out: List[Dict[str, Any]] = []
    # v1.5.0: attach trace to outline so _find_terminology_hits can append
    trace = _new_authoring_trace() if emit_trace else None
    if trace is not None and isinstance(outline, dict):
        outline["_trace"] = trace
    for i, section in enumerate(outline.get("sections", []), start=1):
        sys.stderr.write(f"Drafting section {i}/{len(outline['sections'])}: {section.get('heading_ar', '')[:50]}\n")
        if swarm_proxies:
            sys.stderr.write(f"  Swarm mode: {len(swarm_proxies)} proxies competing\n")
            swarm = draft_section_swarm(content_type, outline, section, fact_pack_text, swarm_proxies)
            draft = swarm["best_draft"]
            gate = humanizer_gate(draft, threshold=humanness_threshold)
            swarm_meta = {
                "winning_proxy": swarm["best_proxy"],
                "winning_score": swarm["best_score"],
                "candidate_scores": {c["proxy"]: c["score"] for c in swarm["candidates"]},
            }
            sys.stderr.write(f"  Winner: {swarm['best_proxy']} (score={swarm['best_score']})\n")
        else:
            draft = draft_section(content_type, outline, section, fact_pack_text, proxy_name)
            gate = humanizer_gate(draft, threshold=humanness_threshold)
            swarm_meta = None
        attempts = 1
        # If gate fails AND we have regen budget, rewrite the section with a tightened prompt
        while not gate["passes_gate"] and attempts <= max_regen_per_section and gate.get("available"):
            sys.stderr.write(f"  Gate failed (score={gate.get('score')}); regen attempt {attempts}\n")
            # Tighten: prepend the AI-tell list as an avoid-set
            tight_intent = (section.get("intent", "") +
                            "\n\nIMPORTANT: avoid all of these AI-typical phrases: " +
                            "من المهم ملاحظة، علاوة على ذلك، تجدر الإشارة، في غاية الأهمية، بشكل عام، في الواقع.")
            tight_section = dict(section, intent=tight_intent)
            draft = draft_section(content_type, outline, tight_section, fact_pack_text, proxy_name)
            gate = humanizer_gate(draft, threshold=humanness_threshold)
            attempts += 1
        sections_out.append({
            "section_index": i,
            "heading_ar": section.get("heading_ar"),
            "draft_ar": draft,
            "humanizer_gate": gate,
            "regen_attempts": attempts - 1,
            "swarm": swarm_meta,
        })

    elapsed = time.time() - started
    # Assemble the full document
    full_text_lines = []
    if outline.get("title_ar"):
        full_text_lines.append(f"# {outline['title_ar']}")
        full_text_lines.append("")
    for s in sections_out:
        if s.get("heading_ar"):
            full_text_lines.append(f"## {s['heading_ar']}")
            full_text_lines.append("")
        full_text_lines.append(s["draft_ar"])
        full_text_lines.append("")
    full_text = "\n".join(full_text_lines)

    result = {
        "content_type": content_type,
        "proxy_used": proxy_name,
        "model_used": PROXIES[proxy_name]["model"],
        "humanness_threshold": humanness_threshold,
        "sections": sections_out,
        "full_text_ar": full_text,
        "elapsed_s": round(elapsed, 1),
        "n_regens_total": sum(s["regen_attempts"] for s in sections_out),
    }
    # v1.5.0: serialize influence trace if telemetry was enabled
    if trace is not None:
        result["influence_trace"] = trace.as_json()
        # Cleanup: remove trace ref from outline so callers don't see it
        if isinstance(outline, dict):
            outline.pop("_trace", None)
    return result


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="arabic-authoring-suite v1.0.0 — generate from outline + fact pack")
    p.add_argument("--type", required=True,
                   choices=list(SECTION_SYSTEM_PROMPT_BY_TYPE.keys()))
    p.add_argument("--outline-file", required=True, help="Approved outline JSON")
    p.add_argument("--fact-pack", required=True, help="Fact pack Markdown file")
    p.add_argument("--proxy", default="kimi", choices=list(PROXIES.keys()))
    p.add_argument("--humanness-threshold", type=int, default=60)
    p.add_argument("--max-regen-per-section", type=int, default=1)
    p.add_argument("--swarm", help="Comma-separated proxies to compete on each section "
                                    "(e.g., 'kimi,minimax,gemini'). Best score wins.")
    p.add_argument("--output", "-o", help="Write full text to this file")
    p.add_argument("--json", action="store_true", help="Emit full JSON instead of just text")
    args = p.parse_args()

    outline = json.loads(Path(args.outline_file).read_text(encoding="utf-8"))
    fact_pack = Path(args.fact_pack).read_text(encoding="utf-8")

    swarm = [s.strip() for s in args.swarm.split(",")] if args.swarm else None
    result = generate(args.type, outline, fact_pack,
                      proxy_name=args.proxy,
                      humanness_threshold=args.humanness_threshold,
                      max_regen_per_section=args.max_regen_per_section,
                      swarm_proxies=swarm)

    if args.output:
        Path(args.output).write_text(result["full_text_ar"], encoding="utf-8")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["full_text_ar"])
    sys.stderr.write(f"\nDone in {result['elapsed_s']}s, {result['n_regens_total']} total regens.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
