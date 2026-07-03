#!/usr/bin/env python3
"""错误处理模块 - 捕获错误并自动查阅 reference 给 agent 参考。

设计原则：
1. 捕获具体错误类型/代码
2. 自动读取 troubleshooting.md 中对应的章节
3. 输出给 agent 作为参考，不是强制解决方案
4. agent 有自主解决问题的自由
"""

import re
from pathlib import Path
from typing import Optional, Dict, List


# 错误类型到 reference 章节的映射
ERROR_PATTERNS = {
    # Profile/登录态问题
    "login_expired": {
        "keywords": ["login", "登录态", "cookie", "storage_state", "认证"],
        "reference_section": "问题 1: Chromium 没有使用保存的 Profile 打开",
        "alt_sections": ["问题 11: 登录态频繁过期"]
    },
    
    # 浏览器启动问题
    "browser_launch": {
        "keywords": ["launch", "启动浏览器失败", "Chrome", "Chromium", "executable"],
        "reference_section": "问题 7: Chrome/Chromium 找不到",
        "alt_sections": ["问题 8: Windows 上 Playwright 安装失败"]
    },
    
    # 端口占用
    "port_in_use": {
        "keywords": ["port", "端口", "9222", "CDP", "address already in use"],
        "reference_section": "问题 9: 端口 9222 被占用"
    },
    
    # 自动化检测
    "automation_detected": {
        "keywords": ["webdriver", "automation", "检测", "blocked", "forbidden"],
        "reference_section": "问题 3: Playwright 被网站检测为自动化浏览器"
    },
    
    # 数据加载问题
    "data_not_loaded": {
        "keywords": ["timeout", "超时", "暂无内容", "0 条数据", "spinner"],
        "reference_section": "问题 5: 表格数据未加载完成就抓取"
    },
    
    # 手机号脱敏
    "phone_masked": {
        "keywords": ["****", "脱敏", "EyeInvisible", "手机号"],
        "reference_section": "问题 4: 手机号显示为脱敏格式"
    },
    
    # API 认证问题
    "api_auth": {
        "keywords": ["401", "Token", "APP_KEY", "认证失败", "auth"],
        "reference_section": "问题 10: APP_KEY 无效或过期"
    },
    
    # 路径问题
    "path_not_found": {
        "keywords": ["No such file", "找不到路径", "FileNotFoundError", "path"],
        "reference_section": "问题 6: 跨平台路径问题"
    },
    
    # 重复数据
    "duplicate_data": {
        "keywords": ["重复", "duplicate", "已存在", "去重"],
        "reference_section": "问题 12: 同步重复客户"
    },
    
    # 钥匙串问题 (macOS)
    "keychain_prompt": {
        "keywords": ["keychain", "钥匙串", "密码", "password"],
        "reference_section": "问题 2: macOS 钥匙串弹窗要求输入密码"
    }
}


def classify_error(error_msg: str) -> Optional[str]:
    """根据错误信息分类错误类型。
    
    Args:
        error_msg: 错误信息字符串
        
    Returns:
        错误类型 key，如 "login_expired"，无法分类返回 None
    """
    error_lower = error_msg.lower()
    
    for error_type, config in ERROR_PATTERNS.items():
        for keyword in config["keywords"]:
            if keyword.lower() in error_lower:
                return error_type
    
    return None


def get_reference_content(section_title: str) -> Optional[str]:
    """从 troubleshooting.md 读取指定章节内容。
    
    Args:
        section_title: 章节标题，如 "问题 1: Chromium 没有使用保存的 Profile 打开"
        
    Returns:
        章节内容字符串，找不到返回 None
    """
    # 查找 troubleshooting.md
    skill_root = Path(__file__).resolve().parents[1]
    troubleshooting_path = skill_root / "references" / "troubleshooting.md"
    
    if not troubleshooting_path.exists():
        return None
    
    try:
        content = troubleshooting_path.read_text(encoding="utf-8")
    except Exception:
        return None
    
    # 解析章节内容
    # 格式: ## 问题 X: 标题\n\n内容...\n\n---
    pattern = rf"## {re.escape(section_title)}\n\n(.*?)(?=\n---|\n## |\Z)"
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        return match.group(1).strip()
    
    return None


def get_error_reference(error_msg: str) -> Dict:
    """根据错误信息获取参考的 reference 内容。
    
    Args:
        error_msg: 错误信息字符串
        
    Returns:
        包含 reference 信息的字典:
        {
            "error_type": "login_expired",
            "main_reference": "...",
            "alt_references": ["..."],
            "hint": "..."
        }
    """
    error_type = classify_error(error_msg)
    
    if not error_type:
        return {
            "error_type": None,
            "main_reference": None,
            "alt_references": [],
            "hint": "未找到匹配的 reference，请根据错误信息自行判断"
        }
    
    config = ERROR_PATTERNS[error_type]
    
    # 获取主要 reference
    main_ref = get_reference_content(config["reference_section"])
    
    # 获取备选 reference
    alt_refs = []
    for section in config.get("alt_sections", []):
        ref = get_reference_content(section)
        if ref:
            alt_refs.append(ref)
    
    return {
        "error_type": error_type,
        "main_reference": main_ref,
        "alt_references": alt_refs,
        "hint": f"检测到错误类型: {error_type}，以下是相关参考信息（仅供参考，请根据实际情况灵活处理）"
    }


def format_error_with_reference(error_msg: str, original_error: Exception = None) -> str:
    """格式化错误信息，附带 reference 参考。
    
    Args:
        error_msg: 错误信息
        original_error: 原始异常对象
        
    Returns:
        格式化后的错误信息字符串
    """
    ref_info = get_error_reference(error_msg)
    
    output = []
    output.append(f"❌ 错误: {error_msg}")
    
    if original_error:
        output.append(f"   详情: {type(original_error).__name__}: {original_error}")
    
    output.append("")
    
    if ref_info["error_type"]:
        output.append(f"📖 {ref_info['hint']}")
        output.append("")
        
        if ref_info["main_reference"]:
            output.append("【主要参考】")
            output.append(ref_info["main_reference"])
            output.append("")
        
        if ref_info["alt_references"]:
            output.append("【其他可能相关的参考】")
            for i, ref in enumerate(ref_info["alt_references"], 1):
                output.append(f"参考 {i}:")
                output.append(ref)
                output.append("")
        
        output.append("💡 以上信息仅供参考，请根据用户的具体情况分析并解决。")
    else:
        output.append(ref_info["hint"])
    
    return "\n".join(output)


def handle_error(error_msg: str, original_error: Exception = None, raise_after_log: bool = False):
    """处理错误：记录日志、输出 reference 参考。
    
    Args:
        error_msg: 错误信息
        original_error: 原始异常对象
        raise_after_log: 是否在处理后重新抛出异常
    """
    formatted = format_error_with_reference(error_msg, original_error)
    print(formatted)
    
    if raise_after_log and original_error:
        raise original_error


# 便捷函数：在 except 块中使用
def log_error_with_reference(e: Exception, context: str = ""):
    """在 except 块中调用，自动提取错误信息并查阅 reference。
    
    用法:
        try:
            # 可能出错的代码
        except Exception as e:
            log_error_with_reference(e, "启动浏览器时")
    """
    error_msg = f"{context}: {str(e)}" if context else str(e)
    handle_error(error_msg, e)


if __name__ == "__main__":
    # 测试
    test_errors = [
        "Chrome CDP 端口 9222 未就绪",
        "巨懂车登录态过期（URL 含 login）",
        "未找到 Chrome 浏览器，请先运行: playwright install chromium",
        "大风车 Token 过期: 401 Unauthorized",
        "等待 Arco 表格容器超时",
    ]
    
    for err in test_errors:
        print("=" * 60)
        print(format_error_with_reference(err))
        print()
