#!/usr/bin/env python3
"""获取大风车门店下的销售列表，用于配置 follower_mapping。"""

import json
import sys
from pathlib import Path

# 添加 scripts 目录到 path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import auth


def get_staff_list(token: str) -> list:
    """获取门店下的所有销售/员工。"""
    # 尝试获取员工列表
    urls = [
        # 通用对象查询（objCode=staff）
        ("https://danube-chord.souche.com/generic/genericObjectAction/queryFindViewRecordPageInfo.json", 
         {"objCode": "staff", "pageNo": 1, "pageSize": 100, "keywords": ""}),
        # 用户列表
        ("https://danube-chord.souche.com/generic/genericObjectAction/queryFindViewRecordPageInfo.json",
         {"objCode": "user", "pageNo": 1, "pageSize": 100, "keywords": ""}),
        # 销售列表
        ("https://danube-chord.souche.com/generic/genericObjectAction/queryFindViewRecordPageInfo.json",
         {"objCode": "salesman", "pageNo": 1, "pageSize": 100, "keywords": ""}),
    ]
    
    for url, payload in urls:
        try:
            data = auth.api_post(url.replace("https://danube-chord.souche.com", ""), payload, token, silent=True)
            records = (data.get("common") or {}).get("records", [])
            if records:
                print(f"✅ 找到 {len(records)} 条记录 (objCode={payload.get('objCode')})")
                return records
        except Exception as e:
            pass
    
    return []


def extract_staff_info(records: list) -> list:
    """从记录中提取销售信息。"""
    staff_list = []
    for rec in records:
        fields = rec.get("fields", [])
        info = {
            "recordId": rec.get("recordId", ""),
            "name": "",
            "phone": "",
        }
        for f in fields:
            code = f.get("code", "")
            if "name" in code.lower() or code == "staff_name":
                info["name"] = f.get("displayValue", "") or f.get("value", "")
            elif "phone" in code.lower() or code == "staff_phone":
                info["phone"] = f.get("displayValue", "") or f.get("value", "")
        if info["name"]:
            staff_list.append(info)
    return staff_list


def main():
    print("=== 获取大风车销售列表 ===\n")
    
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
    print("正在获取销售列表...")
    records = get_staff_list(token)
    
    if not records:
        print("\n❌ 未找到销售列表")
        print("\n💡 可能的原因:")
        print("   1. API 接口变更，请联系技术支持")
        print("   2. 当前账号没有查看销售列表的权限")
        print("\n🔧 替代方案: 手动配置 follower_mapping")
        print("   在 config.json 的 dfc 部分添加:")
        print('   "follower_mapping": {')
        print('     "巨懂车跟进人名字": {"recordId": "大风车销售ID", "recordDisplay": "销售姓名"},')
        print('     "张三": {"recordId": "xxx", "recordDisplay": "张三"}')
        print("   }")
        return
    
    # 提取销售信息
    staff_list = extract_staff_info(records)
    
    if not staff_list:
        print("\n❌ 未能解析销售信息")
        return
    
    print(f"\n✅ 找到 {len(staff_list)} 个销售:\n")
    print(f"{'序号':<6} {'姓名':<15} {'recordId':<40}")
    print("-" * 70)
    for i, staff in enumerate(staff_list, 1):
        print(f"{i:<6} {staff['name']:<15} {staff['recordId']:<40}")
    
    # 生成 follower_mapping 配置
    print("\n=== follower_mapping 配置 ===\n")
    print("将以下内容复制到 config.json 的 dfc 部分:\n")
    
    mapping = {}
    for staff in staff_list:
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
