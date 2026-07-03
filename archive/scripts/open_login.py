#!/usr/bin/env python3
"""打开大风车登录页面，等待用户登录后保存 cookies。"""

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
    sys.stdout.flush()
    
    # 2. 启动浏览器
    print("启动大风车浏览器...")
    sys.stdout.flush()
    pw, ctx = dfc_browser_writer.launch_dfc_browser(dfc_browser_dir, headless=False)
    
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        
        # 隐藏 webdriver 标志
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        
        # 3. 打开登录页面
        print("打开大风车登录页面...")
        sys.stdout.flush()
        page.goto("https://xindafengche.souche.com/#/login?action=accountLogin")
        
        print("\n" + "=" * 60)
        print("📱 请在浏览器中登录大风车")
        print("=" * 60)
        print("\n登录完成后，脚本会自动检测并保存 cookies")
        print("（最长等待 5 分钟）\n")
        sys.stdout.flush()
        
        # 4. 等待登录完成
        max_wait = 300  # 5 分钟
        start_time = time.time()
        last_check = 0
        
        while time.time() - start_time < max_wait:
            time.sleep(2)
            elapsed = int(time.time() - start_time)
            
            # 每 30 秒打印一次状态
            if elapsed - last_check >= 30:
                print(f"   等待登录中... ({elapsed}秒)")
                sys.stdout.flush()
                last_check = elapsed
            
            # 检查 URL 是否已离开登录页
            current_url = page.url
            if "/login" not in current_url:
                print(f"\n✅ 检测到已离开登录页: {current_url}")
                sys.stdout.flush()
                
                # 等待页面完全加载
                time.sleep(3)
                
                # 获取 cookies
                print("\n提取 cookies...")
                sys.stdout.flush()
                cookies = ctx.cookies()
                print(f"获取到 {len(cookies)} 个 cookies")
                sys.stdout.flush()
                
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
                    print(f"   Cookies 已保存到: {cookies_path}")
                    sys.stdout.flush()
                    
                    # 5. 测试 API
                    print("\n测试 API 连通性...")
                    sys.stdout.flush()
                    
                    import auth
                    token = auth.get_token()
                    account = auth.get_account_info(token)
                    shop_code = account["shopCode"]
                    
                    test_payload = {
                        "objCode": "customer",
                        "businessTypeCode": "customer_default_type",
                        "fields": [
                            {"code": "customer_field_shop_code", "value": shop_code},
                            {"code": "customer_field_phone", "value": "13800138888"},
                            {"code": "customer_field_name", "value": "【测试客户-请删除】"},
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
                    sys.stdout.flush()
                    
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
                            
                            if del_result.get("code") == "200":
                                print("\n✅ 测试完成：写入和删除功能均正常")
                            else:
                                print(f"\n⚠️ 删除失败，请手动删除客户 ID: {record_id}")
                    else:
                        print(f"\n❌ API 测试失败: {result.get('msg', '未知错误')}")
                    
                    sys.stdout.flush()
                    return
                else:
                    print("\n⚠️ 未检测到 _security_token")
                    print("   请确认已完全登录到大风车后台")
                    sys.stdout.flush()
                    # 继续等待
                    start_time = time.time()  # 重置计时
        
        print("\n❌ 等待超时（5分钟），请重新运行脚本")
        sys.stdout.flush()
        
    finally:
        print("\n关闭浏览器...")
        sys.stdout.flush()
        time.sleep(1)
        ctx.close()
        pw.stop()
        print("完成")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
