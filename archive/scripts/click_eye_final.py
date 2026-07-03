#!/usr/bin/env python3
"""点击眼睛图标并捕获解密 API。"""

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

        # 监听 API 响应
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
                        print(f"  状态: {response.status}")
                        print(f"  手机号: {phones[:5]}")
                        print(f"  完整响应: {body_str[:500]}")
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

        # 找到所有眼睛图标
        eye_icons = page.evaluate("""
            () => {
                const svgs = document.querySelectorAll('table svg.icon_-icon-Eye');
                return Array.from(svgs).map((svg, i) => {
                    // 获取该图标所在行的手机号文本
                    const row = svg.closest('tr');
                    const rowText = row ? row.innerText.substring(0, 200) : '';
                    return {
                        index: i,
                        class: svg.className.baseVal,
                        rowText: rowText
                    };
                });
            }
        """)

        print(f"\n=== 找到 {len(eye_icons)} 个眼睛图标 ===")
        for icon in eye_icons[:3]:
            print(f"\n  图标 #{icon['index']}:")
            print(f"    class: {icon['class']}")
            # 提取手机号
            phone_match = re.search(r'1\d{2}\*{6}\d{2}', icon['rowText'])
            if phone_match:
                print(f"    脱敏手机号: {phone_match.group()}")

        if not eye_icons:
            print("❌ 未找到眼睛图标")
            return

        # 点击第一个眼睛图标
        print(f"\n=== 点击第一个眼睛图标 ===")
        api_log.clear()  # 清空之前的 API 记录

        clicked = page.evaluate("""
            () => {
                const svg = document.querySelector('table svg.icon_-icon-Eye');
                if (!svg) return { clicked: false, error: 'no eye icon' };
                
                // 找到可点击的父元素
                let clickable = svg;
                while (clickable && clickable.tagName !== 'TR') {
                    const style = window.getComputedStyle(clickable);
                    if (style.cursor === 'pointer' || clickable.tagName === 'BUTTON' || clickable.tagName === 'A') {
                        break;
                    }
                    clickable = clickable.parentElement;
                }
                
                clickable.click();
                return { clicked: true, tag: clickable.tagName };
            }
        """)

        print(f"点击结果: {json.dumps(clicked, ensure_ascii=False)}")

        # 等待 API 响应
        page.wait_for_timeout(5000)

        # 检查手机号是否变成完整的
        result = page.evaluate("""
            () => {
                const rows = document.querySelectorAll('table tbody tr');
                const firstRow = rows[0];
                if (!firstRow) return { error: 'no rows' };
                
                const text = firstRow.innerText;
                // 查找完整手机号
                const fullPhone = text.match(/手机[：:]\\s*\\n?\\s*(1\\d{10})/);
                // 查找脱敏手机号
                const maskedPhone = text.match(/手机[：:]\\s*\\n?\\s*(1\\d{2}\\*{6}\\d{2})/);
                
                return {
                    fullPhone: fullPhone ? fullPhone[1] : null,
                    maskedPhone: maskedPhone ? maskedPhone[1] : null,
                    phoneSection: text.substring(text.indexOf('手机'), text.indexOf('手机') + 50)
                };
            }
        """)

        print(f"\n=== 点击后手机号状态 ===")
        print(f"完整手机号: {result.get('fullPhone', 'N/A')}")
        print(f"脱敏手机号: {result.get('maskedPhone', 'N/A')}")
        print(f"手机号区域: {result.get('phoneSection', 'N/A')}")

        # 输出所有 CRM API
        print(f"\n=== 捕获到 {len(api_log)} 个 CRM API ===")
        for i, resp in enumerate(api_log):
            print(f"\n[{i+1}] {resp['url'].split('?')[0].split('/')[-1][:60]}")
            body_str = json.dumps(resp['body'], ensure_ascii=False)
            if len(body_str) < 400:
                print(f"    {body_str}")

        # 保存
        with open('/tmp/eye_click_full.json', 'w') as f:
            json.dump({'result': result, 'apis': api_log}, f, ensure_ascii=False, indent=2)
        print(f"\n数据已保存到 /tmp/eye_click_full.json")


if __name__ == "__main__":
    main()
