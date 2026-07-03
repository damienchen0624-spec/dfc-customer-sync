#!/usr/bin/env python3
"""抓包大风车新增客户 API。

打开大风车客户列表页面，手动新增一个客户，捕获 API 请求。
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_daemon
import auth


def main():
    config = sync_daemon.load_config(ROOT / "config" / "config.json")
    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())

    token = auth.get_token()
    print(f"Token: {token[:20]}...")

    print("\n=== 启动 Chrome ===")
    sync_daemon._start_chrome_cdp(user_data_dir, port=9222, timeout_sec=30)

    from playwright.sync_api import sync_playwright

    captured = []

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def handle_request(request):
            url = request.url
            # 捕获所有 POST 请求到 souche.com
            if request.method == "POST" and "souche.com" in url:
                body = request.post_data or ""
                captured.append({
                    "url": url,
                    "method": request.method,
                    "body": body[:2000] if body else "",
                })

        def handle_response(response):
            url = response.url
            if "souche.com" in url and ("add" in url.lower() or "customer" in url.lower()):
                try:
                    body = response.json()
                    print(f"\n[API Response] {url.split('?')[0]}")
                    print(f"  Status: {response.status}")
                    print(f"  Body: {json.dumps(body, ensure_ascii=False)[:500]}")
                except:
                    pass

        page.on("request", handle_request)
        page.on("response", handle_response)

        # 打开大风车客户列表
        dfc_url = "https://xindafengche.souche.com/customer/list"
        print(f"\n导航到大风车: {dfc_url}")
        page.goto(dfc_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)

        print(f"\n页面 URL: {page.url}")
        print(f"页面标题: {page.title()}")

        # 截图看看当前页面
        page.screenshot(path="/tmp/dfc_customer_list.png")
        print("截图已保存: /tmp/dfc_customer_list.png")

        # 查找新增按钮
        add_btn = page.query_selector("button:has-text('新增'), button:has-text('新建'), [class*='add'], a:has-text('新增')")
        if add_btn:
            print(f"\n找到新增按钮: {add_btn.inner_text()}")
            add_btn.click()
            page.wait_for_timeout(3000)
            page.screenshot(path="/tmp/dfc_add_form.png")
            print("新增表单截图: /tmp/dfc_add_form.png")
        else:
            print("\n未找到新增按钮，查看页面内容...")
            # 列出所有按钮
            buttons = page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button, a[class*="btn"], [role="button"]');
                    return Array.from(btns).map(b => ({
                        tag: b.tagName,
                        text: (b.innerText || '').substring(0, 50),
                        class: (b.className || '').substring(0, 80)
                    }));
                }
            """)
            print(f"页面按钮: {json.dumps(buttons[:20], ensure_ascii=False, indent=2)}")

        # 输出捕获的请求
        print(f"\n=== 捕获到 {len(captured)} 个 POST 请求 ===")
        for i, req in enumerate(captured):
            print(f"\n[{i+1}] {req['url'][:100]}")
            if req['body']:
                print(f"    Body: {req['body'][:200]}")


if __name__ == "__main__":
    main()
