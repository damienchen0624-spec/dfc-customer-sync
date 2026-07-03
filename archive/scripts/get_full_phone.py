#!/usr/bin/env python3
"""通过点击复制按钮或查看元素获取完整手机号。"""

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

        # 方法1：查找包含完整手机号的元素属性
        print("\n=== 方法1：查找元素属性中的手机号 ===")
        try:
            # 查找所有包含手机号格式的元素
            phone_elements = page.evaluate("""
                () => {
                    const results = [];
                    // 查找所有元素
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        // 检查属性
                        for (const attr of el.attributes) {
                            if (attr.value && /1[3-9]\\d{9}/.test(attr.value)) {
                                results.push({
                                    tag: el.tagName,
                                    attr: attr.name,
                                    value: attr.value,
                                    text: el.textContent?.substring(0, 100)
                                });
                            }
                        }
                        // 检查 data 属性
                        if (el.dataset) {
                            for (const [key, value] of Object.entries(el.dataset)) {
                                if (value && /1[3-9]\\d{9}/.test(value)) {
                                    results.push({
                                        tag: el.tagName,
                                        attr: 'data-' + key,
                                        value: value,
                                        text: el.textContent?.substring(0, 100)
                                    });
                                }
                            }
                        }
                    }
                    return results;
                }
            """)
            print(f"找到 {len(phone_elements)} 个包含手机号的属性")
            for item in phone_elements[:5]:
                print(f"  {item['tag']}[{item['attr']}]: {item['value'][:50]}...")
        except Exception as e:
            print(f"方法1失败: {e}")

        # 方法2：点击第一条记录的"查看"进入详情页
        print("\n=== 方法2：进入详情页获取手机号 ===")
        try:
            # 点击第一个"查看"链接
            view_link = page.query_selector('span.arco-link:has-text("查看")')
            if view_link:
                view_link.click()
                page.wait_for_timeout(3000)
                
                # 在详情页查找手机号
                detail_url = page.url
                print(f"详情页 URL: {detail_url}")
                
                # 查找页面上的手机号
                detail_phones = page.evaluate("""
                    () => {
                        const results = [];
                        const text = document.body.innerText;
                        const matches = text.match(/1[3-9]\\d{9}/g);
                        if (matches) {
                            results.push(...new Set(matches));
                        }
                        return results;
                    }
                """)
                print(f"详情页找到的手机号: {detail_phones}")
                
                # 查找详情页的 API 响应
                # 通常详情页会有单独的 API
                
                # 返回
                page.go_back()
                page.wait_for_timeout(2000)
        except Exception as e:
            print(f"方法2失败: {e}")

        # 方法3：尝试获取 React 组件的 props/state
        print("\n=== 方法3：尝试从 React 组件获取数据 ===")
        try:
            react_data = page.evaluate("""
                () => {
                    // 尝试从 React fiber 中获取数据
                    const rootEl = document.querySelector('[data-reactroot]') || 
                                   document.getElementById('root') || 
                                   document.getElementById('app');
                    
                    if (!rootEl) return null;
                    
                    // 尝试获取 fiber
                    const fiberKey = Object.keys(rootEl).find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
                    if (!fiberKey) return 'no-fiber-key';
                    
                    const fiber = rootEl[fiberKey];
                    
                    // 递归查找包含手机号的 props
                    function findPhoneInObj(obj, path = '', depth = 0) {
                        if (depth > 10) return null;
                        if (!obj || typeof obj !== 'object') return null;
                        
                        for (const [key, value] of Object.entries(obj)) {
                            if (typeof value === 'string' && /1[3-9]\\d{9}/.test(value)) {
                                return { path: path + '.' + key, value };
                            }
                            if (typeof value === 'object') {
                                const found = findPhoneInObj(value, path + '.' + key, depth + 1);
                                if (found) return found;
                            }
                        }
                        return null;
                    }
                    
                    // 遍历 fiber tree
                    let current = fiber;
                    let count = 0;
                    while (current && count < 100) {
                        if (current.memoizedProps) {
                            const found = findPhoneInObj(current.memoizedProps, 'props');
                            if (found) return found;
                        }
                        current = current.child || current.sibling || current.return?.sibling;
                        count++;
                    }
                    
                    return 'not-found-in-fiber';
                }
            """)
            print(f"React 数据: {react_data}")
        except Exception as e:
            print(f"方法3失败: {e}")


if __name__ == "__main__":
    main()
