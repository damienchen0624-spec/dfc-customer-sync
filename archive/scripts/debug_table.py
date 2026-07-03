#!/usr/bin/env python3
"""调试：查看当前表格 DOM 内容。"""

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
            page.screenshot(path='/tmp/table_debug2.png')
            return

        page.wait_for_timeout(5000)

        # 获取表格基本信息
        info = page.evaluate("""
            () => {
                const table = document.querySelector('table');
                if (!table) return { error: 'no table' };
                const rows = table.querySelectorAll('tbody tr');
                return {
                    tableFound: true,
                    rowCount: rows.length,
                    tableClass: table.className.substring(0, 100),
                    firstRowText: rows.length > 0 ? rows[0].innerText.substring(0, 500) : 'no rows',
                    firstRowHtml: rows.length > 0 ? rows[0].outerHTML.substring(0, 2000) : 'no rows'
                };
            }
        """)
        
        print(f"\n表格信息: {json.dumps(info, ensure_ascii=False, indent=2)}")

        # 提取所有行的纯文本
        all_rows = page.evaluate("""
            () => {
                const rows = document.querySelectorAll('table tbody tr');
                return Array.from(rows).map((row, i) => ({
                    index: i,
                    text: row.innerText.substring(0, 400)
                }));
            }
        """)
        
        print(f"\n=== 所有行文本 ({len(all_rows)} 行) ===")
        for row in all_rows[:5]:
            print(f"\n--- 行 {row['index']} ---")
            print(row['text'][:300])

        # 保存截图
        page.screenshot(path='/tmp/table_current.png')
        print(f"\n截图已保存到 /tmp/table_current.png")


if __name__ == "__main__":
    main()
