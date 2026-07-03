#!/usr/bin/env python3
"""用 Playwright 启动一个新的 Chrome 实例。"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    # 1. 初始化
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    
    # 2. 获取门店信息
    import auth
    token = auth.get_token()
    account = auth.get_account_info(token)
    shop_code = account["shopCode"]
    
    print(f"门店: {account['shopName']} ({shop_code})")
    
    # 3. 启动 Playwright
    from playwright.sync_api import sync_playwright
    
    print("\n启动 Playwright...")
    pw = sync_playwright().start()
    
    try:
        # 启动一个新的浏览器实例
        print("启动浏览器...")
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()
        
        # 4. 访问大风车页面
        print("\n访问大风车页面...")
        page.goto("https://xindafengche.souche.com/#/app/crm/list?objCode=customer")
        time.sleep(3)
        
        # 检查是否需要登录
        current_url = page.url
        print(f"当前页面: {current_url}")
        
        if "/login" in current_url:
            print("\n⚠️ 需要登录！请在浏览器中完成登录...")
            # 等待用户登录
            for i in range(60):  # 最多等待 3 分钟
                time.sleep(3)
                current_url = page.url
                if "/login" not in current_url:
                    print(f"✅ 登录成功！")
                    break
                if i % 10 == 0:
                    print(f"   等待登录中... ({i*3}秒)")
            else:
                print("❌ 等待超时")
                return
        
        # 5. 等待页面加载完成
        print("\n等待页面加载...")
        time.sleep(3)
        
        # 6. 通过浏览器 JavaScript 发送 API 请求
        print("\n通过浏览器发送 API 请求...")
        
        test_payload = {
            "objCode": "customer",
            "businessTypeCode": "customer_default_type",
            "fields": [
                {"code": "customer_field_shop_code", "value": shop_code},
                {"code": "customer_field_phone", "value": "13800138888"},
                {"code": "customer_field_name", "value": "【浏览器测试-请删除】"},
                {"code": "customer_field_source", "value": "other"},
                {"code": "customer_field_gender", "value": "unknown"},
                {"code": "customer_field_is_important", "value": "false"},
                {"code": "customer_field_grade", "value": "C"}
            ]
        }
        
        js_code = """
        async (payload) => {
            try {
                const response = await fetch('https://super-mario.souche.com/crm/customerObjectAction/saveCustomer.json', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json;charset=UTF-8',
                        'Accept': 'application/json, text/plain, */*',
                        '_source_code': 'WEB'
                    },
                    credentials: 'include',
                    body: JSON.stringify(payload)
                });
                
                const text = await response.text();
                try {
                    return {
                        status: response.status,
                        statusText: response.statusText,
                        data: JSON.parse(text)
                    };
                } catch {
                    return {
                        status: response.status,
                        statusText: response.statusText,
                        data: text
                    };
                }
            } catch (error) {
                return {
                    error: error.message
                };
            }
        }
        """
        
        result = page.evaluate(js_code, test_payload)
        
        print(f"\n📊 响应结果:")
        print(f"Status: {result.get('status')}")
        print(f"Status Text: {result.get('statusText')}")
        print(f"Data: {json.dumps(result.get('data'), ensure_ascii=False, indent=2)}")
        
        # 7. 如果成功，查询并删除测试客户
        if result.get('status') == 200 and result.get('data', {}).get('code') == '200':
            print("\n✅ 录入成功！")
            
            # 查询刚录入的客户
            print("\n🔍 查询刚录入的客户...")
            from dfc_client import DfcClient
            query_client = DfcClient(token=token, shop_code=shop_code)
            check_result = query_client.check_customer_exists("13800138888")
            
            if check_result["exists"]:
                record_id = check_result.get("record_id")
                print(f"✅ 找到客户记录 ID: {record_id}")
                
                # 删除测试客户
                print("\n🗑️  正在删除测试客户...")
                delete_payload = {
                    "objCode": "customer",
                    "id": record_id,
                    "reason": "测试数据清理"
                }
                
                delete_js = """
                async (payload) => {
                    try {
                        const response = await fetch('https://super-mario.souche.com/crm/customerObjectAction/deleteCustomer.json', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json;charset=UTF-8',
                                'Accept': 'application/json, text/plain, */*',
                                '_source_code': 'WEB'
                            },
                            credentials: 'include',
                            body: JSON.stringify(payload)
                        });
                        return {
                            status: response.status,
                            data: await response.json()
                        };
                    } catch (error) {
                        return { error: error.message };
                    }
                }
                """
                
                delete_result = page.evaluate(delete_js, delete_payload)
                print(f"删除结果: {json.dumps(delete_result, ensure_ascii=False, indent=2)}")
                
                if delete_result.get('status') == 200:
                    print("\n🎉 测试完成：写入和删除功能均正常")
                else:
                    print(f"\n⚠️  删除失败，请手动删除客户 ID: {record_id}")
            else:
                print("⚠️  未找到刚录入的客户（可能需要等待）")
        else:
            print(f"\n❌ 录入失败")
            
    finally:
        print("\n关闭浏览器...")
        time.sleep(2)
        browser.close()
        pw.stop()
        print("完成")


if __name__ == "__main__":
    main()
