#!/usr/bin/env python3
"""用浏览器抓包大风车新增客户 API。"""

import json
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

    captured_posts = []
    captured_responses = []

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def handle_request(request):
            url = request.url
            if request.method == "POST" and "souche.com" in url:
                body = request.post_data or ""
                captured_posts.append({
                    "url": url,
                    "body": body[:3000] if body else "",
                    "headers": dict(request.headers),
                })

        def handle_response(response):
            url = response.url
            if "souche.com" in url and ("add" in url.lower() or "save" in url.lower() or "create" in url.lower()):
                try:
                    body = response.json()
                    captured_responses.append({
                        "url": url,
                        "status": response.status,
                        "body": body,
                    })
                    print(f"\n[CAPTURED] {url}")
                    print(f"  Status: {response.status}")
                    print(f"  Body: {json.dumps(body, ensure_ascii=False)[:500]}")
                except:
                    pass

        page.on("request", handle_request)
        page.on("response", handle_response)

        # 打开大风车
        dfc_url = "https://xindafengche.souche.com/"
        print(f"\n导航到大风车: {dfc_url}")
        page.goto(dfc_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        print(f"当前 URL: {page.url}")

        # 导航到客户列表
        list_url = "https://xindafengche.souche.com/customer/list"
        print(f"\n导航到客户列表: {list_url}")
        page.goto(list_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        print(f"当前 URL: {page.url}")

        # 截图
        page.screenshot(path="/tmp/dfc_list.png")
        print("截图: /tmp/dfc_list.png")

        # 查找新增按钮
        buttons = page.evaluate("""
            () => {
                const btns = document.querySelectorAll('button, a, [role="button"], [class*="add"], [class*="btn"]');
                return Array.from(btns).map(b => ({
                    tag: b.tagName,
                    text: (b.innerText || b.textContent || '').trim().substring(0, 50),
                    class: (b.className || '').toString().substring(0, 100),
                    href: b.href || '',
                    visible: b.offsetParent !== null
                })).filter(b => b.visible && b.text);
            }
        """)
        
        print(f"\n页面可见按钮/链接 ({len(buttons)} 个):")
        for b in buttons[:30]:
            if b['text']:
                print(f"  {b['tag']} | {b['text'][:40]} | class={b['class'][:50]}")

        # 尝试找新增客户按钮
        add_btn = page.query_selector("button:has-text('新增'), button:has-text('新建'), button:has-text('添加'), a:has-text('新增客户')")
        if add_btn:
            text = add_btn.inner_text()
            print(f"\n✅ 找到新增按钮: '{text}'")
            
            # 清空捕获
            captured_posts.clear()
            
            # 点击
            add_btn.click()
            page.wait_for_timeout(3000)
            page.screenshot(path="/tmp/dfc_add_form.png")
            print(f"点击后 URL: {page.url}")
            print("表单截图: /tmp/dfc_add_form.png")
            
            # 输出捕获的请求
            print(f"\n=== 点击后捕获到 {len(captured_posts)} 个 POST 请求 ===")
            for i, req in enumerate(captured_posts):
                print(f"\n[{i+1}] {req['url'][:120]}")
                if req['body']:
                    print(f"    Body: {req['body'][:300]}")
        else:
            print("\n❌ 未找到新增按钮")


if __name__ == "__main__":
    main()
