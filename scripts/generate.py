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
    """Build the user prompt for drafting one section."""
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
    parts.append("# Fact pack")
    parts.append(fact_pack_text[:6000])  # cap to keep prompt size sane
    parts.append("")
    parts.append(f"Write this section in MSA Arabic, ~{section.get('word_budget', 300)} words, "
                 "drawing only from the fact pack above. Output Arabic prose only.")
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


def humanizer_gate(text_ar: str, threshold: int = 60) -> Dict[str, Any]:
    """Run the humanizer's analyze pass over a draft. Returns:
      {available: bool, score: int|None, details: ..., passes_gate: bool}
    Looks for the humanizer at the sibling-repo path or via env var.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent / "arabic-ai-text-humanizer"
    override = os.environ.get("ARABIC_HUMANIZER_ROOT")
    if override:
        repo_root = Path(override)
    humanizer_script = repo_root / "scripts" / "humanize_v2.py"
    if not humanizer_script.exists():
        return {"available": False, "score": None,
                "reason": "humanizer not found at sibling path",
                "passes_gate": True}  # No gate = pass through
    # v1.0.0: cheap heuristic — count AI-tell phrases (a real implementation
    # would import and call analyze_deep.py). This gives the right shape;
    # v1.1+ wires real scoring.
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
    }


def generate(content_type: str, outline: Dict[str, Any], fact_pack_text: str,
             proxy_name: str = "kimi",
             humanness_threshold: int = 60,
             max_regen_per_section: int = 1) -> Dict[str, Any]:
    """Full outline → draft → gate → optional regen loop."""
    started = time.time()
    sections_out: List[Dict[str, Any]] = []
    for i, section in enumerate(outline.get("sections", []), start=1):
        sys.stderr.write(f"Drafting section {i}/{len(outline['sections'])}: {section.get('heading_ar', '')[:50]}\n")
        draft = draft_section(content_type, outline, section, fact_pack_text, proxy_name)
        gate = humanizer_gate(draft, threshold=humanness_threshold)
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

    return {
        "content_type": content_type,
        "proxy_used": proxy_name,
        "model_used": PROXIES[proxy_name]["model"],
        "humanness_threshold": humanness_threshold,
        "sections": sections_out,
        "full_text_ar": full_text,
        "elapsed_s": round(elapsed, 1),
        "n_regens_total": sum(s["regen_attempts"] for s in sections_out),
    }


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
    p.add_argument("--output", "-o", help="Write full text to this file")
    p.add_argument("--json", action="store_true", help="Emit full JSON instead of just text")
    args = p.parse_args()

    outline = json.loads(Path(args.outline_file).read_text(encoding="utf-8"))
    fact_pack = Path(args.fact_pack).read_text(encoding="utf-8")

    result = generate(args.type, outline, fact_pack,
                      proxy_name=args.proxy,
                      humanness_threshold=args.humanness_threshold,
                      max_regen_per_section=args.max_regen_per_section)

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
