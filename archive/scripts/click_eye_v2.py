#!/usr/bin/env python3
"""找到眼睛图标并点击。"""

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

    api_log = []

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()

        if Path(storage_path).exists():
            storage_data = json.loads(Path(storage_path).read_text(encoding="utf-8"))
            if "cookies" in storage_data:
                ctx.add_cookies(storage_data["cookies"])
                print(f"✅ 已加载 {len(storage_data['cookies'])} 个 cookies")

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def handle_response(response):
            url = response.url
            if 'sh_crm_api' in url:
                try:
                    body = response.json()
                    api_log.append({'url': url, 'status': response.status, 'body': body})
                    body_str = json.dumps(body, ensure_ascii=False)
                    phones = re.findall(r'1[3-9]\d{9}', body_str)
                    if phones and 'customer' in url.lower():
                        print(f"\n[🔑 API] {url.split('?')[0].split('/')[-1]}")
                        print(f"  手机号: {phones[:5]}")
                        print(f"  响应: {body_str[:500]}")
                except:
                    pass

        page.on('response', handle_response)

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

        # 查找所有 SVG，找到眼睛图标
        all_svgs = page.evaluate("""
            () => {
                const table = document.querySelector('table');
                if (!table) return [];
                const svgs = table.querySelectorAll('svg');
                return Array.from(svgs).map((svg, i) => {
                    const cls = (svg.className.baseVal || '');
                    const parentCls = (svg.parentElement?.className || '');
                    const row = svg.closest('tr');
                    const rowText = row ? row.innerText.substring(0, 150) : '';
                    return {
                        index: i,
                        class: cls.substring(0, 100),
                        parentClass: parentCls.substring(0, 100),
                        hasEye: cls.includes('Eye') || cls.includes('eye'),
                        rowText: rowText
                    };
                });
            }
        """)

        print(f"\n=== 表格中 {len(all_svgs)} 个 SVG ===")
        eye_svgs = [s for s in all_svgs if s['hasEye']]
        print(f"眼睛图标: {len(eye_svgs)} 个")
        
        for s in eye_svgs[:3]:
            print(f"  #{s['index']}: class={s['class']}, parent={s['parentClass']}")
            phone_match = re.search(r'(1\d{2}\*{6}\d{2})', s['rowText'])
            if phone_match:
                print(f"      手机号: {phone_match.group()}")

        if not eye_svgs:
            # 尝试更宽泛的搜索
            print("\n尝试查找所有包含 'Eye' 的元素...")
            eye_elements = page.evaluate("""
                () => {
                    const all = document.querySelectorAll('*');
                    const results = [];
                    for (const el of all) {
                        const cls = (el.className || '').toString();
                        if (cls.includes('Eye') || cls.includes('eye')) {
                            results.push({
                                tag: el.tagName,
                                class: cls.substring(0, 100),
                                parentTag: el.parentElement?.tagName
                            });
                        }
                    }
                    return results.slice(0, 10);
                }
            """)
            print(f"找到 {len(eye_elements)} 个元素")
            for e in eye_elements:
                print(f"  {e['tag']} .{e['class']} parent={e['parentTag']}")
            return

        # 点击第一个眼睛图标
        print(f"\n=== 点击眼睛图标 ===")
        api_log.clear()

        clicked = page.evaluate("""
            () => {
                const svg = document.querySelector('table svg[class*="Eye"]');
                if (!svg) return { clicked: false, error: 'no eye svg' };
                
                // 向上查找可点击的父元素
                let el = svg;
                for (let i = 0; i < 5; i++) {
                    if (el) {
                        el.click();
                        return { clicked: true, tag: el.tagName, class: (el.className || '').toString().substring(0, 50) };
                    }
                    el = el.parentElement;
                }
                return { clicked: false };
            }
        """)

        print(f"点击结果: {json.dumps(clicked, ensure_ascii=False)}")
        page.wait_for_timeout(5000)

        # 检查手机号
        result = page.evaluate("""
            () => {
                const row = document.querySelector('table tbody tr');
                if (!row) return { error: 'no row' };
                const text = row.innerText;
                const fullPhone = text.match(/手机[：:]\\s*\\n?\\s*(1\\d{10})/);
                const maskedPhone = text.match(/手机[：:]\\s*\\n?\\s*(1\\d{2}\\*{6}\\d{2})/);
                return {
                    fullPhone: fullPhone ? fullPhone[1] : null,
                    maskedPhone: maskedPhone ? maskedPhone[1] : null
                };
            }
        """)

        print(f"\n完整手机号: {result.get('fullPhone')}")
        print(f"脱敏手机号: {result.get('maskedPhone')}")

        # 输出 API
        print(f"\n=== {len(api_log)} 个 CRM API ===")
        for i, resp in enumerate(api_log):
            print(f"[{i+1}] {resp['url'].split('?')[0].split('/')[-1][:60]}")

        with open('/tmp/eye_result2.json', 'w') as f:
            json.dump({'result': result, 'apis': api_log}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
