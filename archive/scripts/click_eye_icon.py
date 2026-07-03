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
            if 'sh_crm_api' in url:
                try:
                    body = response.json()
                    api_responses.append({
                        'url': url,
                        'status': response.status,
                        'body': body
                    })
                    # 检查是否包含完整手机号（11位，以1开头）
                    body_str = json.dumps(body, ensure_ascii=False)
                    phones = re.findall(r'1[3-9]\d{9}', body_str)
                    if phones and 'customer' in url.lower():
                        print(f"\n[API] {url.split('?')[0].split('/')[-1]}")
                        print(f"  ✅ 包含 {len(phones)} 个完整手机号: {phones[:3]}")
                except:
                    pass

        page.on('response', handle_response)

        list_url = config["jvdc"]["list_url"]
        print(f"\n导航到：{list_url}")
        sync_daemon._navigate_reliable(page, list_url, timeout_ms=30000)

        print(f"\n当前 URL: {page.url}")
        
        # 等待表格加载
        print("等待表格加载...")
        try:
            page.wait_for_selector('table tbody tr', timeout=20000)
            print("✅ 表格已加载")
        except:
            print("⚠️ 表格加载超时，尝试继续...")
        
        page.wait_for_timeout(3000)

        # 查找并点击眼睛图标
        print("\n=== 查找眼睛图标 ===")
        
        # 使用 JavaScript 查找手机号旁边的眼睛图标
        result = page.evaluate("""
            () => {
                // 查找所有包含脱敏手机号的元素
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    const text = el.innerText || el.textContent || '';
                    if (text.includes('138******72') || (text.includes('***') && text.includes('138'))) {
                        // 找到父元素
                        const parent = el.closest('tr') || el.parentElement;
                        if (parent) {
                            // 查找所有 SVG 图标
                            const svgs = parent.querySelectorAll('svg');
                            for (const svg of svgs) {
                                // 检查是否是眼睛图标（通常眼睛图标有特定的 path 或 class）
                                const svgHtml = svg.innerHTML.toLowerCase();
                                const svgClass = (svg.className.baseVal || '').toLowerCase();
                                if (svgHtml.includes('eye') || svgHtml.includes('view') || 
                                    svgClass.includes('eye') || svgClass.includes('view') ||
                                    svgHtml.includes('m12 4.5') || svgHtml.includes('m12 5')) {  // 常见眼睛图标 path
                                    return {
                                        found: true,
                                        tag: svg.tagName,
                                        class: svgClass,
                                        html: svgHtml.substring(0, 100),
                                        parentHtml: parent.innerHTML.substring(0, 200)
                                    };
                                }
                            }
                            // 如果没找到特定的眼睛，返回所有 SVG
                            if (svgs.length > 0) {
                                return {
                                    found: false,
                                    svgCount: svgs.length,
                                    firstSvg: {
                                        tag: svgs[0].tagName,
                                        class: (svgs[0].className.baseVal || '').substring(0, 100),
                                        html: svgs[0].innerHTML.substring(0, 100)
                                    },
                                    parentHtml: parent.innerHTML.substring(0, 300)
                                };
                            }
                        }
                        break;
                    }
                }
                return { found: false, error: '未找到手机号元素' };
            }
        """)
        
        print(f"查找结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
        
        if result.get('found'):
            print("\n=== 点击眼睛图标 ===")
            # 点击眼睛图标
            clicked = page.evaluate("""
                () => {
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        const text = el.innerText || el.textContent || '';
                        if (text.includes('138******72') || (text.includes('***') && text.includes('138'))) {
                            const parent = el.closest('tr') || el.parentElement;
                            if (parent) {
                                const svgs = parent.querySelectorAll('svg');
                                for (const svg of svgs) {
                                    const svgHtml = svg.innerHTML.toLowerCase();
                                    const svgClass = (svg.className.baseVal || '').toLowerCase();
                                    if (svgHtml.includes('eye') || svgHtml.includes('view') || 
                                        svgClass.includes('eye') || svgClass.includes('view') ||
                                        svgHtml.includes('m12 4.5') || svgHtml.includes('m12 5')) {
                                        svg.click();
                                        return { clicked: true };
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
                        const allElements = document.querySelectorAll('*');
                        for (const el of allElements) {
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
                    print(f"\n✅ 找到完整手机号：{phone_text}")
                else:
                    print("\n⚠️ 未检测到完整手机号变化")
        else:
            print("❌ 未找到眼睛图标")
        
        # 输出捕获的 API 响应
        print(f"\n=== 捕获到 {len(api_responses)} 个 CRM API 响应 ===")
        for i, resp in enumerate(api_responses):
            print(f"\n[{i+1}] {resp['url'].split('?')[0].split('/')[-1][:60]}")
            body_str = json.dumps(resp['body'], ensure_ascii=False)
            if len(body_str) < 300:
                print(f"    {body_str}")
        
        # 保存到文件
        with open('/tmp/eye_click_result.json', 'w') as f:
            json.dump(api_responses, f, ensure_ascii=False, indent=2)
        print(f"\nAPI 响应已保存到 /tmp/eye_click_result.json")


if __name__ == "__main__":
    main()
