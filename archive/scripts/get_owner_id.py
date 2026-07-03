#!/usr/bin/env python3
"""获取大风车当前用户信息（含 owner ID）。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auth


def main():
    token = auth.get_token()
    print(f"Token: {token[:20]}...")

    # 获取账户信息
    account = auth.get_account_info(token)
    print(f"\n账户信息:")
    print(f"  门店: {account.get('shopName')} ({account.get('shopCode')})")
    print(f"  orgId: {account.get('orgId')}")

    # 尝试获取当前用户信息
    headers = auth.build_headers(token)

    # 试几个可能的用户信息 API
    urls = [
        "https://danube-tenant-web.souche.com/account/info.json",
        "https://danube-tenant-web.souche.com/user/info.json",
        "https://danube-tenant-web.souche.com/curr_user/info.json",
        "https://crazyracing-kartrider.souche.com/crm/user/info.json",
    ]

    import urllib.request
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                print(f"\n✅ {url.split('/')[-1]}")
                print(f"   {json.dumps(data, ensure_ascii=False)[:500]}")
                
                # 查找可能的 userId/ownerId 字段
                if data.get("data"):
                    d = data["data"]
                    for key in ["userId", "ownerId", "id", "accountId", "staffId"]:
                        if key in d:
                            print(f"   >>> {key}: {d[key]}")
        except Exception as e:
            print(f"\n❌ {url.split('/')[-1]}: {e}")

    # 也试试从客户列表 API 获取 owner 信息
    print("\n=== 从客户列表获取 owner 信息 ===")
    query_url = "https://danube-chord.souche.com/generic/genericObjectAction/queryFindViewRecordPageInfo.json"
    payload = {"objCode": "customer", "pageNo": 1, "pageSize": 1, "keywords": ""}
    data = auth.api_post("/generic/genericObjectAction/queryFindViewRecordPageInfo.json", payload, token, silent=True)
    records = (data.get("common") or {}).get("records", [])
    if records:
        rec = records[0]
        fields = rec.get("fields", [])
        for f in fields:
            if "owner" in f.get("code", "").lower():
                print(f"  {f.get('code')}: {f.get('value')} (display: {f.get('displayValue', '')})")


if __name__ == "__main__":
    main()
