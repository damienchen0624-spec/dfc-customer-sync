#!/usr/bin/env python3
"""获取大风车门店下的销售列表，用于配置 follower_mapping。

通过用户 API 获取门店下所有销售/员工信息。
"""

import json
import sys
from pathlib import Path

# 添加 scripts 目录到 path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import auth
import dfc_client


# 用户查询 API
USER_LIST_URL = f"{auth.API_BASE}/userApi/queryUserList.json"


def get_staff_list(token: str, max_pages: int = 10, logger=None) -> dict:
    """从用户 API 获取门店下所有销售信息。
    
    Args:
        token: 大风车 Token
        max_pages: 最多查询页数（每页50条）
        logger: 可选的日志记录器
    
    Returns:
        {recordId: {"name": "姓名", "recordId": "xxx", "recordDisplay": "姓名"}}
    """
    all_staff = {}
    
    for page in range(1, max_pages + 1):
        payload = {
            "pageNo": page,
            "pageSize": 50,
        }
        try:
            result = dfc_client._http_post(USER_LIST_URL, payload, token)
            data = result.get("data", {})
            # 兼容多种响应格式
            records = data.get("items") or data.get("records") or data.get("list") or []
            if not records:
                if logger:
                    logger.info(f"第{page}页无数据，停止查询")
                break
            
            page_new = 0
            for rec in records:
                # 兼容多种字段命名
                staff_id = rec.get("recordId") or rec.get("userId") or rec.get("id", "")
                staff_name = rec.get("name") or rec.get("realName") or rec.get("userName") or rec.get("displayName", "")
                if staff_id and staff_name:
                    if staff_id not in all_staff:
                        page_new += 1
                    all_staff[staff_id] = {
                        "name": staff_name,
                        "recordId": str(staff_id),
                        "recordDisplay": staff_name
                    }
            
            if logger:
                logger.info(f"第{page}页: {len(records)} 条记录, 新增 {page_new} 个销售, 累计 {len(all_staff)} 个")
            
            # 如果返回数量少于 pageSize，说明已到最后一页
            if len(records) < 50:
                break
        except Exception as e:
            if logger:
                logger.warning(f"第{page}页查询失败: {e}")
            break
    
    return all_staff


def main():
    print("=== 获取大风车销售列表 ===\n")
    print("（通过用户 API 获取销售信息）\n")
    
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
    print("正在从用户 API 获取销售列表...")
    staff_dict = get_staff_list(token)
    
    if not staff_dict:
        print("\n❌ 未找到销售列表")
        print("\n💡 可能的原因:")
        print("   1. 门店没有员工数据")
        print("   2. API 接口变更，请联系技术支持")
        print("\n🔧 替代方案: 手动配置 follower_mapping")
        print("   在 config.json 的 dfc 部分添加:")
        print('   "follower_mapping": {')
        print('     "巨懂车跟进人名字": {"recordId": "大风车销售ID", "recordDisplay": "销售姓名"},')
        print('     "张三": {"recordId": "xxx", "recordDisplay": "张三"}')
        print("   }")
        return
    
    # 转换为列表用于展示
    staff_list = list(staff_dict.values())
    
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
