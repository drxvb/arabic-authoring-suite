#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smoke_test_schemas.py — v0.1.1 release gate.

Builds one valid + one deliberately invalid outline per content type and runs
the validator. Confirms the schemas in templates/ and the validator in
validate_outline.py agree. Exits non-zero if any case behaves wrong.

Not a true eval suite — that lands in v0.2 with adversarial bad-brief samples.
This is the release gate for v0.1.1's schema/validator pair.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_outline import validate_outline_file


def _write_tmp(outline: dict) -> Path:
    fd = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(outline, fd, ensure_ascii=False)
    fd.close()
    return Path(fd.name)


VALID = {
    "article": {
        "type": "article",
        "title_ar": "نمو قطاع التقنية في المملكة",
        "register": "news",
        "fact_pack_ref": "./brief.md",
        "sections": [
            {
                "heading_ar": "المشهد الراهن",
                "intent": "تأطير حجم القطاع وحصته من الناتج المحلي حتى نهاية 2025.",
                "source_refs": ["[1]", "[2]"],
                "word_budget": 350,
            },
            {
                "heading_ar": "الاستثمار الأجنبي",
                "intent": "عرض تدفقات الاستثمار وأثرها على التوظيف المحلي.",
                "source_refs": ["[3]"],
                "word_budget": 400,
            },
        ],
    },
    "book-chapter": {
        "type": "book-chapter",
        "title_ar": "أساسيات النحو العربي الحديث",
        "chapter_number": 3,
        "register": "classical",
        "fact_pack_ref": "./brief.md",
        "sections": [
            {"heading_ar": "تمهيد",       "intent": "ضبط المصطلحات وتوضيح حدود الفصل.",
             "source_refs": ["[1]", "[2]"], "word_budget": 600},
            {"heading_ar": "أقسام الكلمة","intent": "عرض تقسيم الكلمة الثلاثي مع أمثلة من النصوص الكلاسيكية.",
             "source_refs": ["[1]", "[3]", "[4]"], "word_budget": 1200},
            {"heading_ar": "الإعراب",     "intent": "شرح علامات الإعراب الأصلية والفرعية مع جداول مرجعية.",
             "source_refs": ["[5]", "[6]"], "word_budget": 1500},
            {"heading_ar": "خاتمة",       "intent": "تلخيص نقاط الفصل وربطها بفصل الصرف اللاحق مع توصيات للقارئ.",
             "source_refs": ["[7]", "[8]"], "word_budget": 500},
        ],
    },
    "course-module": {
        "type": "course-module",
        "title_ar": "مدخل إلى أساسيات بايثون",
        "register": "technical",
        "fact_pack_ref": "./brief.md",
        "learning_objectives": [
            "أن يكون المتعلم قادرا على كتابة دوال بايثون بسيطة.",
            "أن يميز المتعلم بين القائمة والمجموعة والقاموس.",
        ],
        "prerequisites": [],
        "sections": [
            {"heading_ar": "ما هو المتغير؟", "intent": "تعريف المتغيرات والنطاق.",
             "pedagogical_role": "concept", "source_refs": ["[1]"], "word_budget": 400},
            {"heading_ar": "مثال عملي",      "intent": "تطبيق المفاهيم في برنامج صغير.",
             "pedagogical_role": "example", "source_refs": [], "word_budget": 350},
            {"heading_ar": "خلاصة",          "intent": "ربط المفاهيم بهدف الوحدة.",
             "pedagogical_role": "synthesis", "source_refs": ["[2]"], "word_budget": 250},
        ],
        "exercises": [
            {"prompt_ar": "اكتب دالة تعيد مجموع قائمة.", "difficulty": "beginner",
             "answer_key_ar": "def s(L): return sum(L)"},
            {"prompt_ar": "ميز قائمة من مجموعة بمثال.",  "difficulty": "intermediate",
             "answer_key_ar": "القائمة مرتبة وتقبل التكرار؛ المجموعة لا تقبل التكرار."},
            {"prompt_ar": "صمم قاموسا لتمثيل طالب.",     "difficulty": "advanced",
             "answer_key_ar": "{'name': 'A', 'gpa': 3.7, 'courses': [...]}"},
        ],
    },
    "news": {
        "type": "news",
        "headline_ar": "افتتاح معرض الكتاب الدولي بالرياض",
        "lede_ar": "افتتح وزير الثقافة معرض الرياض الدولي للكتاب اليوم الخميس، بمشاركة أكثر من ألف دار نشر.",
        "register": "news",
        "fact_pack_ref": "./brief.md",
        "five_w_h": {
            "who_ar": "وزير الثقافة",
            "what_ar": "افتتاح معرض الكتاب الدولي",
            "when_ar": "اليوم الخميس",
            "where_ar": "الرياض",
        },
        "sections": [
            {"intent": "تغطية الافتتاح والبرنامج الرئيسي.", "source_refs": ["[1]"], "word_budget": 300},
        ],
    },
}


# Each invalid case mutates VALID in one specific way and expects an error mentioning a known substring.
INVALID = [
    ("article",      "remove required field 'title_ar'",
     lambda o: {k: v for k, v in o.items() if k != "title_ar"}, "title_ar"),
    ("article",      "1 section (below minItems=2)",
     lambda o: {**o, "sections": o["sections"][:1]}, "minItems"),
    ("article",      "empty source_refs in section",
     lambda o: {**o, "sections": [{**o["sections"][0], "source_refs": []}, o["sections"][1]]},
     "minItems"),
    ("book-chapter", "section with only 1 source (below minItems=2)",
     lambda o: {**o, "sections": [{**o["sections"][0], "source_refs": ["[1]"]}] + o["sections"][1:]},
     "minItems"),
    ("book-chapter", "wrong register enum",
     lambda o: {**o, "register": "news"}, "enum"),
    ("course-module","exercise missing answer_key_ar",
     lambda o: {**o, "exercises": [{k: v for k, v in o["exercises"][0].items() if k != "answer_key_ar"}] + o["exercises"][1:]},
     "answer_key_ar"),
    ("course-module","only 1 learning_objective (below minItems=2)",
     lambda o: {**o, "learning_objectives": o["learning_objectives"][:1]}, "minItems"),
    ("news",         "five_w_h missing required where_ar",
     lambda o: {**o, "five_w_h": {k: v for k, v in o["five_w_h"].items() if k != "where_ar"}},
     "where_ar"),
    ("news",         "bad dateline date format",
     lambda o: {**o, "dateline": {"location_ar": "الرياض", "date_iso": "May 28, 2026"}},
     "pattern"),
]


def main() -> int:
    failed = 0

    print("=== Positive cases (4 valid outlines) ===")
    for ctype, outline in VALID.items():
        path = _write_tmp(outline)
        errs, resolved = validate_outline_file(path, None)
        path.unlink()
        status = "PASS" if not errs else f"FAIL ({len(errs)} errors)"
        print(f"  {ctype:<15} -> {status}")
        if errs:
            failed += 1
            for e in errs:
                print(f"      {e}")

    print("\n=== Negative cases (deliberate violations) ===")
    for ctype, description, mutator, expected_substring in INVALID:
        bad = mutator(VALID[ctype])
        path = _write_tmp(bad)
        errs, resolved = validate_outline_file(path, None if "type" in bad else ctype)
        path.unlink()
        if not errs:
            print(f"  {ctype:<15} {description!r} -> FAIL (validator missed the error)")
            failed += 1
            continue
        if not any(expected_substring in e for e in errs):
            print(f"  {ctype:<15} {description!r} -> FAIL (got errors but not the expected {expected_substring!r})")
            for e in errs:
                print(f"      {e}")
            failed += 1
            continue
        print(f"  {ctype:<15} {description!r} -> caught ({expected_substring})")

    print()
    if failed:
        print(f"FAILED: {failed} smoke-test case(s) wrong.")
        return 1
    print(f"OK: all {len(VALID)} positive + {len(INVALID)} negative cases behaved correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
