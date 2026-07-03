#!/usr/bin/env python3
"""XHR 诊断：抓取 React 渲染前的 API 请求/响应，找出渲染为空的原因。"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_daemon


def main():
    config = sync_daemon.load_config(ROOT / "config" / "config.json")
    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())

    if Path(user_data_dir).exists():
        shutil.rmtree(user_data_dir)
        print(f"已删除旧 profile: {user_data_dir}")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=[
                "--disable-session-crashed-bubble",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)

        # 收集所有请求的详细信息（包括 XHR）
        xhr_details = []

        def on_response(response):
            url = response.url
            req_type = response.request.resource_type
            status = response.status

            # 记录所有非静态资源的请求
            if req_type in ("xhr", "fetch", "document") or "/api/" in url or "config" in url:
                try:
                    body = response.text()
                except Exception:
                    body = "(无法读取 body)"

                xhr_details.append({
                    "url": url,
                    "method": response.request.method,
                    "status": status,
                    "type": req_type,
                    "request_headers": dict(response.request.headers),
                    "response_headers": dict(response.headers),
                    "body_length": len(body),
                    "body_preview": body[:2000],
                })
                print(f"\n[XHR/FETCH {status}] {url[:150]}")
                print(f"  Method: {response.request.method}")
                print(f"  Body 前 500 字符: {body[:500]}")

        page.on("response", on_response)

        # 也监控 console
        def on_console(msg):
            print(f"[CONSOLE {msg.type.upper()}] {msg.text[:200]}")

        def on_pageerror(error):
            print(f"[PAGE ERROR] {error}")

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)

        print(f"导航到: {config['jvdc']['login_url']}")
        page.goto(config["jvdc"]["login_url"], wait_until="networkidle", timeout=30000)

        # 等待足够时间
        page.wait_for_timeout(8000)

        # 检查 #root
        root_len = page.evaluate("() => (document.getElementById('root')?.innerHTML.length) ?? -1")
        print(f"\n最终 #root 内容长度: {root_len}")

        # 检查所有 XHR 详情
        print(f"\n=== 捕获到 {len(xhr_details)} 个 XHR/API 请求 ===")
        for i, detail in enumerate(xhr_details):
            print(f"\n--- 请求 {i+1} ---")
            print(f"URL: {detail['url']}")
            print(f"Method: {detail['method']}")
            print(f"Status: {detail['status']}")
            print(f"Type: {detail['type']}")
            print(f"Body 长度: {detail['body_length']}")
            print(f"Body 预览: {detail['body_preview'][:1000]}")

        # 检查页面是否有路由 hash 或 query params
        print(f"\n当前 URL: {page.url}")
        print(f"Hash: {page.evaluate('() => location.hash')}")
        print(f"Search: {page.evaluate('() => location.search')}")

        # 检查 localStorage / sessionStorage 是否有初始数据
        storage_info = page.evaluate("""
            () => {
                const ls = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    ls[key] = localStorage.getItem(key).substring(0, 200);
                }
                const ss = {};
                for (let i = 0; i < sessionStorage.length; i++) {
                    const key = sessionStorage.key(i);
                    ss[key] = sessionStorage.getItem(key).substring(0, 200);
                }
                return { localStorage: ls, sessionStorage: ss };
            }
        """)
        print(f"\nlocalStorage: {json.dumps(storage_info['localStorage'], indent=2, ensure_ascii=False)}")
        print(f"\nsessionStorage: {json.dumps(storage_info['sessionStorage'], indent=2, ensure_ascii=False)}")

        # 截图
        screenshot_path = Path(user_data_dir).parent / f"xhr-diagnostic-{datetime.now().strftime('%H%M%S')}.png"
        page.screenshot(path=str(screenshot_path))
        print(f"\n截图已保存: {screenshot_path}")

        ctx.close()
        print("\n诊断完成。")


if __name__ == "__main__":
    main()
