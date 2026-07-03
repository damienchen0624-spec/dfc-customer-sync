#!/usr/bin/env python3
"""大风车 CRM 客户写入客户端（向后兼容包装）。

v3.0 重构：写操作已统一到 dfc_client.py 的 DfcClient 类中。
本模块保留 DfcWriter 类名作为兼容包装，实际逻辑委托给 DfcClient。

新代码请直接使用 dfc_client.DfcClient。
"""

import json
from typing import Dict

# 从统一客户端导入
from dfc_client import DfcClient, DfcApiError, build_fields, SAVE_CUSTOMER_URL


class DfcWriterError(Exception):
    """大风车写入异常（保持旧接口）。"""
    def __init__(self, message: str, kind: str = "unknown"):
        super().__init__(message)
        self.kind = kind


class DfcWriter:
    """大风车 CRM 客户写入客户端（Token 认证）。

    向后兼容包装，实际逻辑委托给 DfcClient。
    新代码请直接使用 dfc_client.DfcClient。
    """

    def __init__(self, token: str, shop_code: str, shop_name: str = "",
                 owner_id: str = "", owner_name: str = ""):
        """
        Args:
            token: APP_KEY 获取的 Token
            shop_code: 门店 recordId
            shop_name: 门店显示名称
            owner_id: 销售 recordId（可选）
            owner_name: 销售显示名称（可选）
        """
        self.token = token
        self.shop_code = shop_code
        self.shop_name = shop_name
        self.owner_id = owner_id
        self.owner_name = owner_name

        # 内部使用 DfcClient
        self._client = DfcClient(
            token=token,
            shop_code=shop_code,
            shop_name=shop_name,
            owner_id=owner_id,
            owner_name=owner_name,
        )

    def add_customer(self, lead: Dict) -> Dict:
        """
        新增客户。

        Args:
            lead: 客户数据，包含 phone, name, source, grade 等

        Returns:
            {"ok": True, "customer_id": "..."} 或 {"ok": False, "error": {...}}
        """
        return self._client.add_customer(lead)

    def auto_customer(self, lead: Dict) -> Dict:
        """
        智能处理：根据手机号自动判断新建还是编辑。
        """
        return self._client.auto_customer(lead)


# ============================================================
# 兼容函数（保持旧接口）
# ============================================================
def check_dfc_login(user_data_dir: str) -> Dict:
    """检查大风车登录态 — Token 模式下始终返回 True（只要 APP_KEY 有效）。"""
    try:
        import auth
        token = auth.get_token()
        if token:
            return {"logged_in": True, "source": "app_key_token"}
    except Exception as e:
        return {"logged_in": False, "reason": str(e)}
    return {"logged_in": False, "reason": "APP_KEY 无效"}


# 保持旧名称兼容
DfcBrowserWriter = DfcWriter


if __name__ == "__main__":
    # 测试
    import auth
    token = auth.get_token()
    account = auth.get_account_info(token)

    writer = DfcWriter(
        token=token,
        shop_code=account["shopCode"],
        shop_name=account["shopName"],
    )

    result = writer.add_customer({
        "phone": "13800138099",
        "name": "【测试-请删除】",
        "source": "其他",
        "grade": "C",
    })

    print(json.dumps(result, ensure_ascii=False, indent=2))
