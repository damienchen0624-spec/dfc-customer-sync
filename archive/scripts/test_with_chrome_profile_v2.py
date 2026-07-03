#!/usr/bin/env python3
"""用 Playwright 启动 Chrome 并使用用户 profile。"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    # 1. 初始化
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    
    # 2. 获取门店信息
    import auth
    token = auth.get_token()
    account = auth.get_account_info(token)
    shop_code = account["shopCode"]
    
    print(f"门店: {account['shopName']} ({shop_code})")
    
    # 3. 启动 Playwright
    from playwright.sync_api import sync_playwright
    
    print("\n启动 Playwright...")
    pw = sync_playwright().start()
    
    # 用户 Chrome profile 路径
    chrome_profile_path = str(Path.home() / "Library/Application Support/Google/Chrome/Default")
    
    try:
        # 使用用户 Chrome profile 启动浏览器
        print(f"使用 Chrome profile: {chrome_profile_path}")
        
        ctx = pw.chromium.launch_persistent_context(
            chrome_profile_path,
            headless=False,
            channel="chrome",  # 使用系统 Chrome
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        
        # 4. 访问大风车页面
        print("\n访问大风车页面...")
        page.goto("https://xindafengche.souche.com/#/app/crm/list?objCode=customer")
        time.sleep(3)
        
        # 检查是否需要登录
        current_url = page.url
        print(f"当前页面: {current_url}")
        
        if "/login" in current_url:
            print("\n⚠️ 需要登录！请在浏览器中完成登录...")
            # 等待用户登录
            for i in range(60):  # 最多等待 3 分钟
                time.sleep(3)
                current_url = page.url
                if "/login" not in current_url:
                    print(f"✅ 登录成功！")
                    break
                if i % 10 == 0:
                    print(f"   等待登录中... ({i*3}秒)")
            else:
                print("❌ 等待超时")
                return
        
        # 5. 等待页面加载完成
        print("\n等待页面加载...")
        time.sleep(3)
        
        # 6. 点击"新增客户"按钮
        print("点击'新增客户'按钮...")
        
        # 尝试不同的选择器
        selectors = [
            "button:has-text('新增客户')",
            "button:has-text('新增')",
            "a:has-text('新增客户')",
            ".btn:has-text('新增')",
        ]
        
        clicked = False
        for selector in selectors:
            try:
                page.click(selector, timeout=3000)
                print(f"✅ 点击成功: {selector}")
                clicked = True
                break
            except Exception as e:
                print(f"   尝试 {selector}: {str(e)[:50]}")
                continue
        
        if not clicked:
            print("❌ 未找到'新增客户'按钮")
            # 截图保存
            page.screenshot(path="/tmp/dfc_page.png")
            print("   已截图保存到 /tmp/dfc_page.png")
            return
        
        time.sleep(2)
        
        # 7. 填写客户信息
        print("\n填写客户信息...")
        
        # 填写姓名
        try:
            page.fill("input[placeholder*='姓名']", "【Playwright测试-请删除】")
            print("✅ 填写姓名")
        except Exception as e:
            print(f"❌ 填写姓名失败: {e}")
        
        # 填写手机号
        try:
            page.fill("input[placeholder*='手机']", "13800138888")
            print("✅ 填写手机号")
        except Exception as e:
            print(f"❌ 填写手机号失败: {e}")
        
        time.sleep(1)
        
        # 8. 点击保存
        print("\n点击保存...")
        try:
            page.click("button:has-text('保存')")
            print("✅ 点击保存")
        except Exception as e:
            print(f"❌ 点击保存失败: {e}")
        
        time.sleep(3)
        
        # 9. 检查结果
        print("\n检查结果...")
        
        # 检查是否有成功提示
        try:
            page.wait_for_selector("text=成功", timeout=5000)
            print("✅ 录入成功！")
        except Exception as e:
            print(f"⚠️ 未检测到成功提示: {e}")
            # 截图保存
            page.screenshot(path="/tmp/dfc_result.png")
            print("   已截图保存到 /tmp/dfc_result.png")
        
        # 10. 查询并删除测试客户
        print("\n🔍 查询刚录入的客户...")
        from dfc_client import DfcClient
        query_client = DfcClient(token=token, shop_code=shop_code)
        check_result = query_client.check_customer_exists("13800138888")
        
        if check_result["exists"]:
            record_id = check_result.get("record_id")
            print(f"✅ 找到客户记录 ID: {record_id}")
            
            # 删除测试客户
            print("\n🗑️  正在删除测试客户...")
            
            # 通过 API 删除
            delete_payload = {
                "objCode": "customer",
                "id": record_id,
                "reason": "测试数据清理"
            }
            
            delete_js = """
            async (payload) => {
                try {
                    const response = await fetch('https://super-mario.souche.com/crm/customerObjectAction/deleteCustomer.json', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json;charset=UTF-8',
                            'Accept': 'application/json, text/plain, */*',
                            '_source_code': 'WEB'
                        },
                        credentials: 'include',
                        body: JSON.stringify(payload)
                    });
                    return {
                        status: response.status,
                        data: await response.json()
                    };
                } catch (error) {
                    return { error: error.message };
                }
            }
            """
            
            delete_result = page.evaluate(delete_js, delete_payload)
            print(f"删除结果: {json.dumps(delete_result, ensure_ascii=False, indent=2)}")
            
            if delete_result.get('status') == 200:
                print("\n🎉 测试完成：写入和删除功能均正常")
            else:
                print(f"\n⚠️  删除失败，请手动删除客户 ID: {record_id}")
        else:
            print("⚠️  未找到刚录入的客户（可能需要等待）")
            
    finally:
        print("\n关闭浏览器...")
        time.sleep(2)
        ctx.close()
        pw.stop()
        print("完成")


if __name__ == "__main__":
    main()
