#!/usr/bin/env python3
"""尝试直接调用解密 API 获取完整手机号。"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_daemon
import auth
from playwright.sync_api import sync_playwright


def main():
    config = sync_daemon.load_config(ROOT / "config" / "config.json")
    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
    storage_path = sync_daemon._storage_state_path(config)

    print("启动 Chrome CDP...")
    sync_daemon._start_chrome_cdp(user_data_dir, port=9222, timeout_sec=30)

    # 从之前的 API 响应中获取加密手机号
    encrypt_phone = "@LFOHJhSu59s65dQ+gzENIM8bs8dXkBb5H+p5kDzzqSk="
    phone_encoded = "#IdnT1SDKIXaNeMwQAkl2FMmOnTUusicuNB+0EIxC2FSlfdfFO27f8wB5Wb9..."

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
                    body_str = json.dumps(body, ensure_ascii=False)
                    phones = re.findall(r'1[3-9]\d{9}', body_str)
                    if phones:
                        print(f"\n[API] {url.split('?')[0].split('/')[-1]}")
                        print(f"  ✅ 包含手机号：{phones}")
                except:
                    pass

        page.on('response', handle_response)

        # 先导航到页面
        list_url = config["jvdc"]["list_url"]
        print(f"\n导航到：{list_url}")
        sync_daemon._navigate_reliable(page, list_url, timeout_ms=30000)
        page.wait_for_timeout(3000)

        # 尝试多种可能的解密 API
        base_url = "https://www.autoengine.com/motor/sh_crm_api"
        
        # 获取 token
        token = auth.get_token()
        print(f"\nToken: {token[:20]}...")

        # 尝试调用可能的解密 API
        decrypt_urls = [
            f"{base_url}/saas/customer/decrypt_phone/?account_type=9",
            f"{base_url}/common/phone/decrypt/?account_type=9",
            f"{base_url}/saas/customer/phone_detail/?account_type=9",
            f"{base_url}/saas/customer/get_phone/?account_type=9",
        ]

        for url in decrypt_urls:
            print(f"\n尝试：{url}")
            try:
                response = page.evaluate("""
                    async (params) => {
                        const resp = await fetch(params.url, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                encrypt_phone: params.encrypt_phone,
                                phone_encoded: params.phone_encoded
                            })
                        });
                        return await resp.json();
                    }
                """, {
                    'url': url,
                    'encrypt_phone': encrypt_phone,
                    'phone_encoded': phone_encoded
                })
                
                print(f"  响应：{json.dumps(response, ensure_ascii=False)[:200]}")
                
                # 检查是否包含手机号
                resp_str = json.dumps(response, ensure_ascii=False)
                phones = re.findall(r'1[3-9]\d{9}', resp_str)
                if phones:
                    print(f"  ✅ 找到手机号：{phones}")
                    break
            except Exception as e:
                print(f"  错误：{e}")

        # 输出所有捕获的 API
        print(f"\n=== 捕获到 {len(api_responses)} 个 API ===")
        for i, resp in enumerate(api_responses[-5:]):
            print(f"[{i+1}] {resp['url'].split('?')[0].split('/')[-1]}")
        
        # 保存到文件
        with open('/tmp/decrypt_attempt.json', 'w') as f:
            json.dump(api_responses, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
