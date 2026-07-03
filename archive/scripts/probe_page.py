#!/usr/bin/env python3
"""探测巨懂车客户列表页面的 DOM 结构。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_daemon
from playwright.sync_api import sync_playwright


def main():
    config = sync_daemon.load_config(ROOT / "config" / "config.json")
    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
    storage_path = sync_daemon._storage_state_path(config)

    print("启动 Chrome CDP...")
    sync_daemon._start_chrome_cdp(user_data_dir, port=9222, timeout_sec=30)

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

        list_url = config["jvdc"]["list_url"]
        print(f"导航到: {list_url}")
        sync_daemon._navigate_reliable(page, list_url, timeout_ms=30000)

        print(f"当前 URL: {page.url}")

        # 等待页面加载
        page.wait_for_timeout(3000)

        # 检查是否有表格
        tables = page.query_selector_all("table")
        print(f"\n找到 {len(tables)} 个 table 元素")

        # 检查表格行
        rows = page.query_selector_all("table tbody tr")
        print(f"找到 {len(rows)} 个 table tbody tr 元素")

        # 打印前 3 行的文本内容
        for i, row in enumerate(rows[:3]):
            text = row.inner_text()
            print(f"\n=== 第 {i+1} 行 ===")
            print(text[:500] if len(text) > 500 else text)

        # 查找包含手机号的元素
        print("\n=== 查找手机号 ===")
        body_text = page.inner_text("body")
        import re
        phones = re.findall(r"1\d{10}", body_text)
        masked_phones = re.findall(r"1\d{2}\*{6}\d{2}", body_text)
        print(f"完整手机号: {phones[:5]}")
        print(f"脱敏手机号: {masked_phones[:5]}")

        # 保存页面 HTML 供分析
        html = page.content()
        dump_path = ROOT / "dom_dump_test.html"
        dump_path.write_text(html, encoding="utf-8")
        print(f"\n页面 HTML 已保存到: {dump_path}")


if __name__ == "__main__":
    main()
