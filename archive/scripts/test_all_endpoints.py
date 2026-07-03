#!/usr/bin/env python3
"""测试不同的 API 端点和请求格式。"""

import json
import ssl
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import auth
import dfc_browser_writer


def test_api(url, payload, cookies, label=""):
    """测试 API 端点。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    # 构建 Cookie header
    cookie_parts = []
    for c in cookies:
        c_domain = c.get("domain", "")
        if ".souche.com" in c_domain:
            cookie_parts.append(f"{c['name']}={c['value']}")
    cookie_header = "; ".join(cookie_parts)
    
    # 提取 _security_token
    security_token = ""
    for c in cookies:
        if c.get("name") == "_security_token":
            security_token = c.get("value", "")
            break
    
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
    print(f"Security Token: {security_token[:20]}..." if security_token else "Security Token: (none)")
    
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            code = result.get("code", "")
            msg = result.get("msg", "")
            success = result.get("success", False)
            
            if code == "200" and success:
                print(f"✅ 成功! code={code}, msg={msg}")
                print(f"   Data: {json.dumps(result.get('data', {}), ensure_ascii=False)[:200]}")
                return True, result
            else:
                print(f"❌ 失败! code={code}, msg={msg}, success={success}")
                print(f"   完整响应: {json.dumps(result, ensure_ascii=False)[:300]}")
                return False, result
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        print(f"❌ HTTP {e.code}: {e.reason}")
        print(f"   Body: {body[:200]}")
        return False, {"error": str(e)}
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False, {"error": str(e)}


def main():
    # 1. 初始化
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    
    dfc_browser_dir = str(Path(config["browser"]["user_data_dir"]).expanduser().parent / "dfc-browser")
    cookies_path = Path(dfc_browser_dir) / "dfc_cookies.json"
    
    # 2. 获取门店信息
    token = auth.get_token()
    account = auth.get_account_info(token)
    shop_code = account["shopCode"]
    owner_id = config.get("dfc", {}).get("owner_id", "")
    
    print(f"门店: {account['shopName']} ({shop_code})")
    print(f"Owner ID: {owner_id}")
    
    # 3. 启动浏览器获取 cookies
    print("\n启动大风车浏览器获取 cookies...")
    pw, ctx = dfc_browser_writer.launch_dfc_browser(dfc_browser_dir, headless=False)
    
    try:
        # 先访问页面确保登录态
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        print("访问大风车页面...")
        page.goto("https://xindafengche.souche.com/#/app/crm/list?objCode=customer")
        import time
        time.sleep(3)
        
        # 获取 cookies
        cookies = ctx.cookies()
        print(f"获取到 {len(cookies)} 个 cookies")
        
        # 保存 cookies 到文件
        with open(cookies_path, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"Cookies 已保存到: {cookies_path}")
        
        # 4. 构建测试 payload
        test_payload = {
            "objCode": "customer",
            "businessTypeCode": "customer_default_type",
            "fields": [
                {"code": "customer_field_shop_code", "value": shop_code},
                {"code": "customer_field_phone", "value": "13800138001"},
                {"code": "customer_field_name", "value": "【API测试-请删除】"},
                {"code": "customer_field_source", "value": "other"},
                {"code": "customer_field_gender", "value": "unknown"},
                {"code": "customer_field_is_important", "value": "false"},
                {"code": "customer_field_grade", "value": "C"},
            ]
        }
        if owner_id:
            test_payload["fields"].append({"code": "customer_field_owner", "value": owner_id})
        
        # 5. 测试不同的端点
        endpoints = [
            ("super-mario add.json", "https://super-mario.souche.com/crm/customerObjectAction/add.json"),
            ("super-mario saveCustomer.json", "https://super-mario.souche.com/crm/customerObjectAction/saveCustomer.json"),
            ("danube-chord add.json", "https://danube-chord.souche.com/crm/customerObjectAction/add.json"),
            ("danube-chord saveCustomer.json", "https://danube-chord.souche.com/crm/customerObjectAction/saveCustomer.json"),
            ("xindafengche add.json", "https://xindafengche.souche.com/crm/customerObjectAction/add.json"),
            ("crazyracing add.json", "https://crazyracing-kartrider.souche.com/crm/customerObjectAction/add.json"),
        ]
        
        for label, url in endpoints:
            success, result = test_api(url, test_payload, cookies, label)
            if success:
                print(f"\n🎉 找到可用的端点: {url}")
                # 如果成功，尝试删除
                if result.get("data", {}).get("id"):
                    record_id = result["data"]["id"]
                    print(f"   记录 ID: {record_id}")
                break
        
    finally:
        ctx.close()
        pw.stop()
        print("\n浏览器已关闭")


if __name__ == "__main__":
    main()
