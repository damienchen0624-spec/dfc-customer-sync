#!/usr/bin/env python3
"""从巨懂车页面的 JavaScript 数据中提取完整手机号。"""

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

        list_url = config["jvdc"]["list_url"]
        print(f"导航到: {list_url}")
        sync_daemon._navigate_reliable(page, list_url, timeout_ms=30000)

        print(f"当前 URL: {page.url}")
        page.wait_for_timeout(3000)

        # 方法1：从页面 HTML 中提取所有完整手机号（11位数字）
        print("\n=== 方法1：从 HTML 提取完整手机号 ===")
        html = page.content()
        phones = re.findall(r'1[3-9]\d{9}', html)
        unique_phones = list(set(phones))
        print(f"找到 {len(unique_phones)} 个完整手机号: {unique_phones[:10]}")

        # 方法2：尝试从页面的 JavaScript 变量中提取
        print("\n=== 方法2：从 JS 上下文提取数据 ===")
        try:
            # 尝试获取 __NEXT_DATA__ 或类似的 SSR 数据
            next_data = page.evaluate("""
                () => {
                    // 尝试常见的数据源
                    if (window.__NEXT_DATA__) return JSON.stringify(window.__NEXT_DATA__);
                    if (window.__INITIAL_STATE__) return JSON.stringify(window.__INITIAL_STATE__);
                    if (window.__NUXT__) return JSON.stringify(window.__NUXT__);
                    
                    // 尝试从 React fiber 中获取
                    const rootEl = document.getElementById('root') || document.getElementById('app');
                    if (rootEl && rootEl._reactRootContainer) {
                        return 'react-found';
                    }
                    
                    return null;
                }
            """)
            if next_data:
                print(f"找到 JS 数据源: {str(next_data)[:200]}...")
        except Exception as e:
            print(f"JS 提取失败: {e}")

        # 方法3：点击"查看"按钮进入详情页获取完整手机号
        print("\n=== 方法3：点击第一条记录的'查看'按钮 ===")
        try:
            # 找到第一个"查看"链接
            view_links = page.query_selector_all('span.arco-link:has-text("查看")')
            if view_links:
                print(f"找到 {len(view_links)} 个'查看'按钮")
                first_view = view_links[0]
                first_view.click()
                page.wait_for_timeout(3000)
                
                # 在详情页查找手机号
                detail_html = page.content()
                detail_phones = re.findall(r'1[3-9]\d{9}', detail_html)
                print(f"详情页找到 {len(detail_phones)} 个完整手机号: {detail_phones[:5]}")
                
                # 返回
                page.go_back()
                page.wait_for_timeout(2000)
        except Exception as e:
            print(f"点击失败: {e}")

        # 方法4：拦截 XHR 请求
        print("\n=== 方法4：检查网络请求 ===")
        print("提示：巨懂车可能通过 API 获取客户数据，可以尝试拦截 API 响应")


if __name__ == "__main__":
    main()
