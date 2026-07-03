#!/usr/bin/env python3
"""点击 EyeInvisible 图标获取完整手机号。"""

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
                        print(f"\n[ API] {url.split('?')[0].split('/')[-1]}")
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

        # 找到眼睛图标并点击
        print(f"\n=== 查找并点击 EyeInvisible 图标 ===")
        api_log.clear()

        # 用 Playwright 的 locator 直接点击
        eye_locator = page.locator('table svg.icon_-icon-EyeInvisible').first
        
        if eye_locator.count() > 0:
            print(f"找到 {eye_locator.count()} 个 EyeInvisible 图标")
            
            # 获取点击前的手机号
            before_phone = page.evaluate("""
                () => {
                    const row = document.querySelector('table tbody tr');
                    if (!row) return null;
                    const text = row.innerText;
                    const match = text.match(/手机[：:]\\s*\\n?\\s*(\\S+)/);
                    return match ? match[1] : null;
                }
            """)
            print(f"点击前手机号: {before_phone}")

            # 点击眼睛图标
            eye_locator.click()
            print("✅ 已点击眼睛图标")
            
            page.wait_for_timeout(5000)

            # 获取点击后的手机号
            after_phone = page.evaluate("""
                () => {
                    const row = document.querySelector('table tbody tr');
                    if (!row) return null;
                    const text = row.innerText;
                    const match = text.match(/手机[：:]\\s*\\n?\\s*(\\S+)/);
                    return match ? match[1] : null;
                }
            """)
            print(f"点击后手机号: {after_phone}")

            # 检查图标是否变化
            icon_state = page.evaluate("""
                () => {
                    const svg = document.querySelector('table tbody tr svg[class*="Eye"]');
                    if (!svg) return { error: 'no eye icon' };
                    const cls = svg.className.baseVal;
                    return { class: cls, isVisible: cls.includes('EyeInvisible') === false };
                }
            """)
            print(f"图标状态: {json.dumps(icon_state, ensure_ascii=False)}")
        else:
            print("❌ 未找到 EyeInvisible 图标")
            return

        # 输出 API
        print(f"\n=== {len(api_log)} 个 CRM API ===")
        for i, resp in enumerate(api_log):
            url_short = resp['url'].split('?')[0].split('/')[-1][:60]
            body_str = json.dumps(resp['body'], ensure_ascii=False)
            print(f"\n[{i+1}] {url_short}")
            if len(body_str) < 400:
                print(f"    {body_str}")
            else:
                print(f"    (长度 {len(body_str)})")

        with open('/tmp/eye_click_success.json', 'w') as f:
            json.dump({
                'before': before_phone,
                'after': after_phone,
                'icon': icon_state,
                'apis': api_log
            }, f, ensure_ascii=False, indent=2)
        print(f"\n数据已保存到 /tmp/eye_click_success.json")


if __name__ == "__main__":
    main()
