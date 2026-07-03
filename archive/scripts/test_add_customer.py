#!/usr/bin/env python3
"""测试新增客户到大风车（找不重复的）。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_daemon
import auth
import jvdc_scraper
import dfc_client


def main():
    config = sync_daemon.load_config(ROOT / "config" / "config.json")
    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
    storage_path = sync_daemon._storage_state_path(config)

    token = auth.get_token()
    account_info = auth.get_account_info(token)
    shop_code = account_info.get("shopCode", "")
    print(f"门店: {account_info.get('shopName', '')} ({shop_code})")

    dfc = dfc_client.DfcClient(token, shop_code)

    print("\n=== 启动 Chrome ===")
    sync_daemon._start_chrome_cdp(user_data_dir, port=9222, timeout_sec=30)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()

        if Path(storage_path).exists():
            storage_data = json.loads(Path(storage_path).read_text(encoding="utf-8"))
            if "cookies" in storage_data:
                ctx.add_cookies(storage_data["cookies"])

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        list_url = config["jvdc"]["list_url"]
        leads = jvdc_scraper.fetch_new_leads(page, list_url, since=None, allowed_types=[])
        print(f"\n抓取到 {len(leads)} 个客户")

        # 逐个查重，找到不存在的
        print("\n=== 逐个查重 ===")
        test_lead = None
        for i, lead in enumerate(leads):
            phone = lead.get("phone", "")
            check = dfc.phone_exists_result(phone)
            exists = check.get("exists", False)
            status = "已存在" if exists else "✅ 不存在"
            print(f"  [{i+1}] {phone} - {status}")
            if not exists and test_lead is None:
                test_lead = lead

        if test_lead is None:
            print("\n⚠️ 所有客户都已存在于大风车")
            # 用构造数据测试
            print("\n=== 使用构造数据测试新增 API ===")
            test_lead = {
                "phone": "13800138000",
                "name": "测试客户-巨懂车同步",
                "leave_time": "2026-06-29 18:00",
                "source": "微信",
                "grade": "",
                "status": "未联系",
                "intent_model": "测试车型",
                "lead_type": "表单线索",
            }
            print(f"  使用构造数据: {test_lead['name']} / {test_lead['phone']}")

        # 新增
        print(f"\n=== 新增客户 ===")
        print(f"  姓名: {test_lead.get('name')}")
        print(f"  手机: {test_lead.get('phone')}")
        print(f"  来源: {test_lead.get('source')}")
        print(f"  意向车型: {test_lead.get('intent_model')}")

        result = dfc.add_customer_result(test_lead)
        print(f"\n  结果: {json.dumps(result, ensure_ascii=False, indent=2)}")

        if result.get("ok"):
            print(f"\n✅ 新增成功！")
        else:
            error = result.get("error", {})
            print(f"\n❌ 新增失败: {error.get('message', '未知错误')}")
            print(f"   错误类型: {error.get('kind', 'unknown')}")


if __name__ == "__main__":
    main()
