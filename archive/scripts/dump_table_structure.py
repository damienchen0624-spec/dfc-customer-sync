#!/usr/bin/env python3
"""Dump 表格 HTML 结构找到眼睛图标。"""

import json
import re
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
        print(f"\n导航到：{list_url}")
        sync_daemon._navigate_reliable(page, list_url, timeout_ms=30000)
        
        print(f"\n当前 URL: {page.url}")
        
        # 等待表格加载
        print("等待表格加载...")
        try:
            page.wait_for_selector('table tbody tr', timeout=20000)
            print("✅ 表格已加载")
        except:
            print("⚠️ 表格加载超时")
            # 保存截图
            page.screenshot(path='/tmp/table_debug.png')
            print("已保存截图到 /tmp/table_debug.png")
        
        page.wait_for_timeout(3000)

        # Dump 表格 HTML 结构
        print("\n=== Dump 表格 HTML ===")
        table_html = page.evaluate("""
            () => {
                const table = document.querySelector('table');
                if (!table) return { error: '未找到 table 元素' };
                
                const rows = table.querySelectorAll('tbody tr');
                if (rows.length === 0) return { error: '表格没有行', tableHtml: table.outerHTML.substring(0, 500) };
                
                // 获取前 3 行的 HTML
                const rowHtmls = [];
                for (let i = 0; i < Math.min(3, rows.length); i++) {
                    rowHtmls.push({
                        index: i,
                        html: rows[i].outerHTML.substring(0, 1000),
                        text: rows[i].innerText.substring(0, 200)
                    });
                }
                
                return {
                    rowCount: rows.length,
                    rows: rowHtmls
                };
            }
        """)
        
        print(json.dumps(table_html, ensure_ascii=False, indent=2))
        
        # 查找所有 SVG 图标
        print("\n=== 查找所有 SVG 图标 ===")
        svgs = page.evaluate("""
            () => {
                const table = document.querySelector('table');
                if (!table) return [];
                
                const svgs = table.querySelectorAll('svg');
                return Array.from(svgs).map((svg, i) => ({
                    index: i,
                    class: (svg.className.baseVal || '').substring(0, 100),
                    html: svg.innerHTML.substring(0, 200),
                    parentTag: svg.parentElement?.tagName,
                    parentClass: (svg.parentElement?.className || '').substring(0, 100),
                    grandparentText: svg.parentElement?.parentElement?.innerText?.substring(0, 100)
                }));
            }
        """)
        
        print(f"找到 {len(svgs)} 个 SVG")
        for svg in svgs[:10]:
            print(f"\n  SVG #{svg['index']}:")
            print(f"    class: {svg['class']}")
            print(f"    html: {svg['html'][:150]}")
            print(f"    parent: {svg['parentTag']} .{svg['parentClass']}")
            print(f"    附近文本：{svg['grandparentText'][:100]}")
        
        # 保存完整数据
        with open('/tmp/table_structure.json', 'w') as f:
            json.dump({'table': table_html, 'svgs': svgs}, f, ensure_ascii=False, indent=2)
        print(f"\n完整结构已保存到 /tmp/table_structure.json")


if __name__ == "__main__":
    main()
