#!/usr/bin/env python3
"""通过浏览器访问大风车后台，抓取新增客户的 API 调用。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auth
from playwright.sync_api import sync_playwright


def main():
    # 获取认证
    token = auth.get_token()
    account = auth.get_account_info(token)
    shop_code = account["shopCode"]
    
    print(f"Token: {token[:50]}...")
    print(f"门店: {account['shopName']} ({shop_code})")
    
    # 启动浏览器
    with sync_playwright() as p:
        # 使用已有的浏览器上下文
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        # 设置 cookies 和 storage state
        context.add_cookies([{
            'name': 'souche-security-token',
            'value': token,
            'domain': '.souche.com',
            'path': '/'
        }])
        
        page = context.new_page()
        
        # 监听 API 请求
        api_calls = []
        
        def handle_request(request):
            url = request.url
            if 'add' in url.lower() and 'customer' in url.lower():
                print(f"\n[API 请求] {request.method} {url}")
                if request.post_data:
                    try:
                        body = json.loads(request.post_data)
                        print(f"  Body: {json.dumps(body, ensure_ascii=False)[:500]}")
                    except:
                        print(f"  Body: {request.post_data[:500]}")
                api_calls.append({
                    'url': url,
                    'method': request.method,
                    'post_data': request.post_data
                })
        
        page.on('request', handle_request)
        
        # 访问大风车后台
        print("\n访问大风车后台...")
        page.goto('https://xindafengche.souche.com/', timeout=30000)
        page.wait_for_timeout(3000)
        
        print(f"当前 URL: {page.url}")
        
        # 尝试找到新增客户按钮
        print("\n查找新增客户入口...")
        
        # 截图看看当前页面
        page.screenshot(path='/tmp/dfc_home.png')
        print("已保存截图到 /tmp/dfc_home.png")
        
        # 等待用户操作
        print("\n请在浏览器中手动新增一个客户，按 Enter 继续...")
        input()
        
        # 输出捕获的 API 调用
        print(f"\n=== 捕获到 {len(api_calls)} 个 API 调用 ===")
        for i, call in enumerate(api_calls):
            print(f"\n[{i+1}] {call['method']} {call['url']}")
            if call['post_data']:
                try:
                    body = json.loads(call['post_data'])
                    print(f"  Body: {json.dumps(body, ensure_ascii=False, indent=2)[:1000]}")
                except:
                    print(f"  Body: {call['post_data'][:1000]}")
        
        # 保存 API 调用到文件
        with open('/tmp/dfc_api_calls.json', 'w') as f:
            json.dump(api_calls, f, ensure_ascii=False, indent=2)
        print(f"\nAPI 调用已保存到 /tmp/dfc_api_calls.json")
        
        browser.close()


if __name__ == "__main__":
    main()
