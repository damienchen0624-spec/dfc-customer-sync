#!/usr/bin/env python3
"""检查 list_url 在无登录态时的跳转行为，找到新的登录入口。"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_daemon


def main():
    config = sync_daemon.load_config(ROOT / "config" / "config.json")
    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())

    # 用全新 profile（无登录态）
    if Path(user_data_dir).exists():
        shutil.rmtree(user_data_dir)
        print(f"已删除旧 profile（确保无登录态）: {user_data_dir}")

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

        # 记录所有导航/跳转
        navigations = []
        def on_request(request):
            if request.resource_type == "document":
                navigations.append(request.url)
                print(f"[NAV] {request.url}")

        page.on("request", on_request)

        # 打开客户列表页（无登录态）
        list_url = config["jvdc"]["list_url"]
        print(f"\n导航到客户列表页: {list_url}")
        page.goto(list_url, wait_until="networkidle", timeout=30000)

        page.wait_for_timeout(5000)

        print(f"\n最终 URL: {page.url}")
        print(f"导航历史: {navigations}")

        # 检查页面内容
        title = page.title()
        body_text = page.evaluate("() => document.body.innerText.substring(0, 500)")
        root_len = page.evaluate("() => (document.getElementById('root')?.innerHTML.length) ?? -1")

        print(f"\n页面标题: {title}")
        print(f"Body 文本前 500 字符: {body_text}")
        print(f"#root 内容长度: {root_len}")

        # 截图
        from datetime import datetime
        screenshot_path = Path(user_data_dir).parent / f"redirect-check-{datetime.now().strftime('%H%M%S')}.png"
        page.screenshot(path=str(screenshot_path))
        print(f"\n截图已保存: {screenshot_path}")

        # 检查页面中是否有登录相关的链接/表单
        login_elements = page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a')).map(a => ({
                    href: a.href,
                    text: a.innerText.trim()
                })).filter(a => a.text.toLowerCase().includes('login') || a.text.includes('登录') || a.href.includes('login'));

                const forms = Array.from(document.querySelectorAll('form')).map(f => ({
                    action: f.action,
                    method: f.method,
                    inputs: Array.from(f.querySelectorAll('input')).map(i => ({
                        type: i.type,
                        name: i.name,
                        placeholder: i.placeholder
                    }))
                }));

                return { links, forms };
            }
        """)
        print(f"\n页面中的登录相关元素: {login_elements}")

        # 也检查 iframe
        frames = page.frames
        print(f"\nFrame 数: {len(frames)}")
        for i, frame in enumerate(frames):
            print(f"  frame[{i}]: {frame.url[:150]}")

        ctx.close()
        print("\n检查完成。")


if __name__ == "__main__":
    main()
