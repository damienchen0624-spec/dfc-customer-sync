#!/usr/bin/env python3
"""巨懂车客户列表抓取 + 解析。

纯函数：filter_new_leads / filter_lead_types / normalize_phone（可单测）
集成函数：fetch_new_leads（Playwright，依赖实际页面）
"""

import re
import time
from pathlib import Path
from typing import Dict, List, Optional


def normalize_phone(raw: str) -> str:
    """从文本里提取 11 位手机号。"""
    if not raw:
        return ""
    m = re.search(r"1\d{10}", raw)
    return m.group(0) if m else ""


def filter_new_leads(rows: List[Dict], since: Optional[str]) -> List[Dict]:
    """保留 leave_time >= since 的记录。"""
    if since is None:
        return list(rows)
    return [r for r in rows if r.get("leave_time", "") >= since]


def filter_lead_types(rows: List[Dict], allowed: List[str]) -> List[Dict]:
    """只保留 lead_type 在 allowed 里的记录。"""
    if not allowed:
        return list(rows)
    return [r for r in rows if r.get("lead_type") in allowed]


# ---- Playwright 集成部分 ----

def fetch_new_leads(page, list_url: str, since: Optional[str], allowed_types: List[str]) -> List[Dict]:
    """打开巨懂车客户列表，抓取并解析比 since 新的留资记录。"""
    # 导航
    current_url = page.url or ""
    if current_url == list_url or current_url.startswith(list_url + "?") or current_url.startswith(list_url + "#"):
        try:
            page.reload(wait_until="networkidle", timeout=30000)
        except Exception:
            page.reload(wait_until="domcontentloaded", timeout=30000)
    else:
        try:
            page.goto(list_url, wait_until="networkidle", timeout=60000)
        except Exception:
            page.goto(list_url, wait_until="domcontentloaded", timeout=60000)

    # 检测登录态
    if "login" in page.url:
        raise BrowserLoginExpired("巨懂车登录态过期（URL 含 login）")

    # 等待表格（增加等待时间和调试信息）
    print(f"   [DEBUG] 等待表格数据加载... (URL: {page.url})")
    
    # 先等待 Arco Design 表格容器（SPA 渲染标志）
    try:
        page.wait_for_selector(".arco-table", timeout=30000)
        print("   [DEBUG] Arco 表格容器已加载")
    except Exception as e:
        print(f"   [DEBUG] 等待 Arco 表格容器超时: {e}")
        # 使用跨平台的调试路径
        import platform_utils
        debug_path = str(platform_utils.get_app_data_dir() / "dfc-customer-sync" / "debug_daemon.html")
        Path(debug_path).parent.mkdir(parents=True, exist_ok=True)
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"   [DEBUG] 页面已保存到: {debug_path}")

    # ★ 关键：等待加载中的 spinner 消失（数据加载完成标志）
    try:
        page.wait_for_selector(".arco-spin-loading-layer", state="hidden", timeout=30000)
        print("   [DEBUG] 数据加载完成（spinner 已消失）")
    except Exception as e:
        print(f"   [DEBUG] 等待 spinner 消失超时: {e}")

    # 额外等待确保 DOM 更新
    page.wait_for_timeout(2000)

    # 检查是否有数据行（排除空行）
    rows_check = page.query_selector_all("table tbody tr:not(.arco-table-empty-row)")
    print(f"   [DEBUG] 找到 {len(rows_check)} 行数据（排除空行）")
    
    if len(rows_check) == 0:
        # 检查是否是空状态
        empty_check = page.query_selector(".arco-table-empty-row")
        if empty_check:
            print("   [DEBUG] 表格显示'暂无内容'，当前视图无数据")
            # 尝试切换到"全部客户"标签
            try:
                all_customers_tab = page.query_selector("text=全部客户")
                if all_customers_tab:
                    all_customers_tab.click()
                    page.wait_for_timeout(3000)
                    # 再次等待 spinner 消失
                    try:
                        page.wait_for_selector(".arco-spin-loading-layer", state="hidden", timeout=15000)
                    except Exception:
                        pass
                    page.wait_for_timeout(2000)
                    rows_check = page.query_selector_all("table tbody tr:not(.arco-table-empty-row)")
                    print(f"   [DEBUG] 切换到'全部客户'后找到 {len(rows_check)} 行数据")
            except Exception as e:
                print(f"   [DEBUG] 切换标签失败: {e}")
    has_phone = False
    for r in rows_check[:5]:
        text = r.inner_text() or ""
        if re.search(r"1\d{10}", text) or re.search(r"1\d{2}\*{6}\d{2}", text):
            has_phone = True
            break

    if not has_phone:
        login_indicators = page.query_selector_all(
            "input[type='password'], button:has-text('登录'), "
            ".account-center-login, [class*='login']"
        )
        if len(login_indicators) > 0:
            raise BrowserLoginExpired("页面出现登录元素，登录态已过期")

    # ★ 关键步骤：点击所有 EyeInvisible 图标，解密手机号
    _reveal_all_phones(page)

    # 抓取并解析每一行（排除空行）
    row_elements = page.query_selector_all("table tbody tr:not(.arco-table-empty-row)")
    rows = []
    for el in row_elements:
        row = _parse_row(el)
        if row.get("phone"):
            rows.append(row)

    rows = filter_new_leads(rows, since)
    rows = filter_lead_types(rows, allowed_types)
    return rows


def _reveal_all_phones(page):
    """点击所有 EyeInvisible 图标，让手机号从脱敏变为完整。"""
    try:
        eye_icons = page.query_selector_all("svg.icon_-icon-EyeInvisible")
        if not eye_icons:
            return
        for icon in eye_icons:
            try:
                icon.click()
                time.sleep(0.3)  # 短暂等待 DOM 更新
            except Exception:
                pass
    except Exception:
        pass


def _parse_row(el) -> Dict:
    """从一行 DOM 提取客户字段。基于实际 DOM 结构解析。"""
    text = el.inner_text() or ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # 按列索引提取当前跟进人（列20）
    follower = ""
    try:
        cells = el.query_selector_all("td")
        if len(cells) > 20:
            follower = cells[20].inner_text().strip()
    except Exception:
        pass

    # 提取客户ID
    customer_id = ""
    for line in lines:
        if re.match(r"^\d+$", line):
            customer_id = line
            break

    # 提取手机号（在"手机："后面的行）
    phone = ""
    for i, line in enumerate(lines):
        if "手机" in line and "：" in line:
            # 手机号可能在同一行或下一行
            rest = line.split("：", 1)[-1].strip()
            if rest:
                phone = normalize_phone(rest)
            elif i + 1 < len(lines):
                phone = normalize_phone(lines[i + 1])
            break

    # 提取客户名称（客户ID后、手机号前的非空非"-"行）
    name = ""
    if customer_id:
        found_id = False
        for line in lines:
            if line == customer_id:
                found_id = True
                continue
            if found_id:
                if line != "-" and "手机" not in line:
                    name = line
                    break
                if "手机" in line:
                    break

    # 提取留资时间（最新留资时间，格式 2026-06-29 14:01）
    leave_time = ""
    time_pattern = re.compile(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}")
    for line in lines:
        m = time_pattern.search(line)
        if m:
            leave_time = m.group(0)
            break

    # 提取来源（线索类型）
    source = ""
    source_keywords = ["懂车帝", "微信", "表单", "话单", "店铺车源", "私信"]
    for line in lines:
        for kw in source_keywords:
            if kw in line:
                source = line.strip()
                break
        if source:
            break

    # 提取意向车型
    intent_model = ""
    for line in lines:
        # 车型通常包含年份和排量，如 "哈弗神兽 2021 1.5T 智享版"
        if re.search(r"\d{4}.*[TtLl]", line) or re.search(r"\d{4}款", line):
            # 排除上牌时间行
            if "上牌" not in line and "公里" not in line and "万" not in line.split()[-1]:
                intent_model = line.strip()
                break

    # 提取线索类型
    lead_type = ""
    lead_keywords = ["表单线索", "话单线索", "私信线索", "系统自建", "客户留资"]
    for line in lines:
        for kw in lead_keywords:
            if kw in line:
                lead_type = kw
                break
        if lead_type:
            break

    # 提取客户状态
    status = ""
    status_keywords = ["未联系", "已联系", "跟进中", "已成交", "待跟进"]
    for line in lines:
        for kw in status_keywords:
            if kw in line:
                status = kw
                break
        if status:
            break

    return {
        "phone": phone,
        "name": name or customer_id,
        "leave_time": leave_time,
        "source": source,
        "grade": "",
        "status": status,
        "intent_model": intent_model,
        "lead_type": lead_type,
        "customer_id": customer_id,
        "follower": follower,  # 当前跟进人（按列索引20提取）
    }


class BrowserLoginExpired(Exception):
    pass
