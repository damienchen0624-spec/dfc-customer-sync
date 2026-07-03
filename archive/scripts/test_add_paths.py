#!/usr/bin/env python3
"""测试不同的 API 路径。"""

import json
import ssl
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auth
import urllib.request


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
            print(f"  {'✅' if ok else '❌'} {label}")
            print(f"     code={result.get('code')}, msg={msg}")
            if ok:
                print(f"     data: {json.dumps(result.get('data', {}), ensure_ascii=False)[:300]}")
            return ok, result
    except Exception as e:
        print(f"  ❌ {label}: {e}")
        return False, {}


token = auth.get_token()
account = auth.get_account_info(token)
shop_code = account.get("shopCode", "")
print(f"门店: {account.get('shopName')} ({shop_code})")

payload = {
    "objCode": "customer",
    "businessTypeCode": "customer_default_type",
    "fields": [
        {"code": "customer_field_shop_code", "value": shop_code},
        {"code": "customer_field_phone", "value": "13800138099"},
        {"code": "customer_field_name", "value": "测试-API路径"},
        {"code": "customer_field_source", "value": "other"},
        {"code": "customer_field_gender", "value": "unknown"},
        {"code": "customer_field_grade", "value": "C"},
        {"code": "customer_field_is_important", "value": "false"},
    ]
}

# 测试 danube-chord 上的不同路径
paths = [
    "/generic/genericObjectAction/add.json",
    "/generic/genericObjectAction/save.json",
    "/generic/genericObjectAction/create.json",
    "/generic/customerObjectAction/add.json",
    "/crm/genericObjectAction/add.json",
]

print("\n=== 测试 danube-chord.souche.com 不同路径 ===")
for path in paths:
    url = f"https://danube-chord.souche.com{path}"
    try_add(url, payload, token, path)

# 也测试 super-mario 上的不同路径
print("\n=== 测试 super-mario.souche.com 不同路径 ===")
paths2 = [
    "/generic/genericObjectAction/add.json",
    "/crm/customer/add.json",
    "/api/customer/add.json",
    "/customer/add.json",
]

for path in paths2:
    url = f"https://super-mario.souche.com{path}"
    try_add(url, payload, token, path)
