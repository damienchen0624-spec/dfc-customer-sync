#!/usr/bin/env python3
"""捕获页面加载时的所有 API 响应，找出包含完整手机号的 API。"""

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
            if 'sh_crm_api' in url or 'autoengine.com' in url:
                try:
                    body = response.json()
                    api_responses.append({
                        'url': url,
                        'status': response.status,
                        'body': body
                    })
                    # 检查是否包含完整手机号
                    body_str = json.dumps(body, ensure_ascii=False)
                    phones = re.findall(r'1[3-9]\d{9}', body_str)
                    if phones:
                        print(f"\n[API] {url.split('?')[0].split('/')[-1][:60]}")
                        print(f"  状态: {response.status}")
                        print(f"  ✅ 包含 {len(phones)} 个完整手机号")
                        print(f"  前 5 个: {phones[:5]}")
                except:
                    pass

        page.on('response', handle_response)

        list_url = config["jvdc"]["list_url"]
        print(f"\n导航到：{list_url}")
        sync_daemon._navigate_reliable(page, list_url, timeout_ms=30000)

        print(f"\n当前 URL: {page.url}")
        page.wait_for_timeout(5000)  # 等待 5 秒让所有 API 完成

        # 输出统计
        print(f"\n=== 总共捕获 {len(api_responses)} 个 API 响应 ===")
        
        # 找到包含手机号的 API
        phone_apis = []
        for i, resp in enumerate(api_responses):
            body_str = json.dumps(resp['body'], ensure_ascii=False)
            phones = re.findall(r'1[3-9]\d{9}', body_str)
            if phones:
                phone_apis.append({
                    'index': i,
                    'url': resp['url'],
                    'phones': phones,
                    'body': resp['body']
                })
        
        print(f"\n=== 找到 {len(phone_apis)} 个包含手机号的 API ===")
        for api in phone_apis:
            print(f"\n[{api['index']+1}] {api['url']}")
            print(f"    手机号数量：{len(api['phones'])}")
            print(f"    前 5 个：{api['phones'][:5]}")
            
            # 分析响应结构
            if isinstance(api['body'], dict):
                print(f"    响应结构:")
                for key in list(api['body'].keys())[:10]:
                    val = api['body'][key]
                    if isinstance(val, list):
                        print(f"      {key}: list[{len(val)}]")
                        if len(val) > 0 and isinstance(val[0], dict):
                            # 输出第一个元素的字段
                            print(f"        字段：{list(val[0].keys())[:15]}")
                    elif isinstance(val, dict):
                        print(f"      {key}: dict")
                    else:
                        print(f"      {key}: {str(val)[:100]}")
        
        # 保存到文件
        with open('/tmp/all_api_responses.json', 'w') as f:
            json.dump(api_responses, f, ensure_ascii=False, indent=2)
        print(f"\n所有 API 响应已保存到 /tmp/all_api_responses.json")


if __name__ == "__main__":
    main()
