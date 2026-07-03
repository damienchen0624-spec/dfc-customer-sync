#!/usr/bin/env python3
"""通过浏览器直接发送新增客户请求。"""

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
    owner_id = config.get("dfc", {}).get("owner_id", "")
    
    print(f"门店: {account['shopName']} ({shop_code})")
    print(f"Owner ID: {owner_id}")
    
    # 3. 启动浏览器
    print("\n启动大风车浏览器...")
    pw, ctx = dfc_browser_writer.launch_dfc_browser(dfc_browser_dir, headless=False)
    
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        
        # 4. 先访问大风车页面，确保登录态有效
        print("访问大风车页面...")
        page.goto("https://xindafengche.souche.com/#/app/crm/list?objCode=customer")
        time.sleep(3)
        
        # 5. 构建测试 payload（严格按照接口文档格式）
        test_payload = {
            "objCode": "customer",
            "businessTypeCode": "customer_default_type",
            "fields": [
                {"code": "customer_field_shop_code", "value": shop_code},
                {"code": "customer_field_phone", "value": "13800138000"},
                {"code": "customer_field_name", "value": "【浏览器测试-请删除】"},
                {"code": "customer_field_source", "value": "other"},
                {"code": "customer_field_gender", "value": "unknown"},
                {"code": "customer_field_is_important", "value": "false"},
                {"code": "customer_field_grade", "value": "C"}
            ]
        }
        
        if owner_id:
            test_payload["fields"].append({"code": "customer_field_owner", "value": owner_id})
        
        print(f"\n📝 测试 Payload:")
        print(json.dumps(test_payload, ensure_ascii=False, indent=2))
        
        # 6. 通过浏览器 JavaScript 发送请求
        print("\n🚀 通过浏览器发送请求...")
        
        js_code = """
        async (payload) => {
            try {
                const response = await fetch('https://danube-chord.souche.com/crm/customerObjectAction/add.json', {
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
            query_client = DfcClient(token=token, shop_code=shop_code, owner_id=owner_id)
            check_result = query_client.check_customer_exists("13800138000")
            
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
                        const response = await fetch('https://danube-chord.souche.com/crm/customerObjectAction/deleteCustomer.json', {
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
        print("\n按 Ctrl+C 关闭浏览器...")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            pass
        ctx.close()
        pw.stop()
        print("浏览器已关闭")


if __name__ == "__main__":
    main()
