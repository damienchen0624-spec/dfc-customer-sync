#!/usr/bin/env python3
"""字段映射的离线单测。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mapping  # noqa: E402


class SourceMappingTest(unittest.TestCase):
    def test_known_source_maps_to_other(self):
        # v3.0: map_source 返回中文名
        self.assertEqual(mapping.map_source("懂车帝-店铺车源"), "其他")

    def test_douyin_source(self):
        self.assertEqual(mapping.map_source("抖音"), "抖音")

    def test_unknown_source_falls_back_to_other(self):
        self.assertEqual(mapping.map_source("未知渠道xyz"), "其他")

    def test_source_code_to_name(self):
        self.assertEqual(mapping.map_source_code_to_name("douyin"), "抖音")
        self.assertEqual(mapping.map_source_code_to_name("other"), "其他")
        self.assertEqual(mapping.map_source_code_to_name("unknown"), "其他")


class GradeMappingTest(unittest.TestCase):
    def test_explicit_grade_passthrough(self):
        self.assertEqual(mapping.map_grade("H", status=""), "H")
        self.assertEqual(mapping.map_grade("A", status="跟进中"), "A")

    def test_grade_falls_back_to_status_when_empty(self):
        self.assertEqual(mapping.map_grade("", status="未联系"), "C")
        self.assertEqual(mapping.map_grade("", status="跟进中"), "B")
        self.assertEqual(mapping.map_grade("", status="已成交"), "A")

    def test_grade_defaults_to_C_when_both_empty(self):
        self.assertEqual(mapping.map_grade("", status=""), "C")


class GenderMappingTest(unittest.TestCase):
    def test_gender_mapping(self):
        self.assertEqual(mapping.map_gender("male"), "先生")
        self.assertEqual(mapping.map_gender("female"), "女士")
        self.assertEqual(mapping.map_gender("unknown"), "未知")
        self.assertEqual(mapping.map_gender("先生"), "先生")
        self.assertEqual(mapping.map_gender(""), "未知")


class EnumDictsTest(unittest.TestCase):
    def test_source_dict_has_common_values(self):
        self.assertIn("直接到店", mapping.SOURCE)
        self.assertIn("抖音", mapping.SOURCE)
        self.assertIn("其他", mapping.SOURCE)

    def test_grade_dict_has_all_grades(self):
        for g in ["H", "A", "B", "C", "N"]:
            self.assertIn(g, mapping.GRADE)

    def test_gender_dict_has_all_genders(self):
        for g in ["先生", "女士", "未知"]:
            self.assertIn(g, mapping.GENDER)


if __name__ == "__main__":
    unittest.main()
