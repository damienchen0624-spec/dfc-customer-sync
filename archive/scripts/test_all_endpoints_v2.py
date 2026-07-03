#!/usr/bin/env python3
"""测试不同的 API 端点和域名组合。"""

import json
import ssl
import urllib.request
from pathlib import Path

# 读取保存的 cookies
cookies_path = Path("/Users/chan/Library/Application Support/大风车 AI 龙虾/dfc-browser/dfc_cookies.json")
with open(cookies_path, 'r', encoding='utf-8') as f:
    cookies = json.load(f)

# 构建 Cookie header
cookie_parts = []
for c in cookies:
    cookie_parts.append(f"{c['name']}={c['value']}")
cookie_header = "; ".join(cookie_parts)

# 提取 _security_token
security_token = ""
for c in cookies:
    if c.get("name") == "_security_token":
        security_token = c.get("value", "")
        break

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

# 测试不同的端点组合
endpoints = [
    ("super-mario add.json", "https://super-mario.souche.com/crm/customerObjectAction/add.json"),
    ("super-mario saveCustomer.json", "https://super-mario.souche.com/crm/customerObjectAction/saveCustomer.json"),
    ("danube-chord add.json", "https://danube-chord.souche.com/crm/customerObjectAction/add.json"),
    ("danube-chord saveCustomer.json", "https://danube-chord.souche.com/crm/customerObjectAction/saveCustomer.json"),
    ("crazyracing add.json", "https://crazyracing-kartrider.souche.com/crm/customerObjectAction/add.json"),
    ("crazyracing saveCustomer.json", "https://crazyracing-kartrider.souche.com/crm/customerObjectAction/saveCustomer.json"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for label, url in endpoints:
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Origin": "https://xindafengche.souche.com",
        "Referer": "https://xindafengche.souche.com/",
        "_source_code": "WEB",
        "Cookie": cookie_header,
    }
    if security_token:
        headers["Souche-Security-Token"] = security_token
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    
    print(f"\n{'='*60}")
    print(f"测试: {label}")
    print(f"URL: {url}")
    
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            code = result.get("code", "")
            msg = result.get("msg", "")
            success = result.get("success", False)
            
            if code == "200" and success:
                print(f"✅ 成功! code={code}, msg={msg}")
                print(f"   Data: {json.dumps(result.get('data', {}), ensure_ascii=False)[:200]}")
                break
            else:
                print(f"❌ 失败! code={code}, msg={msg}, success={success}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        print(f"❌ HTTP {e.code}: {e.reason}")
        print(f"   Body: {body[:200]}")
    except Exception as e:
        print(f"❌ 异常: {e}")
