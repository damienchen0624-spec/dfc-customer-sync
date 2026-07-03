#!/usr/bin/env python3
"""启动 Chrome 并打开巨懂车页面。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_daemon

config = sync_daemon.load_config(ROOT / "config" / "config.json")
user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
storage_path = sync_daemon._storage_state_path(config)

print("启动 Chrome CDP...")
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

    list_url = config["jvdc"]["list_url"]
    print(f"\n导航到：{list_url}")
    sync_daemon._navigate_reliable(page, list_url, timeout_ms=30000)

    try:
        page.wait_for_selector('table tbody tr', timeout=20000)
        print("✅ 表格已加载")
    except:
        print("⚠️ 表格加载超时")

    page.wait_for_timeout(3000)
    page.screenshot(path="/tmp/jvdc_page_ready.png")
    print("\n✅ 页面已就绪，请在浏览器中手动点击眼睛图标")
    print("   完成后运行 check_phone_location.py 检查 DOM")
