#!/usr/bin/env python3
"""
大风车认证模块 — APP_KEY 方式
通过大风车开放平台 API 获取 Token
"""

import json
import os
import ssl
import sys
import urllib.request
import urllib.error
from typing import Dict, Optional


# 大风车 Token API
TOKEN_URL = "https://ai-assistant-web.souche.com/openclaw/token/getByAppKey"
ACCOUNT_URL = "https://danube-tenant-web.souche.com/account/info.json"
SHOP_LIST_URL = "https://danube-tenant-web.souche.com/shops/list.json"
API_BASE = "https://crazyracing-kartrider.souche.com"

# 标准请求头
COMMON_HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Linux; Android 12; ALN-AL00) AppleWebKit/537.36",
    "Origin": "https://xindafengche.souche.com",
    "Referer": "https://xindafengche.souche.com/",
    "_source_code": "WEB",
}


def _ssl_context():
    """创建 SSL 上下文（禁用证书验证）"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def get_token(env_name: str = "APP_KEY") -> str:
    """
    通过 APP_KEY 获取 Token

    Returns:
        dfcToken 字符串

    Raises:
        Exception: APP_KEY 未设置或获取失败时抛出
    """
    app_key = os.getenv(env_name)
    if not app_key:
        raise Exception(
            f"❌ 未找到环境变量 {env_name}\n"
            f"请检查服务器是否已配置 {env_name}"
        )

    url = f"{TOKEN_URL}?appKey={app_key}"
    req = urllib.request.Request(url, headers=COMMON_HEADERS, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise Exception(f"获取 Token 失败: {e.reason}")

    if data.get("code") != "200":
        raise Exception(f"Token 获取失败: {data.get('msg', '未知错误')}")

    token = data.get("data", {}).get("dfcToken")
    if not token:
        raise Exception("Token 获取失败: 响应中无 dfcToken")

    return token


def get_account_info(dfc_token: str) -> dict:
    """
    通过 dfcToken 获取账户信息（orgId, shopCode, shopName）
    """
    headers = COMMON_HEADERS.copy()
    headers["Souche-Security-Token"] = dfc_token

    req = urllib.request.Request(ACCOUNT_URL, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise Exception(f"获取账户信息失败: {e.reason}")

    info = data.get("data", {})
    return {
        "orgId": info.get("orgId"),
        "shopCode": info.get("shopCode"),
        "shopName": info.get("shopName"),
    }


def list_shops(dfc_token: str) -> list:
    """获取门店列表"""
    headers = COMMON_HEADERS.copy()
    headers["Souche-Security-Token"] = dfc_token
    req = urllib.request.Request(SHOP_LIST_URL, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10, context=_ssl_context()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise Exception(f"获取门店列表失败: {e.reason}")
    if data.get("code") != "200":
        raise Exception(f"获取门店列表失败: {data.get('msg', '未知错误')}")
    items = (data.get("data") or {}).get("items", [])
    return [{"shopCode": s.get("code"), "shopName": s.get("name")} for s in items if s.get("code")]


def resolve_shop_scope(
    dfc_token: str,
    scope: str = "current",
    explicit_shop_codes: Optional[list] = None,
) -> tuple:
    """解析门店范围"""
    account = get_account_info(dfc_token)
    if scope == "current":
        return [account["shopCode"]], f"当前门店（{account['shopName']}）"
    if scope == "all":
        shops = list_shops(dfc_token)
        codes = [s.get("shopCode") for s in shops if s.get("shopCode")]
        if not codes:
            return [account["shopCode"]], f"当前门店（{account['shopName']}）"
        return codes, f"全部门店（共 {len(codes)} 家）"
    codes = [c for c in (explicit_shop_codes or []) if c]
    if not codes:
        codes = [account["shopCode"]]
    return codes, f"指定门店（共 {len(codes)} 家）"


def build_headers(dfc_token: str, extra: Optional[dict] = None) -> dict:
    """构建业务 API 请求头"""
    headers = COMMON_HEADERS.copy()
    headers["Souche-Security-Token"] = dfc_token
    headers["Host"] = "crazyracing-kartrider.souche.com"
    headers["X-Souche-Servicechain"] = os.getenv("SOUCHE_SERVICECHAIN", "env-1025647")
    if extra:
        headers.update(extra)
    return headers


def api_post(endpoint: str, payload: dict, dfc_token: str, extra_headers: Optional[dict] = None, silent: bool = False) -> dict:
    """
    发起 POST 请求
    """
    url = f"{API_BASE}{endpoint}"
    headers = build_headers(dfc_token, extra_headers)

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if not silent:
            print(f"HTTP 错误 {e.code}: {e.reason}", file=sys.stderr)
        raise Exception(f"API POST HTTP 错误 {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        if not silent:
            print(f"网络错误: {e.reason}", file=sys.stderr)
        raise Exception(f"API POST 网络错误: {e.reason}")

    if result.get("code") != "200":
        msg = result.get('msg', '未知错误')
        if not silent:
            print(f"API 业务错误: {msg}", file=sys.stderr)
        raise Exception(f"API POST 业务错误: {msg}")

    return result.get("data", {})


def get_servicechain() -> str:
    """获取服务链标识"""
    return os.getenv("SOUCHE_SERVICECHAIN", "env-1025647")


def get_auth_headers() -> Dict[str, str]:
    """获取认证 Headers"""
    return {
        "_source_code": "WEB",
        "content-type": "application/json;charset=UTF-8",
        "souche-security-token": get_token(),
        "x-souche-servicechain": get_servicechain(),
    }


if __name__ == "__main__":
    try:
        print("🔑 正在通过 APP_KEY 获取 Token...")
        token = get_token()
        print(f"✅ Token 获取成功: {token[:30]}...")
        print(f"   服务链: {get_servicechain()}")
    except Exception as e:
        print(f"{e}", file=sys.stderr)
        print("\n💡 提示: 在服务器上 APP_KEY 已配置，无需手动设置", file=sys.stderr)
        sys.exit(1)
