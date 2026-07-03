#!/usr/bin/env python3
"""用 requests 库测试 API。"""

import json
import requests
from pathlib import Path

# 读取保存的 cookies
cookies_path = Path("/Users/chan/Library/Application Support/大风车 AI 龙虾/dfc-browser/dfc_cookies.json")
with open(cookies_path, 'r', encoding='utf-8') as f:
    cookies = json.load(f)

# 构建 cookies dict
cookies_dict = {c['name']: c['value'] for c in cookies}

# 提取 _security_token
security_token = cookies_dict.get('_security_token', '')

print(f"Security Token: {security_token[:20]}..." if security_token else "Security Token: (none)")

# 测试 payload
payload = {
    "objCode": "customer",
    "businessTypeCode": "customer_default_type",
    "fields": [
        {"code": "customer_field_shop_code", "value": "04886517"},
        {"code": "customer_field_phone", "value": "13800138888"},
        {"code": "customer_field_name", "value": "【测试客户-请删除】"},
        {"code": "customer_field_source", "value": "other"},
        {"code": "customer_field_gender", "value": "unknown"},
        {"code": "customer_field_is_important", "value": "false"},
        {"code": "customer_field_grade", "value": "C"}
    ]
}

# 测试不同的端点
endpoints = [
    ("super-mario saveCustomer.json", "https://super-mario.souche.com/crm/customerObjectAction/saveCustomer.json"),
    ("super-mario add.json", "https://super-mario.souche.com/crm/customerObjectAction/add.json"),
]

headers = {
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Origin": "https://xindafengche.souche.com",
    "Referer": "https://xindafengche.souche.com/",
    "_source_code": "WEB",
}
if security_token:
    headers["Souche-Security-Token"] = security_token

for label, url in endpoints:
    print(f"\n{'='*60}")
    print(f"测试: {label}")
    print(f"URL: {url}")
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            cookies=cookies_dict,
            verify=False,
            timeout=15
        )
        
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, ensure_ascii=False)}")
        
        if result.get("code") == "200":
            print("\n✅ 成功!")
            break
        else:
            print(f"\n❌ 失败: {result.get('msg', '未知错误')}")
    except Exception as e:
        print(f"❌ 异常: {e}")
