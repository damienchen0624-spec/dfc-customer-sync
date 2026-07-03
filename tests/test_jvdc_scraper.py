#!/usr/bin/env python3
"""巨懂车解析逻辑的离线单测。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import jvdc_scraper  # noqa: E402


class FilterNewLeadsTest(unittest.TestCase):
    def test_keeps_only_leads_newer_than_since(self):
        rows = [
            {"phone": "111", "leave_time": "2026-06-24 11:43"},
            {"phone": "222", "leave_time": "2026-06-23 22:58"},
            {"phone": "333", "leave_time": "2026-06-23 22:12"},
        ]
        result = jvdc_scraper.filter_new_leads(rows, since="2026-06-23 22:30")
        phones = [r["phone"] for r in result]
        self.assertEqual(phones, ["111", "222"])

    def test_none_since_keeps_all(self):
        rows = [{"phone": "111", "leave_time": "2026-06-24 11:43"}]
        result = jvdc_scraper.filter_new_leads(rows, since=None)
        self.assertEqual(len(result), 1)

    def test_lead_type_filter(self):
        rows = [
            {"phone": "111", "leave_time": "2026-06-24 11:43", "lead_type": "表单线索"},
            {"phone": "222", "leave_time": "2026-06-24 11:40", "lead_type": "其他"},
        ]
        result = jvdc_scraper.filter_lead_types(rows, allowed=["表单线索"])
        self.assertEqual([r["phone"] for r in result], ["111"])

    def test_empty_allowed_keeps_all(self):
        rows = [{"phone": "111", "lead_type": "其他"}]
        result = jvdc_scraper.filter_lead_types(rows, allowed=[])
        self.assertEqual(len(result), 1)


class NormalizePhoneTest(unittest.TestCase):
    def test_strips_whitespace_and_labels(self):
        self.assertEqual(jvdc_scraper.normalize_phone("手机：17631845820"), "17631845820")
        self.assertEqual(jvdc_scraper.normalize_phone(" 17631845820 "), "17631845820")

    def test_returns_empty_for_invalid(self):
        self.assertEqual(jvdc_scraper.normalize_phone("--"), "")


class ParseRowFallbackTest(unittest.TestCase):
    def test_parse_row_uses_text_fallbacks(self):
        class FakeNode:
            def __init__(self, text):
                self._text = text

            def inner_text(self):
                return self._text

        class FakeRow:
            def __init__(self, text_map, full_text):
                self.text_map = text_map
                self.full_text = full_text

            def query_selector(self, selector):
                text = self.text_map.get(selector)
                return FakeNode(text) if text is not None else None

            def inner_text(self):
                return self.full_text

        row = FakeRow(
            text_map={},
            full_text="客户 手机：17631845820 2026-06-24 11:43 来源 抖音 表单线索",
        )
        parsed = jvdc_scraper._parse_row(row)
        self.assertEqual(parsed["phone"], "17631845820")
        self.assertEqual(parsed["leave_time"], "2026-06-24 11:43")
        self.assertEqual(parsed["source"], "抖音")
        self.assertEqual(parsed["lead_type"], "")


if __name__ == "__main__":
    unittest.main()
