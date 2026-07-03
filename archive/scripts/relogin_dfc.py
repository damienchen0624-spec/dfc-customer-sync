#!/usr/bin/env python3
"""重新登录大风车并保存 cookies。"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import dfc_browser_writer


def main():
    # 1. 初始化
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    
    dfc_browser_dir = str(Path(config["browser"]["user_data_dir"]).expanduser().parent / "dfc-browser")
    cookies_path = Path(dfc_browser_dir) / "dfc_cookies.json"
    
    print(f"浏览器数据目录: {dfc_browser_dir}")
    print(f"Cookies 保存路径: {cookies_path}")
    
    # 2. 启动浏览器
    print("\n启动大风车浏览器...")
    pw, ctx = dfc_browser_writer.launch_dfc_browser(dfc_browser_dir, headless=False)
    
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        
        # 隐藏 webdriver 标志
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        
        # 3. 访问大风车
        print("访问大风车...")
        try:
            page.goto("https://xindafengche.souche.com", wait_until="networkidle", timeout=30000)
        except Exception:
            page.goto("https://xindafengche.souche.com", wait_until="domcontentloaded", timeout=30000)
        
        current_url = page.url
        print(f"当前页面: {current_url}")
        
        # 4. 检查是否需要登录
        if "/login" in current_url:
            print("\n" + "=" * 60)
            print("⚠️  需要登录！请在浏览器中完成登录")
            print("=" * 60)
            print("\n等待登录完成...")
            
            # 等待用户登录（最多 5 分钟）
            max_wait = 300  # 5 分钟
            waited = 0
            check_interval = 3
            
            while waited < max_wait:
                time.sleep(check_interval)
                waited += check_interval
                
                current_url = page.url
                if "/login" not in current_url and "xindafengche.souche.com" in current_url:
                    print(f"✅ 检测到登录成功！当前页面: {current_url}")
                    break
                
                if waited % 30 == 0:
                    print(f"   已等待 {waited} 秒...")
            else:
                print("❌ 等待超时，请重新运行脚本")
                return
        else:
            print("✅ 已登录，无需重新登录")
        
        # 5. 导航到客户页面验证
        print("\n导航到客户页面验证登录态...")
        try:
            page.goto("https://xindafengche.souche.com/#/app/crm/list?objCode=customer", 
                       wait_until="networkidle", timeout=15000)
        except Exception:
            pass
        
        time.sleep(2)
        
        # 6. 提取并保存 cookies
        print("\n提取 cookies...")
        cookies = ctx.cookies()
        print(f"获取到 {len(cookies)} 个 cookies")
        
        # 检查 _security_token
        security_token = ""
        for c in cookies:
            if c.get("name") == "_security_token":
                security_token = c.get("value", "")
                break
        
        if security_token:
            # 保存 cookies
            with open(cookies_path, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ 登录成功！")
            print(f"   Security Token: {security_token[:20]}...")
            print(f"   Cookies 数量: {len(cookies)}")
            print(f"   Cookies 已保存到: {cookies_path}")
            
            # 7. 测试 API
            print("\n测试 API 连通性...")
            import auth
            token = auth.get_token()
            account = auth.get_account_info(token)
            shop_code = account["shopCode"]
            
            test_payload = {
                "objCode": "customer",
                "businessTypeCode": "customer_default_type",
                "fields": [
                    {"code": "customer_field_shop_code", "value": shop_code},
                    {"code": "customer_field_phone", "value": "13800138999"},
                    {"code": "customer_field_name", "value": "【连通性测试】"},
                    {"code": "customer_field_source", "value": "other"},
                    {"code": "customer_field_gender", "value": "unknown"},
                    {"code": "customer_field_is_important", "value": "false"},
                    {"code": "customer_field_grade", "value": "C"},
                ]
            }
            
            # 通过浏览器 JavaScript 测试 API
            js_code = """
            async (payload) => {
                try {
                    const response = await fetch('https://super-mario.souche.com/crm/customerObjectAction/add.json', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json;charset=UTF-8',
                            'Accept': 'application/json, text/plain, */*',
                            '_source_code': 'WEB'
                        },
                        credentials: 'include',
                        body: JSON.stringify(payload)
                    });
                    return await response.json();
                } catch (error) {
                    return { error: error.message };
                }
            }
            """
            
            result = page.evaluate(js_code, test_payload)
            print(f"API 响应: {json.dumps(result, ensure_ascii=False)[:300]}")
            
            if result.get("code") == "200":
                print("\n🎉 API 测试成功！可以正常写入客户数据")
                # 删除测试数据
                if result.get("data", {}).get("id"):
                    record_id = result["data"]["id"]
                    print(f"   测试记录 ID: {record_id}")
                    
                    delete_js = """
                    async (id) => {
                        try {
                            const response = await fetch('https://super-mario.souche.com/crm/customerObjectAction/deleteCustomer.json', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json;charset=UTF-8',
                                    'Accept': 'application/json, text/plain, */*',
                                    '_source_code': 'WEB'
                                },
                                credentials: 'include',
                                body: JSON.stringify({ objCode: 'customer', id: id, reason: '测试数据清理' })
                            });
                            return await response.json();
                        } catch (error) {
                            return { error: error.message };
                        }
                    }
                    """
                    del_result = page.evaluate(delete_js, record_id)
                    print(f"   删除结果: {json.dumps(del_result, ensure_ascii=False)[:200]}")
            else:
                print(f"\n❌ API 测试失败: {result.get('msg', '未知错误')}")
        else:
            print("\n⚠️ 未检测到 _security_token")
            print("   可能未完全登录，请检查浏览器页面")
            
    finally:
        print("\n关闭浏览器...")
        time.sleep(2)
        ctx.close()
        pw.stop()
        print("完成")


if __name__ == "__main__":
    main()
