#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_outline.py — Validate an outline JSON file against its content-type schema.

Stdlib-only JSON Schema validator covering the subset used by the four outline
schemas in templates/: type, required, properties, items, minItems, maxItems,
minLength, maxLength, minimum, maximum, enum, const, pattern, $ref, additionalProperties,
$defs. NOT a full draft-2020-12 implementation — adding the missing pieces (oneOf,
anyOf, allOf, dependentRequired, prefixItems, contains, etc.) is on the v0.2 list
if the four schemas grow to need them.

Usage:
    python validate_outline.py article-outline.json
    python validate_outline.py --type article article-outline.json
    python validate_outline.py --list-schemas
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
SCHEMA_BY_TYPE = {
    "article": "article.outline.json",
    "book-chapter": "book-chapter.outline.json",
    "course-module": "course-module.outline.json",
    "news": "news.outline.json",
}


def _resolve_ref(ref: str, root_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve a local $ref like '#/$defs/section' against root_schema. No remote refs."""
    if not ref.startswith("#/"):
        raise ValueError(f"only local $refs supported, got: {ref}")
    cur: Any = root_schema
    for part in ref[2:].split("/"):
        # JSON Pointer unescape (~1 -> /, ~0 -> ~)
        part = part.replace("~1", "/").replace("~0", "~")
        cur = cur[part]
    return cur


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":  return isinstance(value, dict)
    if expected == "array":   return isinstance(value, list)
    if expected == "string":  return isinstance(value, str)
    if expected == "integer": return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":  return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean": return isinstance(value, bool)
    if expected == "null":    return value is None
    return False


def _validate(instance: Any, schema: Dict[str, Any], root: Dict[str, Any],
              path: str = "$") -> List[str]:
    """Return a list of error strings. Empty list = valid."""
    errs: List[str] = []

    if "$ref" in schema:
        return _validate(instance, _resolve_ref(schema["$ref"], root), root, path)

    if "const" in schema and instance != schema["const"]:
        errs.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
        return errs

    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: value {instance!r} not in enum {schema['enum']}")
        return errs

    if "type" in schema:
        expected = schema["type"]
        if isinstance(expected, list):
            if not any(_type_matches(instance, e) for e in expected):
                errs.append(f"{path}: type {type(instance).__name__} not in {expected}")
                return errs
        elif not _type_matches(instance, expected):
            errs.append(f"{path}: expected type {expected}, got {type(instance).__name__}")
            return errs

    # String constraints
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errs.append(f"{path}: string length {len(instance)} < minLength {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errs.append(f"{path}: string length {len(instance)} > maxLength {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errs.append(f"{path}: string does not match pattern {schema['pattern']!r}")

    # Numeric constraints
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errs.append(f"{path}: {instance} > maximum {schema['maximum']}")

    # Object constraints
    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errs.append(f"{path}: required property {req!r} missing")
        props = schema.get("properties", {})
        for key, val in instance.items():
            sub_path = f"{path}.{key}"
            if key in props:
                errs.extend(_validate(val, props[key], root, sub_path))
            elif schema.get("additionalProperties") is False:
                errs.append(f"{sub_path}: additional property not allowed")

    # Array constraints
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errs.append(f"{path}: array length {len(instance)} < minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errs.append(f"{path}: array length {len(instance)} > maxItems {schema['maxItems']}")
        if "items" in schema:
            for i, item in enumerate(instance):
                errs.extend(_validate(item, schema["items"], root, f"{path}[{i}]"))

    return errs


def validate_outline_file(outline_path: Path, content_type: str = None) -> Tuple[List[str], str]:
    """Return (errors, resolved_type)."""
    try:
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return ([f"outline file is not valid JSON: {e}"], "")
    except OSError as e:
        return ([f"could not read outline file: {e}"], "")

    if content_type is None:
        content_type = outline.get("type")
        if content_type is None:
            return ([
                "outline has no 'type' field and --type was not given; "
                f"expected one of {sorted(SCHEMA_BY_TYPE)}"
            ], "")

    schema_filename = SCHEMA_BY_TYPE.get(content_type)
    if schema_filename is None:
        return ([f"unknown content type: {content_type}. Known: {sorted(SCHEMA_BY_TYPE)}"], content_type)

    schema_path = TEMPLATES_DIR / schema_filename
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except OSError as e:
        return ([f"could not read schema {schema_path}: {e}"], content_type)

    return (_validate(outline, schema, schema), content_type)


def main() -> int:
    p = argparse.ArgumentParser(description="Validate an outline against its content-type schema")
    p.add_argument("outline", nargs="?", help="Path to outline JSON file")
    p.add_argument("--type", choices=list(SCHEMA_BY_TYPE),
                   help="Content type (otherwise inferred from outline's 'type' field)")
    p.add_argument("--list-schemas", action="store_true",
                   help="List available schemas and exit")
    args = p.parse_args()

    if args.list_schemas:
        for t, fname in SCHEMA_BY_TYPE.items():
            print(f"  {t:<15} -> templates/{fname}")
        return 0

    if not args.outline:
        p.error("outline path required (or use --list-schemas)")

    errors, resolved_type = validate_outline_file(Path(args.outline), args.type)
    if errors:
        print(f"INVALID ({resolved_type or 'unknown'}): {len(errors)} error(s)", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"OK: outline conforms to {resolved_type} schema.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
