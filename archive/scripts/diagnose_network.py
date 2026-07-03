#!/usr/bin/env python3
"""网络诊断：检查 Playwright Chromium 能否正常加载巨懂车登录页的 JS 资源。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_daemon

def main():
    config = sync_daemon.load_config(ROOT / "config" / "config.json")
    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())

    # 清理旧 profile
    if Path(user_data_dir).exists():
        import shutil
        shutil.rmtree(user_data_dir)
        print(f"已删除旧 profile: {user_data_dir}")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=["--disable-session-crashed-bubble", "--disable-gpu"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # 收集所有网络请求
        requests = []
        def on_request(request):
            requests.append({
                "url": request.url,
                "method": request.method,
                "resource_type": request.resource_type,
            })

        def on_response(response):
            status = response.status
            url = response.url
            if status >= 400 or url.endswith('.js') or url.endswith('.css'):
                print(f"[{status}] {url[:120]}")

        page.on("request", on_request)
        page.on("response", on_response)

        print(f"导航到: {config['jvdc']['login_url']}")
        page.goto(config["jvdc"]["login_url"], wait_until="networkidle", timeout=30000)

        page.wait_for_timeout(5000)

        # 统计请求
        by_type = {}
        for req in requests:
            t = req["resource_type"]
            by_type[t] = by_type.get(t, 0) + 1

        print(f"\n总请求数: {len(requests)}")
        print("按类型统计:")
        for t, count in sorted(by_type.items()):
            print(f"  {t}: {count}")

        # 检查 JS 请求
        js_requests = [r for r in requests if r["resource_type"] == "script"]
        print(f"\nJS 请求数: {len(js_requests)}")
        for js in js_requests[:10]:
            print(f"  {js['url'][:120]}")

        # 检查 HTML 中的 script 标签
        html = page.content()
        import re
        scripts = re.findall(r'<script[^>]*src="([^"]*)"', html)
        print(f"\nHTML 中 <script src> 数: {len(scripts)}")
        for s in scripts[:10]:
            print(f"  {s[:120]}")

        # 检查 #root 内容
        root_content = page.evaluate("""
            () => {
                const root = document.getElementById('root');
                return root ? root.innerHTML.length : -1;
            }
        """)
        print(f"\n#root 内容长度: {root_content}")

        # 截图
        from datetime import datetime
        screenshot_path = Path(user_data_dir).parent / f"network-diagnostic-{datetime.now().strftime('%H%M%S')}.png"
        page.screenshot(path=str(screenshot_path))
        print(f"截图已保存: {screenshot_path}")

        ctx.close()

if __name__ == "__main__":
    main()
