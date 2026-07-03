#!/usr/bin/env python3
"""打开巨懂车页面，等待用户手动点击眼睛图标，然后检查 DOM。"""

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
            return

        page.wait_for_timeout(3000)

        # 截图当前状态
        page.screenshot(path="/tmp/jvdc_before_click.png")
        print("截图已保存: /tmp/jvdc_before_click.png")

        # 输出第一行的当前状态
        first_row = page.evaluate("""
            () => {
                const row = document.querySelector('table tbody tr');
                if (!row) return null;
                return {
                    text: row.innerText.substring(0, 300),
                    html: row.innerHTML.substring(0, 500)
                };
            }
        """)
        
        if first_row:
            print(f"\n=== 第一行当前状态 ===")
            print(f"文本: {first_row['text'][:200]}...")

        print("\n" + "="*60)
        print("⏳ 请在浏览器中手动点击第一个客户的眼睛图标")
        print("   完成后按 Enter 继续...")
        print("="*60)
        
        input()

        # 检查点击后的状态
        print("\n=== 检查点击后的 DOM 变化 ===")
        
        # 1. 检查第一行的手机号
        after_phone = page.evaluate("""
            () => {
                const row = document.querySelector('table tbody tr');
                if (!row) return null;
                const text = row.innerText;
                const fullPhone = text.match(/手机[：:]\\s*\\n?\\s*(1\\d{10})/);
                const maskedPhone = text.match(/手机[：:]\\s*\\n?\\s*(1\\d{2}\\*{6}\\d{2})/);
                return {
                    fullPhone: fullPhone ? fullPhone[1] : null,
                    maskedPhone: maskedPhone ? maskedPhone[1] : null,
                    rowText: text.substring(0, 300)
                };
            }
        """)

        print(f"完整手机号: {after_phone.get('fullPhone')}")
        print(f"脱敏手机号: {after_phone.get('maskedPhone')}")

        # 2. 搜索完整手机号在 DOM 中的位置
        if after_phone.get('fullPhone'):
            phone = after_phone['fullPhone']
            print(f"\n=== 搜索 {phone} 在 DOM 中的位置 ===")
            
            locations = page.evaluate(f"""
                () => {{
                    const phone = '{phone}';
                    const results = [];
                    
                    // 搜索所有文本节点
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        null,
                        false
                    );
                    
                    let node;
                    while (node = walker.nextNode()) {{
                        if (node.textContent.includes(phone)) {{
                            const parent = node.parentElement;
                            results.push({{
                                type: 'text-node',
                                parentTag: parent.tagName,
                                parentClass: (parent.className || '').toString().substring(0, 80),
                                text: node.textContent.substring(0, 100),
                                isInTable: !!parent.closest('table')
                            }});
                        }}
                    }}
                    
                    // 搜索所有属性
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {{
                        for (const attr of el.attributes) {{
                            if (attr.value && attr.value.includes(phone)) {{
                                results.push({{
                                    type: 'attribute',
                                    tag: el.tagName,
                                    attrName: attr.name,
                                    attrValue: attr.value.substring(0, 200),
                                    class: (el.className || '').toString().substring(0, 80)
                                }});
                            }}
                        }}
                    }}
                    
                    return results.slice(0, 20);
                }}
            """)

            print(f"找到 {len(locations)} 个位置:")
            for i, loc in enumerate(locations):
                print(f"\n  [{i+1}] 类型: {loc['type']}")
                if loc['type'] == 'text-node':
                    print(f"      父元素: {loc['parentTag']} .{loc['parentClass']}")
                    print(f"      在表格中: {loc['isInTable']}")
                    print(f"      文本: {loc['text'][:80]}")
                else:
                    print(f"      元素: {loc['tag']} .{loc['class']}")
                    print(f"      属性: {loc['attrName']} = {loc['attrValue'][:80]}")

        # 3. 截图点击后的状态
        page.screenshot(path="/tmp/jvdc_after_click.png")
        print(f"\n截图已保存: /tmp/jvdc_after_click.png")


if __name__ == "__main__":
    main()
