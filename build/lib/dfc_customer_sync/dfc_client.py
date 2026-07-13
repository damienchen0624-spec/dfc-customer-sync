#!/usr/bin/env python3
"""大风车 CRM 客户读写客户端。

统一处理所有大风车 CRM 操作：
- 读操作（查重）：POST danube-chord queryFindViewRecordPageInfo.json
- 写操作（新增）：POST super-mario saveCustomer.json

认证方式：APP_KEY → Token（Souche-Security-Token header）
"""

import json
import ssl
import urllib.request
import urllib.error
from typing import Dict, List, Optional

import mapping


# ============================================================
# API 端点
# ============================================================
QUERY_URL = "https://danube-chord.souche.com/generic/genericObjectAction/queryFindViewRecordPageInfo.json"
SAVE_CUSTOMER_URL = "https://super-mario.souche.com/pcbotwall/crm/customerObjectAction/saveCustomer.json"

COMMON_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://xindafengche.souche.com",
    "Referer": "https://xindafengche.souche.com/",
    "_source_code": "WEB",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
}


# ============================================================
# 异常
# ============================================================
class DfcApiError(Exception):
    """大风车 API 异常。"""
    def __init__(self, message: str, kind: str = "unknown", status: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.status = status

    def to_dict(self) -> Dict:
        return {"kind": self.kind, "message": self.message, "status": self.status}


def _classify_business_error(msg: str) -> str:
    """根据错误信息分类异常类型。"""
    text = (msg or "").lower()
    if any(key in text for key in ["token", "登录", "auth", "expired", "invalid token"]):
        return "auth"
    if any(key in text for key in ["必填", "参数", "格式", "校验", "validate"]):
        return "validation"
    if any(key in text for key in ["重复", "已存在", "duplicate", "exists"]):
        return "duplicate"
    return "business"


# ============================================================
# SSL & HTTP
# ============================================================
def _ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _http_post(url: str, payload: Dict, token: str) -> Dict:
    """发 POST，返回完整响应；业务失败抛 DfcApiError。"""
    headers = COMMON_HEADERS.copy()
    headers["Souche-Security-Token"] = token
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise DfcApiError(f"HTTP {e.code}: {e.reason}", kind="auth", status=e.code)
        raise DfcApiError(f"HTTP {e.code}: {e.reason}", kind="http", status=e.code)
    except urllib.error.URLError as e:
        raise DfcApiError(f"网络错误: {e}", kind="network")
    if result.get("code") != "200":
        msg = result.get("msg", "未知错误")
        raise DfcApiError(msg, kind=_classify_business_error(msg))
    return result


# ============================================================
# 字段构造器（精简版，只保留同步流程中实际使用的字段）
# ============================================================
def _base(code, name, display_type, input_type="default", required=False, max_length=None,
          match_case=None, mounted=True, display=True):
    f = {
        "builtIn": True, "canRead": True, "code": code,
        "display": display, "displayType": display_type,
        "editable": True, "inputType": input_type,
        "name": name, "required": required, "type": "TEXT",
        "mounted": mounted, "key": code, "validate": True, "validateMsg": "",
    }
    if max_length is not None:
        f["maxLength"] = max_length
    if match_case is not None:
        f["matchCase"] = match_case
    return f


def _text_field(code, name, content, max_length=255, match_case=False, display_type="short"):
    f = _base(code, name, display_type, match_case=match_case, max_length=max_length)
    f["type"] = "TEXT"
    f["patterns"] = []
    if content is not None:
        f["content"] = content
    return f


def _radio_field(code, name, code_chosen, elements_dict, display_type="radioButton"):
    elements = [{"code": v, "name": k} for k, v in elements_dict.items()]
    f = _base(code, name, display_type)
    f["type"] = "RADIO"
    f["codeChosen"] = code_chosen
    f["elements"] = elements
    return f


def _lookup_field(code, name, record_id, record_display, obj_code, target_obj_code,
                  required=False):
    f = _base(code, name, "default", required=required)
    f["type"] = "LOOKUP"
    f["objCode"] = obj_code
    f["targetObjCode"] = target_obj_code
    f["recordId"] = record_id
    f["recordDisplay"] = record_display
    return f


def _create_type_field():
    """客户创建方式（必填），默认 PC-主动创建。"""
    elements = [
        {"code": "TfAFSLA4ES_option_value_CmAXtBu0M9", "name": "线索创建"},
        {"code": "TfAFSLA4ES_option_value_zhwlM7FhH5", "name": "APP-主动创建"},
        {"code": "TfAFSLA4ES_option_value_ZFA7I3dLUf", "name": "销售订单创建"},
        {"code": "TfAFSLA4ES_option_value_swsV7sYozR", "name": "PC-主动创建"},
        {"code": "TfAFSLA4ES_option_value_vKOkQdCzab", "name": "批量导入"},
        {"code": "TfAFSLA4ES_option_value_tsK42eGzMd", "name": "通讯录导入"},
        {"code": "TfAFSLA4ES_option_value_nksb0DdY6C", "name": "采购订单创建"},
        {"code": "tA6f2zuK8A", "name": "企微销售助手创建"},
    ]
    f = _base("customer_field_create_type", "客户创建方式", "picker")
    f["type"] = "RADIO"
    f["required"] = True
    f["codeChosen"] = "TfAFSLA4ES_option_value_swsV7sYozR"  # PC-主动创建
    f["elements"] = elements
    return f


# ============================================================
# 构建 fields 数组（精简版，只保留同步流程中实际使用的字段）
# ============================================================
def build_fields(data: dict) -> list:
    """
    输入简化数据，返回 CRM 接口需要的完整 fields 数组。

    实际使用的字段：
      phone: 手机号（必填）
      shop: {recordId, recordDisplay} 门店（必填）
      name, source(中文名), gender(中文名), grade(H/A/B/C/N),
      is_important(是/否), owner, intent, wechat
    """
    fields = []

    # 门店（必填）
    shop = data.get("shop")
    if shop:
        fields.append(_lookup_field("customer_field_shop_code", "门店",
                                    shop["recordId"], shop["recordDisplay"],
                                    "scdo_shop", "scdo_shop", required=True))

    # 销售
    owner = data.get("owner")
    if owner:
        fields.append(_lookup_field("customer_field_owner", "销售",
                                    owner["recordId"], owner["recordDisplay"],
                                    "scdo_user", "scdo_user"))

    # 手机号（必填）
    if "phone" in data:
        fields.append(_text_field("customer_field_phone", "手机号",
                                  data["phone"], max_length=11, match_case=False))

    # 姓名
    if "name" in data and data["name"]:
        fields.append(_text_field("customer_field_name", "姓名",
                                  data["name"], max_length=255, match_case=True))

    # 微信号
    if "wechat" in data and data["wechat"]:
        fields.append(_text_field("customer_field_weichat", "微信号",
                                  data["wechat"], max_length=20, match_case=False))

    # 性别
    if "gender" in data:
        gender_name = data["gender"]
        code = mapping.GENDER.get(gender_name, mapping.GENDER["未知"])
        fields.append(_radio_field("customer_field_gender", "性别", code, mapping.GENDER))

    # 客户来源
    if "source" in data:
        source_name = data["source"]
        code = mapping.SOURCE.get(source_name, mapping.SOURCE["其他"])
        fields.append(_radio_field("customer_field_source", "客户来源", code, mapping.SOURCE, "picker"))

    # 意向等级
    if "grade" in data:
        grade_name = data["grade"]
        code = mapping.GRADE.get(grade_name, mapping.GRADE["C"])
        fields.append(_radio_field("customer_field_grade", "意向等级", code, mapping.GRADE, "picker"))

    # 重点客户
    if "is_important" in data:
        important_name = data["is_important"]
        code = mapping.IMPORTANT.get(important_name, mapping.IMPORTANT["否"])
        fields.append(_radio_field("customer_field_is_important", "重点客户", code, mapping.IMPORTANT))

    # 意向描述
    if "intent" in data and data["intent"]:
        fields.append(_text_field("customer_field_intent", "意向描述",
                                  data["intent"], max_length=1000, display_type="long"))

    # 客户创建方式（必填）
    fields.append(_create_type_field())

    return fields


# ============================================================
# DfcClient 类（统一读写客户端）
# ============================================================
class DfcClient:
    """大风车 CRM 客户读写客户端（Token 认证）。"""

    def __init__(self, token: str, shop_code: str, shop_name: str = "",
                 owner_id: str = "", owner_name: str = ""):
        self.token = token
        self.shop_code = shop_code
        self.shop_name = shop_name
        self.owner_id = owner_id
        self.owner_name = owner_name

    # ---- 读操作 ----

    def phone_exists(self, phone: str) -> bool:
        """按手机号查大风车是否已有该客户。"""
        payload = {"objCode": "customer", "pageNo": 1, "pageSize": 50, "keywords": phone}
        try:
            result = _http_post(QUERY_URL, payload, self.token)
            data = result.get("data", {})
            records = (data.get("common") or {}).get("records", [])
            for rec in records:
                for f in rec.get("fields", []):
                    if f.get("code") == "customer_field_phone" and f.get("value") == phone:
                        return True
            return False
        except DfcApiError:
            raise

    def phone_exists_result(self, phone: str) -> Dict:
        """按手机号查重，返回结构化结果。"""
        try:
            exists = self.phone_exists(phone)
            return {"ok": True, "exists": exists, "error": None}
        except DfcApiError as e:
            return {"ok": False, "exists": None, "error": e.to_dict()}

    def query_customer_by_phone(self, phone: str) -> Optional[dict]:
        """按手机号查询客户，返回第一个精确匹配的 record，或 None。"""
        payload = {"objCode": "customer", "pageNo": 1, "pageSize": 20, "keywords": phone}
        try:
            result = _http_post(QUERY_URL, payload, self.token)
            data = result.get("data", {})
            records = (data.get("common") or {}).get("records", [])
            for rec in records:
                for field in rec.get("fields", []):
                    if field.get("code") == "customer_field_phone" and field.get("value") == phone:
                        return rec
            return None
        except DfcApiError:
            return None

    # ---- 写操作 ----

    def add_customer(self, lead: Dict, follower_mapping: Dict = None) -> Dict:
        """
        新增客户（从巨懂车同步的 lead 数据）。

        Args:
            lead: 客户数据，包含 phone, name, source, grade, status, intent_model, follower 等
            follower_mapping: 跟进人到销售的映射表 {"薛": {"recordId": "xxx", "recordDisplay": "薛"}}

        Returns:
            {"ok": True, "customer_id": "..."} 或 {"ok": False, "error": {...}}
        """
        # 映射字段
        source_name = mapping.map_source(lead.get("source", ""))
        grade_name = mapping.map_grade(lead.get("grade", ""), lead.get("status", ""))
        gender_name = mapping.map_gender(lead.get("gender", ""))

        # 构建意向描述
        intent = ""
        intent_model = (lead.get("intent_model") or "").strip()
        if intent_model:
            intent = f"巨懂车留资：{intent_model}"

        # 构建简化数据
        data = {
            "phone": lead.get("phone", ""),
            "name": lead.get("name", ""),
            "source": source_name,
            "grade": grade_name,
            "gender": gender_name,
            "is_important": lead.get("is_important", "否"),
            "shop": {"recordId": self.shop_code, "recordDisplay": self.shop_name},
        }

        # 处理销售/跟进人映射
        follower = (lead.get("follower") or "").strip()
        if follower and follower_mapping and follower in follower_mapping:
            owner_info = follower_mapping[follower]
            data["owner"] = {"recordId": owner_info["recordId"], "recordDisplay": owner_info.get("recordDisplay", follower)}
        elif self.owner_id:
            data["owner"] = {"recordId": self.owner_id, "recordDisplay": self.owner_name}

        if intent:
            data["intent"] = intent

        if lead.get("wechat"):
            data["wechat"] = lead["wechat"]

        # 构建 fields 并发送请求
        fields = build_fields(data)
        payload = {
            "objCode": "customer",
            "businessTypeCode": "customer_default_type",
            "fields": fields,
        }

        try:
            result = _http_post(SAVE_CUSTOMER_URL, payload, self.token)
            # _http_post 已经在 code != "200" 时抛出异常，成功返回即表示请求成功
            resp_data = result.get("data", {})
            customer_id = resp_data.get("customerId") or resp_data.get("id") or resp_data.get("recordId", "")
            return {"ok": True, "customer_id": customer_id}
        except DfcApiError as e:
            return {"ok": False, "error": e.to_dict()}


# ============================================================
# 兼容函数
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


if __name__ == "__main__":
    # 测试
    import auth
    token = auth.get_token()
    account = auth.get_account_info(token)

    client = DfcClient(
        token=token,
        shop_code=account["shopCode"],
        shop_name=account["shopName"],
    )

    # 测试查重
    result = client.phone_exists_result("13800138099")
    print(f"查重结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
