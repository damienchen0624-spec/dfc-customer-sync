#!/usr/bin/env python3
"""从现有客户获取 owner ID。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auth
import dfc_client


def main():
    token = auth.get_token()
    print(f"Token: {token[:20]}...")

    account = auth.get_account_info(token)
    shop_code = account.get("shopCode", "")
    print(f"门店: {account.get('shopName')} ({shop_code})")

    dfc = dfc_client.DfcClient(token, shop_code)

    # 查询已知存在的客户
    print("\n=== 查询客户 13899086272 ===")
    
    # 直接用 dfc_client 的内部方法
    import urllib.request
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    query_url = "https://danube-chord.souche.com/generic/genericObjectAction/queryFindViewRecordPageInfo.json"
    payload = {"objCode": "customer", "pageNo": 1, "pageSize": 5, "keywords": "13899086272"}
    
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
    req = urllib.request.Request(query_url, data=data, headers=headers, method="POST")
    
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    if result.get("code") != "200":
        print(f"❌ 查询失败: {result.get('msg')}")
        return

    records = (result.get("data", {}).get("common") or {}).get("records", [])
    print(f"\n找到 {len(records)} 条记录")

    if not records:
        print("❌ 未找到客户记录")
        return

    rec = records[0]
    fields = rec.get("fields", [])
    print(f"\n=== 客户字段（共 {len(fields)} 个）===")
    
    owner_id = None
    for f in fields:
        code = f.get("code", "")
        value = f.get("value", "")
        display = f.get("displayValue", "")
        
        if "owner" in code.lower():
            print(f"  ★ {code}: {value}")
            print(f"    display: {display}")
            if value:
                owner_id = value
        elif "phone" in code.lower() or "name" in code.lower():
            print(f"  {code}: {value}")

    if owner_id:
        print(f"\n✅ Owner ID: {owner_id}")
        # 保存到配置文件
        config_path = ROOT / "config" / "config.json"
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["dfc"] = config.get("dfc", {})
            config["dfc"]["owner_id"] = owner_id
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"✅ 已保存到 config.json")
    else:
        print(f"\n⚠️ 未找到 owner 字段，输出所有有值的字段:")
        for f in fields:
            code = f.get("code", "")
            value = f.get("value", "")
            if value and len(str(value)) < 100:
                print(f"  {code}: {value}")


if __name__ == "__main__":
    main()
