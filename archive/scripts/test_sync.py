#!/usr/bin/env python3
"""
测试同步功能
"""
import sys
import os
import json

# 添加 scripts 目录到 Python 路径
sys.path.insert(0, os.path.dirname(__file__))

from jvdc_scraper import JudongcheScraper
from dfc_client import DfcClient
from dfc_browser_writer import check_dfc_login
from auth import get_token, get_account_info

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_sync():
    print("=== 测试同步功能 ===\n")
    
    config = load_config()
    
    # 1. 获取 APP_KEY token
    print("1. 获取 APP_KEY token...")
    try:
        token = get_token()
        account_info = get_account_info(token)
        shop_code = account_info["shopCode"]
        shop_name = account_info["shopName"]
        owner_id = config["dfc"].get("owner_id", "")
        
        dfc_api = DfcClient(token=token, shop_code=shop_code, owner_id=owner_id)
        print(f"   门店: {shop_name} ({shop_code})")
    except Exception as e:
        print(f"   ❌ 获取 token 失败: {e}")
        return
    
    # 2. 检查大风车登录态
    print("\n2. 检查大风车登录态...")
    dfc_browser_dir = os.path.expanduser("~/Library/Application Support/大风车 AI 龙虾/dfc-browser")
    login_check = check_dfc_login(dfc_browser_dir)
    print(f"   登录状态: {login_check}")
    
    if not login_check["logged_in"]:
        print("   ❌ 大风车未登录")
        return
    
    # 3. 启动巨懂车浏览器并抓取
    print("\n3. 启动巨懂车浏览器并抓取...")
    jvdc = JudongcheScraper()
    success = jvdc.start()
    
    if not success:
        print("   ❌ 启动巨懂车浏览器失败")
        return
    
    try:
        # 抓取客户列表
        customers = jvdc.scrape_customer_list()
        print(f"   找到 {len(customers)} 个客户")
        
        if not customers:
            print("   ⚠️ 没有找到客户数据")
            return
        
        # 打印第一个客户信息
        first = customers[0]
        print(f"\n4. 第一个客户信息:")
        print(f"   姓名: {first['name']}")
        print(f"   手机: {first['phone']}")
        print(f"   品牌: {first.get('brand', 'N/A')}")
        print(f"   车系: {first.get('car_series', 'N/A')}")
        print(f"   经销商: {first.get('dealer', 'N/A')}")
        
        # 检查查重
        print(f"\n5. 检查查重...")
        check = dfc_api.phone_exists_result(first["phone"])
        print(f"   查重结果: {check}")
        
        print("\n✅ 测试完成！")
        
    finally:
        jvdc.stop()

if __name__ == "__main__":
    test_sync()
