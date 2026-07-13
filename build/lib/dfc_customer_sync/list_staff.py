#!/usr/bin/env python3
"""获取大风车门店下的销售列表，用于配置 follower_mapping。

通过订单 API 提取所有销售信息（因为直接查询 scdo_user 返回 500）。
"""

import json
import sys
from pathlib import Path

# 添加 scripts 目录到 path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import auth
import dfc_client


# 订单查询 API（rich-man 网关）
ORDER_URL = "https://rich-man.souche.com/orderOperationApi/queryRecordPageInfo.json"


def get_staff_list(token: str, max_pages: int = 10, logger=None) -> dict:
    """从订单数据中提取所有销售信息。
    
    Args:
        token: 大风车 Token
        max_pages: 最多查询页数（每页50条）
        logger: 可选的日志记录器
    
    Returns:
        {recordId: {"name": "姓名", "recordId": "xxx", "recordDisplay": "姓名"}}
    """
    all_owners = {}
    
    for page in range(1, max_pages + 1):
        payload = {
            "pageNo": page,
            "pageSize": 50,
            "viewCode": "order_view_list",
            "objCode": "order",
            "filters": []
        }
        try:
            result = dfc_client._http_post(ORDER_URL, payload, token)
            records = result.get("data", {}).get("common", {}).get("records", [])
            if not records:
                if logger:
                    logger.info(f"第{page}页无数据，停止查询")
                break
            
            page_owners = 0
            for rec in records:
                fields = rec.get("fields", [])
                for f in fields:
                    if f.get("code") == "order_field_owner":
                        owner_id = f.get("recordId", "")
                        owner_name = f.get("displayValue", "")
                        if owner_id and owner_name:
                            if owner_id not in all_owners:
                                page_owners += 1
                            all_owners[owner_id] = {
                                "name": owner_name,
                                "recordId": owner_id,
                                "recordDisplay": owner_name
                            }
            
            if logger:
                logger.info(f"第{page}页: {len(records)} 条订单, 新增 {page_owners} 个销售, 累计 {len(all_owners)} 个")
        except Exception as e:
            if logger:
                logger.warning(f"第{page}页查询失败: {e}")
            break
    
    return all_owners


def extract_staff_info(staff_dict: dict) -> list:
    """将字典转换为列表格式（兼容旧接口）。"""
    return list(staff_dict.values())


def main():
    print("=== 获取大风车销售列表 ===\n")
    print("（通过订单 API 提取销售信息）\n")
    
    try:
        token = auth.get_token()
        print(f"✅ Token 获取成功\n")
    except Exception as e:
        print(f"❌ Token 获取失败: {e}")
        print("💡 请检查 APP_KEY 环境变量是否设置")
        return
    
    # 获取账户信息
    try:
        account = auth.get_account_info(token)
        print(f"门店: {account.get('shopName')} ({account.get('shopCode')})\n")
    except Exception as e:
        print(f"⚠️ 获取账户信息失败: {e}\n")
    
    # 获取销售列表
    print("正在从订单数据提取销售列表...")
    staff_dict = get_staff_list(token)
    
    if not staff_dict:
        print("\n❌ 未找到销售列表")
        print("\n💡 可能的原因:")
        print("   1. 门店没有订单数据")
        print("   2. API 接口变更，请联系技术支持")
        print("\n🔧 替代方案: 手动配置 follower_mapping")
        print("   在 config.json 的 dfc 部分添加:")
        print('   "follower_mapping": {')
        print('     "巨懂车跟进人名字": {"recordId": "大风车销售ID", "recordDisplay": "销售姓名"},')
        print('     "张三": {"recordId": "xxx", "recordDisplay": "张三"}')
        print("   }")
        return
    
    # 提取销售信息
    staff_list = extract_staff_info(staff_dict)
    
    print(f"\n✅ 找到 {len(staff_list)} 个销售:\n")
    print(f"{'序号':<6} {'姓名':<20} {'recordId'}")
    print("-" * 70)
    for i, staff in enumerate(sorted(staff_list, key=lambda x: x["name"]), 1):
        print(f"{i:<6} {staff['name']:<20} {staff['recordId']}")
    
    # 生成 follower_mapping 配置
    print("\n=== follower_mapping 配置 ===\n")
    print("将以下内容复制到 config.json 的 dfc 部分:\n")
    
    mapping = {}
    for staff in sorted(staff_list, key=lambda x: x["name"]):
        name = staff["name"]
        if name:
            mapping[name] = {
                "recordId": staff["recordId"],
                "recordDisplay": name
            }
    
    print(json.dumps(mapping, ensure_ascii=False, indent=2))
    
    print("\n💡 使用说明:")
    print("   1. 巨懂车的'当前跟进人'字段会作为 key 查找映射")
    print("   2. 如果找不到映射，会使用 owner_id（默认销售）")
    print("   3. 确保巨懂车跟进人名字与大风车销售名字一致")


if __name__ == "__main__":
    main()
