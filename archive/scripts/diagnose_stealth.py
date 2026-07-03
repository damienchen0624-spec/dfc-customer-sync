#!/usr/bin/env python3
"""反检测诊断：检查是否是 Playwright 自动化被网站识别导致 React 不渲染。

检查项：
1. navigator.webdriver 是否为 true（自动化检测标志）
2. 加入反检测参数后页面是否正常渲染
3. 监控 #root 的 DOM 变化（MutationObserver）
4. 检查是否有 iframe 嵌套
5. 检查 JS 是否真的执行了（注入追踪脚本）
"""

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

    # 清理旧 profile
    if Path(user_data_dir).exists():
        shutil.rmtree(user_data_dir)
        print(f"已删除旧 profile: {user_data_dir}")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # 加入反检测参数
        ctx = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=[
                "--disable-session-crashed-bubble",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # 在页面加载前注入脚本：隐藏 webdriver 标志 + 监控 root 变化
        page.add_init_script("""
            // 隐藏自动化标志
            Object.defineProperty(navigator, 'webdriver', { get: () => false });

            // 监控 #root 的 DOM 变化
            window.__rootChanges = [];
            const observer = new MutationObserver((mutations) => {
                for (const m of mutations) {
                    window.__rootChanges.push({
                        type: m.type,
                        addedNodes: m.addedNodes.length,
                        removedNodes: m.removedNodes.length,
                        timestamp: Date.now()
                    });
                }
            });

            // 监控 JS 执行
            window.__scriptExecutions = [];
            const origCreateElement = document.createElement.bind(document);
            document.createElement = function(tag) {
                const el = origCreateElement(tag);
                if (tag === 'script') {
                    window.__scriptExecutions.push({ created: true, time: Date.now() });
                }
                return el;
            };

            // 页面加载完成后启动 observer
            document.addEventListener('DOMContentLoaded', () => {
                const root = document.getElementById('root');
                if (root) {
                    observer.observe(root, { childList: true, subtree: true });
                    console.log('[DIAG] MutationObserver attached to #root');
                } else {
                    console.log('[DIAG] #root not found at DOMContentLoaded');
                }
            });
        """)

        # 收集所有 console 消息和网络请求
        console_msgs = []
        def on_console(msg):
            console_msgs.append(f"[{msg.type}] {msg.text}")
            print(f"[CONSOLE {msg.type.upper()}] {msg.text[:200]}")

        def on_pageerror(error):
            console_msgs.append(f"[PAGE ERROR] {error}")
            print(f"[PAGE ERROR] {error}")

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)

        # 监控网络请求
        all_responses = []
        def on_response(response):
            all_responses.append({
                "url": response.url,
                "status": response.status,
                "type": response.request.resource_type,
            })
            if response.status >= 400:
                print(f"[HTTP {response.status}] {response.url[:120]}")

        page.on("response", on_response)

        print(f"导航到: {config['jvdc']['login_url']}")
        page.goto(config["jvdc"]["login_url"], wait_until="networkidle", timeout=30000)

        # 等待足够时间让 React 渲染
        print("等待 10 秒让 React 初始化...")
        page.wait_for_timeout(10000)

        # 检查 webdriver 标志
        webdriver_flag = page.evaluate("() => navigator.webdriver")
        print(f"\nnavigator.webdriver = {webdriver_flag}")

        # 检查 #root 内容
        root_info = page.evaluate("""
            () => {
                const root = document.getElementById('root');
                return {
                    exists: !!root,
                    innerHTML_length: root ? root.innerHTML.length : -1,
                    innerHTML: root ? root.innerHTML.substring(0, 500) : '',
                    childNodes: root ? root.childNodes.length : 0,
                };
            }
        """)
        print(f"\n#root 信息: {json.dumps(root_info, indent=2)}")

        # 检查 DOM 变化记录
        root_changes = page.evaluate("() => window.__rootChanges || []")
        print(f"\n#root DOM 变化次数: {len(root_changes)}")
        if root_changes:
            for change in root_changes[:5]:
                print(f"  {change}")

        # 检查 iframe
        frames = page.frames
        print(f"\n页面 frame 数: {len(frames)}")
        for i, frame in enumerate(frames):
            print(f"  frame[{i}]: {frame.url[:120]}")

        # 检查页面最终 URL（是否有重定向）
        print(f"\n最终 URL: {page.url}")

        # 检查 body 完整 HTML
        body_html = page.evaluate("() => document.body.innerHTML")
        print(f"\nBody HTML 长度: {len(body_html)}")
        print(f"Body HTML 前 1000 字符:\n{body_html[:1000]}")

        # 检查所有 script 标签及其状态
        script_info = page.evaluate("""
            () => {
                const scripts = document.querySelectorAll('script');
                return Array.from(scripts).map((s, i) => ({
                    index: i,
                    src: s.src || '(inline)',
                    defer: s.defer,
                    async: s.async,
                    type: s.type || '(default)',
                    loaded: s.src ? (s.readyState || 'unknown') : 'n/a',
                }));
            }
        """)
        print(f"\nScript 标签详情 ({len(script_info)} 个):")
        for s in script_info:
            print(f"  [{s['index']}] src={s['src'][:80]} defer={s['defer']} async={s['async']} type={s['type']}")

        # 网络请求统计
        by_type = {}
        for r in all_responses:
            t = r["type"]
            by_type[t] = by_type.get(t, 0) + 1
        print(f"\n网络请求统计 (总 {len(all_responses)} 个):")
        for t, count in sorted(by_type.items()):
            print(f"  {t}: {count}")

        # 检查失败的请求
        failed = [r for r in all_responses if r["status"] >= 400]
        if failed:
            print(f"\n失败的请求 ({len(failed)} 个):")
            for r in failed[:10]:
                print(f"  [{r['status']}] {r['url'][:120]}")

        # 截图
        screenshot_path = Path(user_data_dir).parent / f"stealth-diagnostic-{datetime.now().strftime('%H%M%S')}.png"
        page.screenshot(path=str(screenshot_path))
        print(f"\n截图已保存: {screenshot_path}")

        # 尝试手动触发 React 渲染
        print("\n尝试手动触发 React 渲染...")
        try:
            result = page.evaluate("""
                () => {
                    // 检查是否有 React 内部实例
                    const root = document.getElementById('root');
                    if (!root) return { error: 'no root element' };
                    
                    // 检查 React fiber
                    const fiberKey = Object.keys(root).find(k => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$'));
                    const containerKey = Object.keys(root).find(k => k.startsWith('__reactContainer$'));
                    
                    return {
                        hasFiberKey: !!fiberKey,
                        fiberKey: fiberKey || null,
                        hasContainerKey: !!containerKey,
                        containerKey: containerKey || null,
                        rootKeys: Object.keys(root).filter(k => k.startsWith('__')),
                    };
                }
            """)
            print(f"React 内部状态: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"检查 React 状态失败: {e}")

        ctx.close()
        print("\n诊断完成。")


if __name__ == "__main__":
    main()
