#!/usr/bin/env python3
"""拦截巨懂车 API 请求，获取包含完整手机号的原始数据。"""

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

        # 监听所有响应
        def handle_response(response):
            url = response.url
            # 过滤出可能的客户列表 API
            if any(keyword in url.lower() for keyword in [
                "customer", "lead", "profile", "list", "usedcar"
            ]):
                try:
                    if "application/json" in response.headers.get("content-type", ""):
                        body = response.json()
                        api_responses.append({
                            "url": url,
                            "status": response.status,
                            "body": body
                        })
                        print(f"\n📡 API 响应: {url[:100]}...")
                        print(f"   状态: {response.status}")
                except Exception:
                    pass

        page.on("response", handle_response)

        list_url = config["jvdc"]["list_url"]
        print(f"导航到: {list_url}")
        sync_daemon._navigate_reliable(page, list_url, timeout_ms=30000)

        print(f"当前 URL: {page.url}")
        page.wait_for_timeout(5000)

        print(f"\n=== 共拦截到 {len(api_responses)} 个相关 API 响应 ===")

        # 分析每个响应
        for i, resp in enumerate(api_responses):
            print(f"\n--- API {i+1} ---")
            print(f"URL: {resp['url']}")
            body = resp['body']
            
            # 尝试找到包含手机号的数据
            body_str = json.dumps(body, ensure_ascii=False)
            
            # 检查是否有手机号
            import re
            phones = re.findall(r'1[3-9]\d{9}', body_str)
            if phones:
                print(f"✅ 包含 {len(phones)} 个完整手机号: {phones[:5]}")
            
            # 检查数据结构
            if isinstance(body, dict):
                print(f"顶层 keys: {list(body.keys())[:10]}")
                if 'data' in body:
                    data = body['data']
                    if isinstance(data, dict):
                        print(f"data keys: {list(data.keys())[:10]}")
                    elif isinstance(data, list):
                        print(f"data 是列表，长度: {len(data)}")
                        if data:
                            print(f"第一条记录 keys: {list(data[0].keys()) if isinstance(data[0], dict) else type(data[0])}")

        # 保存所有 API 响应供分析
        dump_path = ROOT / "api_responses.json"
        with open(dump_path, "w", encoding="utf-8") as f:
            json.dump(api_responses, f, ensure_ascii=False, indent=2)
        print(f"\nAPI 响应已保存到: {dump_path}")


if __name__ == "__main__":
    main()
