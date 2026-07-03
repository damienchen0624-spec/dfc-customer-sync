#!/usr/bin/env python3
"""用完整字段元数据格式测试 saveCustomer API。"""

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

# 构建完整字段元数据
fields = [
    {
        "builtIn": True,
        "canRead": True,
        "code": "customer_field_shop_code",
        "display": True,
        "displayType": "default",
        "editable": True,
        "inputType": "default",
        "name": "门店",
        "objCode": "scdo_shop",
        "required": True,
        "targetObjCode": "scdo_shop",
        "type": "LOOKUP",
        "value": "04886517"
    },
    {
        "builtIn": True,
        "canRead": True,
        "code": "customer_field_owner",
        "display": True,
        "displayType": "default",
        "editable": True,
        "inputType": "default",
        "name": "销售",
        "required": False,
        "type": "LOOKUP",
        "value": "ACCNBA1pwdmpImq2"
    },
    {
        "builtIn": True,
        "canRead": True,
        "code": "customer_field_phone",
        "display": True,
        "displayType": "short",
        "editable": True,
        "inputType": "default",
        "matchCase": False,
        "maxLength": 11,
        "name": "手机号",
        "required": False,
        "type": "TEXT",
        "value": "13900139001"
    },
    {
        "builtIn": True,
        "canRead": True,
        "code": "customer_field_name",
        "display": True,
        "displayType": "short",
        "editable": True,
        "inputType": "default",
        "maxLength": 255,
        "name": "姓名",
        "required": False,
        "type": "TEXT",
        "value": "【测试客户-请删除】"
    },
    {
        "builtIn": True,
        "canRead": True,
        "code": "customer_field_source",
        "display": True,
        "displayType": "default",
        "editable": True,
        "inputType": "default",
        "name": "客户来源",
        "required": True,
        "type": "RADIO",
        "value": "arrive-store"
    },
    {
        "builtIn": True,
        "canRead": True,
        "code": "customer_field_gender",
        "display": True,
        "displayType": "radioButton",
        "editable": True,
        "inputType": "default",
        "name": "性别",
        "required": True,
        "type": "RADIO",
        "value": "unknown"
    },
    {
        "builtIn": True,
        "canRead": True,
        "code": "customer_field_is_important",
        "display": True,
        "displayType": "radioButton",
        "editable": True,
        "inputType": "default",
        "name": "重点客户",
        "required": True,
        "type": "RADIO",
        "value": "false"
    },
    {
        "builtIn": True,
        "canRead": True,
        "code": "customer_field_grade",
        "display": True,
        "displayType": "default",
        "editable": True,
        "inputType": "default",
        "name": "意向等级",
        "required": True,
        "type": "RADIO",
        "value": "H"
    }
]

payload = {
    "objCode": "customer",
    "businessTypeCode": "customer_default_type",
    "fields": fields
}

url = "https://super-mario.souche.com/crm/customerObjectAction/saveCustomer.json"

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

print(f"\nURL: {url}")
print(f"Payload: {json.dumps(payload, ensure_ascii=False)[:500]}...")

try:
    response = requests.post(
        url,
        json=payload,
        headers=headers,
        cookies=cookies_dict,
        verify=False,
        timeout=15
    )
    
    print(f"\nStatus: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, ensure_ascii=False)}")
    
    if result.get("code") == "200":
        print("\n✅ 成功!")
        record_id = result.get("data", {}).get("id")
        if record_id:
            print(f"   记录 ID: {record_id}")
    else:
        print(f"\n❌ 失败: {result.get('msg', '未知错误')}")
except Exception as e:
    print(f"❌ 异常: {e}")
