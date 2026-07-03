#!/usr/bin/env python3
"""使用 API 数据构造测试记录，验证同步到大风车的流程。"""

import json
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dfc_client import DfcClient
from mapping import build_dfc_fields
import auth


def main():
    # 使用 API 拦截到的真实数据，但用测试手机号
    # 基于真实客户数据构造
    test_lead = {
        'name': '6月29日哈弗神兽2021款',
        'phone': '13800000072',  # 测试手机号（基于脱敏 138******72 构造）
        'intent_model': '哈弗神兽2021款 1.5T 智享版',
        'city': '巴音郭楞',
        'source': '懂车帝平台',
        'grade': '',
        'status': ''
    }
    
    print("=== 测试同步一条客户数据到大风车 ===")
    print(f"客户: {test_lead['name']}")
    print(f"手机: {test_lead['phone']}")
    print(f"车型: {test_lead['intent_model']}")
    print(f"城市: {test_lead['city']}")
    print(f"来源: {test_lead['source']}")
    
    # 获取大风车认证
    print("\n=== 获取大风车认证 ===")
    token = auth.get_token()
    print(f"✅ Token: {token[:30]}...")
    
    account = auth.get_account_info(token)
    shop_code = account["shopCode"]
    print(f"✅ 门店: {account['shopName']} ({shop_code})")
    
    # 映射到大风车字段
    dfc_data = build_dfc_fields(test_lead, shop_code)
    
    print(f"\n=== 映射后的大风车数据 ===")
    print(json.dumps(dfc_data, ensure_ascii=False, indent=2))
    
    # 调用大风车 API
    print(f"\n=== 调用大风车 API ===")
    client = DfcClient(token=token, shop_code=shop_code)
    
    try:
        result = client.add_customer_result(test_lead)
        print(f"✅ 同步完成!")
        print(f"返回: {json.dumps(result, ensure_ascii=False, indent=2)}")
        
        # 检查手机号是否已存在
        print(f"\n=== 检查手机号是否已存在于大风车 ===")
        exists_result = client.phone_exists_result(test_lead['phone'])
        print(f"检查结果: {json.dumps(exists_result, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"❌ 同步失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
