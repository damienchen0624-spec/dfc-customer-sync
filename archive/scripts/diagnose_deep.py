#!/usr/bin/env python3
"""深度诊断：检查 JS 执行情况和 DOM 结构。"""

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

        # 收集所有错误
        errors = []
        def on_console(msg):
            errors.append(f"[{msg.type}] {msg.text}")
            print(f"[{msg.type.upper()}] {msg.text[:200]}")

        def on_pageerror(error):
            errors.append(f"[PAGE ERROR] {error}")
            print(f"[PAGE ERROR] {error}")

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)

        print(f"导航到：{config['jvdc']['login_url']}")
        page.goto(config["jvdc"]["login_url"], wait_until="networkidle", timeout=30000)

        # 等待更长时间让 React 完全初始化
        page.wait_for_timeout(8000)

        # 检查完整的 DOM 结构
        dom_info = page.evaluate("""
            () => {
                const body = document.body;
                const root = document.getElementById('root');
                const app = document.getElementById('app');
                
                // 检查所有可能的 React 挂载点
                const possibleRoots = [];
                ['root', 'app', 'mount', 'main', 'container'].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) {
                        possibleRoots.push({
                            id: id,
                            innerHTML_length: el.innerHTML.length,
                            childNodes: el.childNodes.length,
                            className: el.className
                        });
                    }
                });

                // 检查 React 是否已加载
                const hasReact = typeof React !== 'undefined';
                const hasReactDOM = typeof ReactDOM !== 'undefined';

                // 检查是否有未处理的 Promise 拒绝
                const unhandledRejections = window.__unhandledRejections || [];

                return {
                    body_innerHTML_length: body.innerHTML.length,
                    body_childNodes: body.childNodes.length,
                    root_exists: !!root,
                    root_innerHTML_length: root ? root.innerHTML.length : -1,
                    app_exists: !!app,
                    possibleRoots: possibleRoots,
                    hasReact: hasReact,
                    hasReactDOM: hasReactDOM,
                    unhandledRejections: unhandledRejections.length,
                    script_tags: document.querySelectorAll('script').length,
                    total_elements: document.querySelectorAll('*').length
                };
            }
        """)

        print("\n=== DOM 诊断信息 ===")
        print(json.dumps(dom_info, indent=2, ensure_ascii=False))

        # 检查 body 的实际内容
        body_html = page.evaluate("() => document.body.innerHTML")
        print(f"\n=== Body HTML (前 2000 字符) ===")
        print(body_html[:2000])

        # 检查是否有 React 相关的全局变量
        react_globals = page.evaluate("""
            () => {
                const globals = [];
                for (let key in window) {
                    if (key.toLowerCase().includes('react') || key.toLowerCase().includes('app')) {
                        globals.push(key);
                    }
                }
                return globals;
            }
        """)
        print(f"\n=== React 相关全局变量 ===")
        print(react_globals)

        # 截图
        from datetime import datetime
        screenshot_path = Path(user_data_dir).parent / f"deep-diagnostic-{datetime.now().strftime('%H%M%S')}.png"
        page.screenshot(path=str(screenshot_path))
        print(f"\n截图已保存：{screenshot_path}")

        # 保存完整 HTML
        html_path = Path(user_data_dir).parent / f"page-source-{datetime.now().strftime('%H%M%S')}.html"
        html_content = page.content()
        html_path.write_text(html_content, encoding='utf-8')
        print(f"HTML 已保存：{html_path}")

        ctx.close()

if __name__ == "__main__":
    main()
