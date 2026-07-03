#!/usr/bin/env python3
"""测试不同域名和参数组合的新增客户 API。"""

import json
import ssl
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auth


def try_add(url, payload, token, label=""):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Linux; Android 12; ALN-AL00) AppleWebKit/537.36",
        "Origin": "https://xindafengche.souche.com",
        "Referer": "https://xindafengche.souche.com/",
        "_source_code": "WEB",
        "Souche-Security-Token": token,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            ok = result.get("code") == "200"
            msg = result.get("msg", "")
            print(f"  {'✅' if ok else '❌'} {label}: code={result.get('code')}, msg={msg}")
            if not ok:
                print(f"     完整响应: {json.dumps(result, ensure_ascii=False)[:300]}")
            return ok, result
    except Exception as e:
        print(f"  ❌ {label}: {e}")
        return False, {}


import urllib.request

token = auth.get_token()
account = auth.get_account_info(token)
shop_code = account.get("shopCode", "")
print(f"门店: {account.get('shopName')} ({shop_code})")

# 基础 payload（不含 owner）
payload_basic = {
    "objCode": "customer",
    "businessTypeCode": "customer_default_type",
    "fields": [
        {"code": "customer_field_shop_code", "value": shop_code},
        {"code": "customer_field_phone", "value": "13800138000"},
        {"code": "customer_field_name", "value": "测试客户-域名测试"},
        {"code": "customer_field_source", "value": "other"},
        {"code": "customer_field_gender", "value": "unknown"},
        {"code": "customer_field_grade", "value": "C"},
        {"code": "customer_field_is_important", "value": "false"},
    ]
}

# 带 owner 的 payload
payload_with_owner = {
    "objCode": "customer",
    "businessTypeCode": "customer_default_type",
    "fields": [
        {"code": "customer_field_shop_code", "value": shop_code},
        {"code": "customer_field_owner", "value": "ACCNBAPUuCPIrXy0"},  # 示例 owner ID
        {"code": "customer_field_phone", "value": "13800138001"},
        {"code": "customer_field_name", "value": "测试客户-带owner"},
        {"code": "customer_field_source", "value": "other"},
        {"code": "customer_field_gender", "value": "unknown"},
        {"code": "customer_field_grade", "value": "C"},
        {"code": "customer_field_is_important", "value": "false"},
    ]
}

print("\n=== 测试 1: super-mario.souche.com (无 owner) ===")
try_add(
    "https://super-mario.souche.com/crm/customerObjectAction/add.json",
    payload_basic, token, "super-mario"
)

print("\n=== 测试 2: crazyracing-kartrider.souche.com (无 owner) ===")
try_add(
    "https://crazyracing-kartrider.souche.com/crm/customerObjectAction/add.json",
    payload_basic, token, "crazyracing"
)

print("\n=== 测试 3: super-mario (带 owner) ===")
try_add(
    "https://super-mario.souche.com/crm/customerObjectAction/add.json",
    payload_with_owner, token, "super-mario+owner"
)

print("\n=== 测试 4: crazyracing (带 owner) ===")
try_add(
    "https://crazyracing-kartrider.souche.com/crm/customerObjectAction/add.json",
    payload_with_owner, token, "crazyracing+owner"
)

# 也试试 danube-chord
print("\n=== 测试 5: danube-chord (无 owner) ===")
try_add(
    "https://danube-chord.souche.com/crm/customerObjectAction/add.json",
    payload_basic, token, "danube-chord"
)

print("\n=== 测试 6: danube-chord (带 owner) ===")
try_add(
    "https://danube-chord.souche.com/crm/customerObjectAction/add.json",
    payload_with_owner, token, "danube-chord+owner"
)
