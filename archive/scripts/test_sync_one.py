#!/usr/bin/env python3
"""测试同步：抓取一条历史留资并同步到大风车。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_daemon
import jvdc_scraper
import auth
import dfc_client
import state as state_mod
from playwright.sync_api import sync_playwright


def main():
    config = sync_daemon.load_config(ROOT / "config" / "config.json")
    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
    storage_path = sync_daemon._storage_state_path(config)

    # 启动 Chrome CDP
    print("启动 Chrome CDP...")
    sync_daemon._start_chrome_cdp(user_data_dir, port=9222, timeout_sec=30)

    # 大风车认证
    token = auth.get_token()
    account = auth.get_account_info(token)
    shop_code = account["shopCode"]
    client = dfc_client.DfcClient(token=token, shop_code=shop_code)
    print(f"大风车门店: {account['shopName']} ({shop_code})")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()

        # 加载 cookies
        if Path(storage_path).exists():
            storage_data = json.loads(Path(storage_path).read_text(encoding="utf-8"))
            if "cookies" in storage_data:
                ctx.add_cookies(storage_data["cookies"])
                print(f"✅ 已加载 {len(storage_data['cookies'])} 个 cookies")

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # 抓取所有留资（since=None）
        print(f"抓取客户列表: {config['jvdc']['list_url']}")
        leads = jvdc_scraper.fetch_new_leads(
            page, config["jvdc"]["list_url"],
            since=None,  # 抓取所有
            allowed_types=config["sync"].get("lead_type_filter", []),
        )

        print(f"\n共抓取到 {len(leads)} 条留资")

        if not leads:
            print("❌ 没有抓取到任何留资，可能是选择器问题或页面未加载")
            return

        # 取第一条测试
        test_lead = leads[0]
        print(f"\n=== 测试同步第一条 ===")
        print(json.dumps(test_lead, ensure_ascii=False, indent=2))

        # 检查手机号是否已存在
        phone = test_lead.get("phone", "")
        if not phone:
            print("❌ 该留资没有手机号，无法同步")
            return

        print(f"\n检查手机号 {phone} 是否已存在...")
        if client.phone_exists(phone):
            print(f"⚠️ 手机号 {phone} 已存在于大风车，跳过")
        else:
            print(f"手机号不存在，尝试添加...")
            if client.add_customer(test_lead):
                print(f"✅ 同步成功！")
            else:
                print(f"❌ 同步失败")


if __name__ == "__main__":
    main()
