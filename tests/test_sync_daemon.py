#!/usr/bin/env python3
"""守护进程编排逻辑的离线单测。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_daemon  # noqa: E402


class FakeClient:
    def __init__(self, existing=None, fail_phones=None):
        self.existing = set(existing or [])
        self.fail_phones = set(fail_phones or [])
        self.added = []
        self.skipped_phones = []

    def add_customer(self, lead, follower_mapping=None):
        """模拟 DfcClient.add_customer 的返回格式。"""
        if lead["phone"] in self.fail_phones:
            return {"ok": False, "error": {"kind": "business", "message": "failed"}}
        self.added.append(lead["phone"])
        return {"ok": True, "customer_id": "mock_" + lead["phone"]}


class ProcessLeadsTest(unittest.TestCase):
    def test_adds_new_skips_existing_counts_failures(self):
        state = {"last_sync_time": None, "synced_phones": set(), "stats": {}}
        leads = [
            {"phone": "111", "leave_time": "2026-06-24 11:43"},
            {"phone": "222", "leave_time": "2026-06-24 11:40"},  # 本地已有
            {"phone": "333", "leave_time": "2026-06-24 11:30"},  # 写入失败
        ]
        client = FakeClient(fail_phones=["333"])
        result = sync_daemon.process_leads(leads, client, state)

        self.assertEqual(result["synced"], 2)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertIn("111", state["synced_phones"])
        self.assertIn("222", state["synced_phones"])
        self.assertNotIn("333", state["synced_phones"])  # 失败的不记入，下轮重试

    def test_skips_locally_synced(self):
        state = {"last_sync_time": None, "synced_phones": {"111"}, "stats": {}}
        leads = [{"phone": "111", "leave_time": "2026-06-24 11:43"}]
        client = FakeClient()
        result = sync_daemon.process_leads(leads, client, state)
        self.assertEqual(result["synced"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(client.added, [])

    def test_advances_last_sync_time_to_newest(self):
        state = {"last_sync_time": "2026-06-23", "synced_phones": set(), "stats": {}}
        leads = [
            {"phone": "111", "leave_time": "2026-06-24 11:43"},
            {"phone": "222", "leave_time": "2026-06-24 11:40"},
        ]
        client = FakeClient()
        sync_daemon.process_leads(leads, client, state)
        # 全部成功时水位线推到最晚时间 + 1 分钟（避免 >= 幽灵记录）
        self.assertEqual(state["last_sync_time"], "2026-06-24 11:44")

    def test_rolls_back_on_failure(self):
        # 失败记录的 leave_time 会影响水位线，确保下轮能重试
        state = {"last_sync_time": None, "synced_phones": set(), "stats": {}}
        leads = [
            {"phone": "111", "leave_time": "2026-06-24 11:43"},  # 成功
            {"phone": "222", "leave_time": "2026-06-24 11:40"},  # 失败
            {"phone": "333", "leave_time": "2026-06-24 11:30"},  # 成功
        ]
        client = FakeClient(fail_phones=["222"])
        sync_daemon.process_leads(leads, client, state)
        # 水位线回退到最早失败记录的时间
        self.assertEqual(state["last_sync_time"], "2026-06-24 11:40")
        self.assertNotIn("222", state["synced_phones"])
        # 下轮 filter 仍能抓到 222
        import jvdc_scraper
        re_fetched = jvdc_scraper.filter_new_leads(leads, since=state["last_sync_time"])
        self.assertIn("222", [r["phone"] for r in re_fetched])


if __name__ == "__main__":
    unittest.main()
