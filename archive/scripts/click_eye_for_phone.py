#!/usr/bin/env python3
"""点击眼睛图标获取完整手机号。"""

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
            # 捕获所有 CRM API 响应
            if 'sh_crm_api' in url:
                try:
                    body = response.json()
                    api_responses.append({
                        'url': url,
                        'status': response.status,
                        'body': body
                    })
                    print(f"\n[API] {url.split('/')[-1][:50]}")
                    # 检查是否包含完整手机号
                    body_str = json.dumps(body, ensure_ascii=False)
                    if re.search(r'1[3-9]\d{9}', body_str):
                        print(f"  ✅ 包含完整手机号!")
                        # 提取手机号
                        phones = re.findall(r'1[3-9]\d{9}', body_str)
                        for phone in set(phones):
                            print(f"     手机号: {phone}")
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
            print("️ 表格加载超时")
            page.screenshot(path='/tmp/jvdc_page2.png')
            return
        
        page.wait_for_timeout(3000)

        # 查找手机号和眼睛图标
        print("\n=== 查找手机号和眼睛图标 ===")
        
        # 使用 JavaScript 查找包含脱敏手机号的元素及其旁边的眼睛图标
        result = page.evaluate("""
            () => {
                // 查找所有包含脱敏手机号的文本节点
                const allText = document.querySelectorAll('*');
                let phoneElement = null;
                let eyeIcon = null;
                
                for (const el of allText) {
                    const text = el.innerText || el.textContent || '';
                    if (text.includes('138******72') || (text.includes('***') && text.includes('138'))) {
                        phoneElement = {
                            tag: el.tagName,
                            class: el.className,
                            text: text.substring(0, 100),
                            parentTag: el.parentElement?.tagName,
                            parentClass: el.parentElement?.className
                        };
                        
                        // 查找兄弟元素中的眼睛图标
                        const parent = el.parentElement;
                        if (parent) {
                            const siblings = parent.querySelectorAll('svg, span, button, i');
                            for (const sib of siblings) {
                                const sibClass = sib.className || '';
                                const sibHtml = sib.innerHTML || '';
                                if (sibClass.includes('eye') || sibClass.includes('view') || 
                                    sibHtml.includes('eye') || sibHtml.includes('view') ||
                                    sibHtml.includes('')) {
                                    eyeIcon = {
                                        tag: sib.tagName,
                                        class: sibClass.substring(0, 100),
                                        html: sibHtml.substring(0, 100)
                                    };
                                    break;
                                }
                            }
                        }
                        break;
                    }
                }
                
                return { phoneElement, eyeIcon };
            }
        """)
        
        print(f"手机号元素: {json.dumps(result.get('phoneElement'), ensure_ascii=False, indent=2)}")
        print(f"眼睛图标: {json.dumps(result.get('eyeIcon'), ensure_ascii=False, indent=2)}")
        
        if not result.get('phoneElement'):
            print("❌ 未找到手机号元素")
            return
        
        # 尝试直接点击眼睛图标
        print("\n=== 尝试点击眼睛图标 ===")
        
        # 方法1：通过 JavaScript 点击
        clicked = page.evaluate("""
            () => {
                const allText = document.querySelectorAll('*');
                for (const el of allText) {
                    const text = el.innerText || el.textContent || '';
                    if (text.includes('138******72') || (text.includes('***') && text.includes('138'))) {
                        const parent = el.parentElement;
                        if (parent) {
                            // 查找所有可点击的图标
                            const icons = parent.querySelectorAll('svg, span, button, i, a');
                            for (const icon of icons) {
                                const cls = (icon.className || '').toString();
                                const html = icon.innerHTML || '';
                                // 尝试点击看起来像眼睛的图标
                                if (cls.includes('eye') || cls.includes('view') || cls.includes('show') ||
                                    html.includes('eye') || html.includes('view')) {
                                    icon.click();
                                    return { clicked: true, tag: icon.tagName, class: cls.substring(0, 100) };
                                }
                            }
                            // 如果没找到特定的眼睛图标，尝试点击所有图标
                            for (const icon of icons) {
                                if (icon.tagName === 'SVG' || icon.tagName === 'svg') {
                                    icon.click();
                                    return { clicked: true, tag: 'SVG', class: (icon.className || '').toString().substring(0, 100) };
                                }
                            }
                        }
                        break;
                    }
                }
                return { clicked: false };
            }
        """)
        
        print(f"点击结果: {json.dumps(clicked, ensure_ascii=False)}")
        
        if clicked.get('clicked'):
            print("✅ 已点击眼睛图标")
            page.wait_for_timeout(3000)
            
            # 检查手机号是否变成完整的
            phone_text = page.evaluate("""
                () => {
                    const allText = document.querySelectorAll('*');
                    for (const el of allText) {
                        const text = el.innerText || el.textContent || '';
                        if (text.includes('138') && !text.includes('***') && text.length < 30) {
                            const match = text.match(/1[3-9]\\d{9}/);
                            if (match) return match[0];
                        }
                    }
                    return null;
                }
            """)
            
            if phone_text:
                print(f"\n✅ 找到完整手机号: {phone_text}")
            else:
                print("\n⚠️ 未检测到完整手机号变化")
        else:
            print("❌ 点击失败")
        
        # 输出捕获的 API 响应
        print(f"\n=== 捕获到 {len(api_responses)} 个 API 响应 ===")
        for i, resp in enumerate(api_responses[-10:]):  # 只显示最后10个
            print(f"\n[{i+1}] {resp['url'].split('/')[-1][:60]}")
            body_str = json.dumps(resp['body'], ensure_ascii=False)
            if len(body_str) < 300:
                print(f"    {body_str}")
        
        # 保存到文件
        with open('/tmp/eye_click_api.json', 'w') as f:
            json.dump(api_responses, f, ensure_ascii=False, indent=2)
        print(f"\nAPI 响应已保存到 /tmp/eye_click_api.json")


if __name__ == "__main__":
    main()
