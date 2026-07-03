#!/usr/bin/env python3
"""拦截点击"眼睛"按钮后获取完整手机号的 API。"""

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

    api_responses = []

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

        # 监听所有 API 响应
        def handle_response(response):
            url = response.url
            # 过滤出可能的解密 API
            if any(keyword in url.lower() for keyword in ['phone', 'decrypt', 'detail', 'info', 'view']):
                try:
                    body = response.json()
                    api_responses.append({
                        'url': url,
                        'status': response.status,
                        'body': body
                    })
                    print(f"\n[API 响应] {url}")
                    print(f"  状态: {response.status}")
                    # 检查是否包含手机号
                    body_str = json.dumps(body, ensure_ascii=False)
                    if '1' in body_str and len(body_str) < 500:
                        print(f"  响应: {body_str[:300]}")
                except:
                    pass

        page.on('response', handle_response)

        list_url = config["jvdc"]["list_url"]
        print(f"导航到: {list_url}")
        sync_daemon._navigate_reliable(page, list_url, timeout_ms=30000)

        print(f"当前 URL: {page.url}")
        
        # 等待表格加载
        print("等待表格加载...")
        try:
            page.wait_for_selector('table.arco-table tbody tr', timeout=20000)
            print("✅ 表格已加载")
        except:
            print("⚠️ 表格加载超时")
            # 保存截图看看当前状态
            page.screenshot(path='/tmp/jvdc_page.png')
            print("已保存截图到 /tmp/jvdc_page.png")
            return
        
        page.wait_for_timeout(3000)

        # 找到第一行的眼睛图标
        print("\n=== 查找眼睛图标 ===")
        
        # 尝试多种选择器
        eye_selectors = [
            'svg[class*="eye"]',
            'span[class*="eye"]',
            'i[class*="eye"]',
            '[class*="eye"]',
            '[data-icon="eye"]',
            'svg',  # 所有 SVG
        ]
        
        eye_btn = None
        for selector in eye_selectors:
            elements = page.query_selector_all(selector)
            print(f"  {selector}: 找到 {len(elements)} 个")
            if elements and not eye_btn:
                # 检查是否在手机号附近
                for el in elements[:3]:
                    parent = el.query_selector('..')
                    if parent:
                        text = parent.inner_text()
                        if '138' in text or '***' in text:
                            eye_btn = el
                            print(f"    ✅ 找到手机号附近的眼睛图标: {selector}")
                            break
        
        if not eye_btn:
            print("❌ 未找到眼睛图标，尝试直接查找手机号旁边的可点击元素")
            # 查找包含脱敏手机号的元素
            phone_cells = page.query_selector_all('td')
            for cell in phone_cells:
                text = cell.inner_text()
                if '***' in text and len(text) < 30:
                    print(f"  找到脱敏手机号: {text}")
                    # 查找该单元格内的所有可点击元素
                    clickables = cell.query_selector_all('span, button, svg, a')
                    print(f"    可点击元素: {len(clickables)}")
                    for c in clickables:
                        tag = c.evaluate('el => el.tagName')
                        cls = c.get_attribute('class') or ''
                        print(f"      {tag} class={cls[:50]}")
                        if 'eye' in cls.lower() or 'view' in cls.lower() or 'show' in cls.lower():
                            eye_btn = c
                            print(f"      ✅ 可能是眼睛图标")
                            break
                    if eye_btn:
                        break
        
        if eye_btn:
            print(f"\n=== 点击眼睛图标 ===")
            print(f"清空之前的 API 响应记录...")
            api_responses.clear()
            
            # 点击前截图
            page.screenshot(path='/tmp/before_click.png')
            
            eye_btn.click()
            print("✅ 已点击")
            
            # 等待 API 响应
            page.wait_for_timeout(3000)
            
            # 点击后截图
            page.screenshot(path='/tmp/after_click.png')
            
            # 检查手机号是否变成完整的
            phone_cells = page.query_selector_all('td')
            for cell in phone_cells:
                text = cell.inner_text()
                if '1' in text and len(text) < 30 and '***' not in text:
                    import re
                    if re.search(r'1[3-9]\d{9}', text):
                        print(f"\n✅ 找到完整手机号: {text}")
                        break
            
            # 输出捕获的 API 响应
            print(f"\n=== 捕获到 {len(api_responses)} 个 API 响应 ===")
            for i, resp in enumerate(api_responses):
                print(f"\n[{i+1}] {resp['url']}")
                print(f"    状态: {resp['status']}")
                body_str = json.dumps(resp['body'], ensure_ascii=False)
                print(f"    响应: {body_str[:500]}")
            
            # 保存到文件
            with open('/tmp/eye_api_responses.json', 'w') as f:
                json.dump(api_responses, f, ensure_ascii=False, indent=2)
            print(f"\nAPI 响应已保存到 /tmp/eye_api_responses.json")
        else:
            print("❌ 未找到眼睛图标")


if __name__ == "__main__":
    main()
