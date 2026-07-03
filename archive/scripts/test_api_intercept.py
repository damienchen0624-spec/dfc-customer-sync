#!/usr/bin/env python3
"""通过浏览器拦截实际请求来验证 API 端点。"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import auth
import dfc_browser_writer


def main():
    # 1. 初始化
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    
    dfc_browser_dir = str(Path(config["browser"]["user_data_dir"]).expanduser().parent / "dfc-browser")
    
    # 2. 获取门店信息
    token = auth.get_token()
    account = auth.get_account_info(token)
    shop_code = account["shopCode"]
    
    print(f"门店: {account['shopName']} ({shop_code})")
    
    # 3. 启动浏览器
    print("启动大风车浏览器...")
    pw, ctx = dfc_browser_writer.launch_dfc_browser(dfc_browser_dir, headless=False)
    
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        
        # 4. 拦截网络请求
        print("\n📡 开始拦截网络请求...")
        requests_log = []
        
        def handle_request(request):
            url = request.url
            if "customerObjectAction" in url or "add.json" in url:
                info = {
                    "url": url,
                    "method": request.method,
                    "headers": dict(request.headers),
                    "post_data": request.post_data,
                }
                requests_log.append(info)
                print(f"  🔍 捕获请求: {url}")
                if request.post_data:
                    print(f"     POST Data: {request.post_data[:200]}...")
        
        page.on("request", handle_request)
        
        # 5. 打开新增客户页面
        print("\n🌐 打开新增客户页面...")
        page.goto("https://xindafengche.souche.com/#/app/crm/edit?objCode=customer&businessTypeCode=customer_default_type&isSellCarCustomer=false")
        
        # 等待页面加载
        print("等待页面加载...")
        time.sleep(5)
        
        # 6. 分析捕获的请求
        print(f"\n📊 共捕获 {len(requests_log)} 个相关请求")
        for i, req in enumerate(requests_log):
            print(f"\n--- 请求 {i+1} ---")
            print(f"URL: {req['url']}")
            print(f"Method: {req['method']}")
            if req['post_data']:
                print(f"POST Data: {req['post_data'][:300]}...")
        
        # 7. 保存完整日志
        log_file = Path(__file__).parent.parent / "debug" / "api_requests.json"
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(requests_log, f, ensure_ascii=False, indent=2)
        print(f"\n💾 完整日志已保存到: {log_file}")
        
        # 8. 尝试手动触发一个请求（通过页面 JS）
        print("\n🔧 尝试通过页面 JS 调用 API...")
        
        # 获取 cookies
        cookies = ctx.cookies(["https://xindafengche.souche.com", "https://super-mario.souche.com"])
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies if ".souche.com" in c.get("domain", "")])
        
        # 构建测试 payload
        test_payload = {
            "objCode": "customer",
            "businessTypeCode": "customer_default_type",
            "fields": [
                {"code": "customer_field_shop_code", "value": shop_code},
                {"code": "customer_field_phone", "value": "13800138099"},
                {"code": "customer_field_name", "value": "【JS测试】"},
                {"code": "customer_field_source", "value": "other"},
                {"code": "customer_field_gender", "value": "unknown"},
                {"code": "customer_field_grade", "value": "C"},
                {"code": "customer_field_is_important", "value": "false"},
            ]
        }
        
        # 在页面中执行 fetch
        js_code = f"""
        async () => {{
            const response = await fetch('https://super-mario.souche.com/crm/customerObjectAction/add.json', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                }},
                credentials: 'include',
                body: JSON.stringify({json.dumps(test_payload)})
            }});
            return await response.json();
        }}
        """
        
        print("执行 JS fetch 请求...")
        result = page.evaluate(js_code)
        print(f"结果: {json.dumps(result, ensure_ascii=False)[:300]}")
        
    finally:
        print("\n按 Ctrl+C 关闭浏览器...")
        try:
            time.sleep(30)  # 给用户时间查看
        except KeyboardInterrupt:
            pass
        ctx.close()
        pw.stop()


if __name__ == "__main__":
    main()
