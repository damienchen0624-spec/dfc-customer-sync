#!/usr/bin/env python3
"""找出完整手机号在 DOM 中的存储位置。"""

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

        page.wait_for_timeout(5000)

        # 先点击第一个眼睛图标
        print("\n=== 点击眼睛图标 ===")
        eye_locator = page.locator('table svg.icon_-icon-EyeInvisible').first
        if eye_locator.count() > 0:
            eye_locator.click()
            print("✅ 已点击")
            page.wait_for_timeout(2000)
        else:
            print("️ 未找到 EyeInvisible 图标，可能已经被点击过了")

        # 在 DOM 中搜索完整手机号 13899086272
        print("\n=== 搜索完整手机号在 DOM 中的位置 ===")
        search_result = page.evaluate("""
            () => {
                const phone = '13899086272';
                const results = [];
                
                // 1. 搜索所有元素的文本内容
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.children.length === 0) {  // 叶子节点
                        const text = el.textContent || '';
                        if (text.includes(phone)) {
                            results.push({
                                type: 'text',
                                tag: el.tagName,
                                class: (el.className || '').toString().substring(0, 80),
                                text: text.substring(0, 100),
                                parentTag: el.parentElement?.tagName,
                                parentClass: (el.parentElement?.className || '').toString().substring(0, 80)
                            });
                        }
                    }
                    
                    // 2. 搜索所有属性
                    for (const attr of el.attributes || []) {
                        if (attr.value && attr.value.includes(phone)) {
                            results.push({
                                type: 'attribute',
                                tag: el.tagName,
                                attrName: attr.name,
                                attrValue: attr.value.substring(0, 200),
                                class: (el.className || '').toString().substring(0, 80)
                            });
                        }
                    }
                }
                
                return results.slice(0, 20);
            }
        """)

        print(f"找到 {len(search_result)} 个匹配:")
        for i, r in enumerate(search_result):
            print(f"\n  [{i+1}] 类型: {r['type']}")
            if r['type'] == 'text':
                print(f"      标签: {r['tag']} .{r['class']}")
                print(f"      文本: {r['text']}")
                print(f"      父级: {r['parentTag']} .{r['parentClass']}")
            else:
                print(f"      标签: {r['tag']} .{r['class']}")
                print(f"      属性: {r['attrName']} = {r['attrValue'][:100]}")

        # 也检查第一行的完整 HTML 中是否包含手机号
        print("\n=== 检查第一行 HTML 中的手机号 ===")
        row_html_check = page.evaluate("""
            () => {
                const row = document.querySelector('table tbody tr');
                if (!row) return null;
                const html = row.outerHTML;
                const phone = '13899086272';
                const idx = html.indexOf(phone);
                if (idx === -1) return { found: false };
                
                // 返回手机号前后的 HTML 上下文
                const start = Math.max(0, idx - 200);
                const end = Math.min(html.length, idx + 50);
                return {
                    found: true,
                    context: html.substring(start, end),
                    position: idx
                };
            }
        """)
        
        if row_html_check and row_html_check.get('found'):
            print(f"✅ 在第一行 HTML 中找到手机号")
            print(f"   位置: {row_html_check['position']}")
            print(f"   上下文: ...{row_html_check['context']}...")
        else:
            print("❌ 第一行 HTML 中未找到完整手机号")

        # 检查 React/Vue 内部状态
        print("\n=== 检查 React 内部状态 ===")
        react_check = page.evaluate("""
            () => {
                const row = document.querySelector('table tbody tr');
                if (!row) return null;
                
                // 尝试获取 React fiber
                const key = Object.keys(row).find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
                if (key) {
                    let fiber = row[key];
                    // 遍历 fiber 树查找 props
                    while (fiber) {
                        if (fiber.memoizedProps) {
                            const propsStr = JSON.stringify(fiber.memoizedProps);
                            if (propsStr.includes('13899086272')) {
                                return { found: true, in: 'memoizedProps', snippet: propsStr.substring(propsStr.indexOf('13899086272') - 50, propsStr.indexOf('13899086272') + 50) };
                            }
                        }
                        if (fiber.pendingProps) {
                            const propsStr = JSON.stringify(fiber.pendingProps);
                            if (propsStr.includes('13899086272')) {
                                return { found: true, in: 'pendingProps', snippet: propsStr.substring(propsStr.indexOf('13899086272') - 50, propsStr.indexOf('13899086272') + 50) };
                            }
                        }
                        fiber = fiber.return;
                    }
                }
                return { found: false, reactKey: key || null };
            }
        """)
        
        if react_check:
            print(f"React 状态: {json.dumps(react_check, ensure_ascii=False)[:300]}")

        # 保存所有结果
        with open('/tmp/dom_phone_location.json', 'w') as f:
            json.dump({
                'search_results': search_result,
                'row_html_check': row_html_check,
                'react_check': react_check
            }, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到 /tmp/dom_phone_location.json")


if __name__ == "__main__":
    main()
