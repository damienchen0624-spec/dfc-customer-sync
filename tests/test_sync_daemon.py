#!/usr/bin/env python3
"""守护进程编排逻辑的离线单测。"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_daemon  # noqa: E402


class FakeClient:
    def __init__(self, existing=None, fail_phones=None, fail_kind="business"):
        self.existing = set(existing or [])
        self.fail_phones = set(fail_phones or [])
        self.fail_kind = fail_kind
        self.added = []

    def phone_exists_result(self, phone):
        if phone in self.existing:
            return {"ok": True, "exists": True, "error": None}
        return {"ok": True, "exists": False, "error": None}

    def add_customer_result(self, lead):
        if lead["phone"] in self.fail_phones:
            return {"ok": False, "error": {"kind": self.fail_kind, "message": "failed"}}
        self.added.append(lead["phone"])
        return {"ok": True, "error": None}


class ProcessLeadsTest(unittest.TestCase):
    def test_adds_new_skips_existing_counts_failures(self):
        state = {"last_sync_time": None, "synced_phones": set(), "stats": {}}
        leads = [
            {"phone": "111", "leave_time": "2026-06-24 11:43"},
            {"phone": "222", "leave_time": "2026-06-24 11:40"},  # 已在大风车
            {"phone": "333", "leave_time": "2026-06-24 11:30"},  # 写入失败
        ]
        client = FakeClient(existing=["222"], fail_phones=["333"])
        result = sync_daemon.process_leads(leads, client, state)

        self.assertEqual(result["synced"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertIn("111", state["synced_phones"])
        self.assertIn("222", state["synced_phones"])  # 已存在的也记进本地集合
        self.assertNotIn("333", state["synced_phones"])  # 失败的不记，下轮重试
        self.assertEqual(result["existing_hits"], 1)
        self.assertEqual(result["failure_kinds"], {"business": 1})

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
        self.assertEqual(state["last_sync_time"], "2026-06-24 11:43")

    def test_failed_lead_not_lost_after_watermark_advance(self):
        # 失败的记录不能被水位线越过，否则下一轮永远抓不到 → 永久丢失
        state = {"last_sync_time": None, "synced_phones": set(), "stats": {}}
        leads = [
            {"phone": "111", "leave_time": "2026-06-24 11:43"},  # 成功
            {"phone": "222", "leave_time": "2026-06-24 11:40"},  # 失败
            {"phone": "333", "leave_time": "2026-06-24 11:30"},  # 成功
        ]
        client = FakeClient(fail_phones=["222"])
        sync_daemon.process_leads(leads, client, state)
        # 水位线必须停在最早失败记录 11:40，不能越过到 11:43
        self.assertEqual(state["last_sync_time"], "2026-06-24 11:40")
        # 222 未进 synced_phones，且 11:40 >= 水位线 11:40，下轮会被重试
        self.assertNotIn("222", state["synced_phones"])
        # 验证下轮 filter 仍能抓到 222
        import jvdc_scraper
        re_fetched = jvdc_scraper.filter_new_leads(leads, since=state["last_sync_time"])
        self.assertIn("222", [r["phone"] for r in re_fetched])

    def test_failed_phone_exists_counts_as_failure(self):
        class BrokenClient(FakeClient):
            def phone_exists_result(self, phone):
                return {"ok": False, "exists": None, "error": {"kind": "network", "message": "boom"}}

        state = {"last_sync_time": None, "synced_phones": set(), "stats": {}}
        leads = [{"phone": "111", "leave_time": "2026-06-24 11:43"}]
        result = sync_daemon.process_leads(leads, BrokenClient(), state)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["failure_kinds"], {"network": 1})


if __name__ == "__main__":
    unittest.main()
