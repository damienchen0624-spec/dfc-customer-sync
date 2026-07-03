#!/usr/bin/env python3
"""查看客户记录的完整结构。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auth


def main():
    token = auth.get_token()
    print(f"Token: {token[:20]}...")

    import urllib.request
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    query_url = "https://danube-chord.souche.com/generic/genericObjectAction/queryFindViewRecordPageInfo.json"
    payload = {"objCode": "customer", "pageNo": 1, "pageSize": 1, "keywords": "13899086272"}
    
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

    records = (result.get("data", {}).get("common") or {}).get("records", [])
    if not records:
        print("❌ 未找到记录")
        return

    rec = records[0]
    
    # 输出记录的顶层字段
    print("\n=== 记录顶层字段 ===")
    for key, value in rec.items():
        if key != "fields":
            print(f"  {key}: {value}")
    
    # 输出所有 fields
    print(f"\n=== 所有 fields ({len(rec.get('fields', []))} 个) ===")
    for f in rec.get("fields", []):
        code = f.get("code", "")
        value = f.get("value", "")
        display = f.get("displayValue", "")
        print(f"  {code}: value={repr(value)}, display={repr(display)}")


if __name__ == "__main__":
    main()
