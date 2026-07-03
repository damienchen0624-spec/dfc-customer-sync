#!/usr/bin/env python3
"""端到端测试：巨懂车抓取 → 大风车同步。"""

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

    # 获取大风车认证信息
    print("=== 获取大风车认证 ===")
    token = auth.get_token()
    print(f"Token: {token[:20]}...")
    
    account_info = auth.get_account_info(token)
    shop_code = account_info.get("shopCode", "")
    print(f"门店: {account_info.get('shopName', '')} ({shop_code})")

    dfc = dfc_client.DfcClient(token, shop_code)

    # 启动 Chrome
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
                print(f"✅ 已加载 {len(storage_data['cookies'])} 个 cookies")

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # 抓取巨懂车客户
        print("\n=== 抓取巨懂车客户 ===")
        list_url = config["jvdc"]["list_url"]
        leads = jvdc_scraper.fetch_new_leads(page, list_url, since=None, allowed_types=[])
        
        print(f"\n抓取到 {len(leads)} 个客户:")
        for i, lead in enumerate(leads[:5]):
            print(f"  [{i+1}] {lead.get('name', 'N/A')} | {lead.get('phone', 'N/A')} | {lead.get('leave_time', 'N/A')} | {lead.get('source', 'N/A')}")

        if not leads:
            print("❌ 没有抓取到客户")
            return

        # 测试第一个客户
        lead = leads[0]
        phone = lead.get("phone", "")
        print(f"\n=== 测试同步第一个客户 ===")
        print(f"  姓名: {lead.get('name')}")
        print(f"  手机: {phone}")
        print(f"  留资时间: {lead.get('leave_time')}")
        print(f"  来源: {lead.get('source')}")
        print(f"  意向车型: {lead.get('intent_model')}")
        print(f"  线索类型: {lead.get('lead_type')}")

        # 查重
        print(f"\n=== 大风车查重 ===")
        check = dfc.phone_exists_result(phone)
        print(f"  结果: {json.dumps(check, ensure_ascii=False)}")

        if check.get("exists"):
            print(f"\n⚠️ 该客户已存在于大风车，跳过新增")
        else:
            print(f"\n=== 新增客户到大风车 ===")
            result = dfc.add_customer_result(lead)
            print(f"  结果: {json.dumps(result, ensure_ascii=False)}")
            
            if result.get("ok"):
                print(f"\n✅ 同步成功！")
            else:
                error = result.get("error", {})
                print(f"\n❌ 同步失败: {error.get('message', '未知错误')}")


if __name__ == "__main__":
    main()
