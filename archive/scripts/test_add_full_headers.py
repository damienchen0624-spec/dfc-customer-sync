#!/usr/bin/env python3
"""用完整 headers 测试新增 API。"""

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

    # 使用 auth.build_headers 获取完整 headers
    headers = auth.build_headers(token)
    # 确保 Host 正确
    from urllib.parse import urlparse
    headers["Host"] = urlparse(url).hostname

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
                print(f"     data: {json.dumps(result.get('data', {}), ensure_ascii=False)[:500]}")
            else:
                print(f"     完整: {json.dumps(result, ensure_ascii=False)[:500]}")
            return ok, result
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ❌ {label}: HTTP {e.code} {e.reason}")
        print(f"     Body: {body[:300]}")
        return False, {}
    except Exception as e:
        print(f"  ❌ {label}: {e}")
        return False, {}


token = auth.get_token()
account = auth.get_account_info(token)
shop_code = account.get("shopCode", "")
print(f"门店: {account.get('shopName')} ({shop_code})")
print(f"Servicechain: {auth.get_servicechain()}")

payload = {
    "objCode": "customer",
    "businessTypeCode": "customer_default_type",
    "fields": [
        {"code": "customer_field_shop_code", "value": shop_code},
        {"code": "customer_field_phone", "value": "13800138088"},
        {"code": "customer_field_name", "value": "测试-Headers"},
        {"code": "customer_field_source", "value": "other"},
        {"code": "customer_field_gender", "value": "unknown"},
        {"code": "customer_field_grade", "value": "C"},
        {"code": "customer_field_is_important", "value": "false"},
    ]
}

# 测试 danube-chord 带完整 headers
print("\n=== danube-chord + 完整 headers ===")
try_add(
    "https://danube-chord.souche.com/generic/genericObjectAction/add.json",
    payload, token, "danube-chord add"
)

# 测试 super-mario 带完整 headers
print("\n=== super-mario + 完整 headers ===")
try_add(
    "https://super-mario.souche.com/crm/customerObjectAction/add.json",
    payload, token, "super-mario add"
)

# 也许需要用 form-urlencoded?
print("\n=== 尝试 form-urlencoded 格式 ===")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = auth.build_headers(token)
headers["Host"] = "danube-chord.souche.com"
headers["Content-Type"] = "application/x-www-form-urlencoded"

form_data = f"data={json.dumps(payload)}"
req = urllib.request.Request(
    "https://danube-chord.souche.com/generic/genericObjectAction/add.json",
    data=form_data.encode("utf-8"),
    headers=headers,
    method="POST"
)
try:
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        print(f"  code={result.get('code')}, msg={result.get('msg')}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    print(f"  HTTP {e.code}: {body[:300]}")
except Exception as e:
    print(f"  Error: {e}")
