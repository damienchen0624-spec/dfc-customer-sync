#!/usr/bin/env python3
"""状态管理的离线单测。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import state  # noqa: E402


class StateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.path = Path(self.tmp.name)
        self.tmp.close()
        self.path.unlink()  # 删掉，测试"文件不存在"分支

    def tearDown(self):
        if self.path.exists():
            self.path.unlink()

    def test_load_missing_returns_empty_state(self):
        s = state.load_state(self.path)
        self.assertIsNone(s["last_sync_time"])
        self.assertEqual(s["synced_phones"], set())

    def test_save_then_load_roundtrip(self):
        s = state.load_state(self.path)
        s["last_sync_time"] = "2026-06-24T14:30:00"
        s["synced_phones"].add("17631845820")
        state.save_state(self.path, s)

        s2 = state.load_state(self.path)
        self.assertEqual(s2["last_sync_time"], "2026-06-24T14:30:00")
        self.assertIn("17631845820", s2["synced_phones"])

    def test_synced_phones_serialized_as_list(self):
        s = state.load_state(self.path)
        s["synced_phones"].add("13900139001")
        state.save_state(self.path, s)
        raw = json.loads(self.path.read_text())
        self.assertIsInstance(raw["synced_phones"], list)

    def test_is_synced(self):
        s = state.load_state(self.path)
        s["synced_phones"].add("17631845820")
        self.assertTrue(state.is_synced(s, "17631845820"))
        self.assertFalse(state.is_synced(s, "00000000000"))


if __name__ == "__main__":
    unittest.main()
