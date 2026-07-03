#!/usr/bin/env python3
"""测试大风车写入功能：新增一条测试客户，然后删除。"""

import json
import sys
from pathlib import Path

# 添加 scripts 目录到 path
sys.path.insert(0, str(Path(__file__).parent))

import dfc_browser_writer
import auth


def main():
    # 1. 初始化
    config_path = Path(__file__).parent.parent / "config" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    
    dfc_browser_dir = str(Path(config["browser"]["user_data_dir"]).expanduser().parent / "dfc-browser")
    cookies_path = str(Path(dfc_browser_dir) / "dfc_cookies.json")
    
    # 2. 获取门店信息
    token = auth.get_token()
    account = auth.get_account_info(token)
    shop_code = account["shopCode"]
    owner_id = config.get("dfc", {}).get("owner_id", "")
    
    print(f"门店: {account['shopName']} ({shop_code})")
    
    # 3. 启动浏览器（headless 模式）
    print("启动大风车浏览器...")
    pw, ctx = dfc_browser_writer.launch_dfc_browser(dfc_browser_dir, headless=True)
    
    try:
        writer = dfc_browser_writer.DfcBrowserWriter(ctx, shop_code, owner_id, cookies_path=cookies_path)
        
        # 4. 创建测试客户数据
        test_lead = {
            "phone": "13800138000",  # 测试手机号
            "name": "【测试客户-请删除】",
            "leave_time": "2026-06-30 12:55",
            "source": "测试",
            "grade": "H",
            "status": "未联系",
            "intent_model": "测试车型 2024款",
            "lead_type": "表单线索",
            "customer_id": "",
        }
        
        print(f"\n📝 准备录入测试客户:")
        print(f"   姓名: {test_lead['name']}")
        print(f"   手机: {test_lead['phone']}")
        
        # 5. 新增客户
        print("\n🚀 正在录入大风车...")
        result = writer.add_customer_result(test_lead)
        
        if result["ok"]:
            print("✅ 录入成功！")
            
            # 6. 查询刚录入的客户 ID（通过手机号）
            print("\n🔍 查询刚录入的客户...")
            from dfc_client import DfcClient
            query_client = DfcClient(token=token, shop_code=shop_code, owner_id=owner_id)
            check_result = query_client.check_customer_exists(test_lead["phone"])
            
            if check_result["exists"]:
                record_id = check_result.get("record_id")
                print(f"✅ 找到客户记录 ID: {record_id}")
                
                # 7. 删除测试客户
                print("\n🗑️  正在删除测试客户...")
                del_result = writer.delete_customer(record_id, reason="测试数据清理")
                
                if del_result["ok"]:
                    print("✅ 删除成功！")
                    print("\n🎉 测试完成：写入和删除功能均正常")
                else:
                    print(f"❌ 删除失败: {del_result.get('error')}")
                    print(f"   请手动删除客户 ID: {record_id}")
            else:
                print("⚠️  未找到刚录入的客户（可能录入到了其他门店或需要等待）")
                print("   请手动检查大风车客户列表")
        else:
            print(f"❌ 录入失败: {result.get('error')}")
            
    finally:
        ctx.close()
        pw.stop()
        print("\n浏览器已关闭")


if __name__ == "__main__":
    main()
