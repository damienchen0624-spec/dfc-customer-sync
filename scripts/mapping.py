#!/usr/bin/env python3
"""巨懂车 → 大风车 客户字段映射。

只保留同步流程中实际使用的映射：
- 来源渠道映射（巨懂车渠道 → 大风车 source code）
- 意向等级映射（巨懂车级别/状态 → 大风车 grade code）
- 性别映射
- 重点客户映射
"""

from typing import Dict, Optional


# ============================================================
# 意向等级映射
# ============================================================
STATUS_TO_GRADE = {
    "未联系": "C",
    "已联系": "B",
    "跟进中": "B",
    "待跟进": "B",
    "已成交": "A",
}


def map_grade(jvdc_grade: str, status: str = "") -> str:
    """意向等级：优先用巨懂车的级别(H/A/B/C/N)，为空时按状态推断，再为空默认 C。"""
    grade = (jvdc_grade or "").strip().upper()
    if grade in {"H", "A", "B", "C", "N"}:
        return grade
    return STATUS_TO_GRADE.get((status or "").strip(), "C")


# ============================================================
# 性别映射
# ============================================================
def map_gender(gender: str) -> str:
    """映射性别到中文名。"""
    gender_map = {"male": "先生", "female": "女士", "unknown": "未知"}
    return gender_map.get((gender or "").strip(), "未知")


# ============================================================
# 完整枚举字典（中文名 → CRM code）
# 只保留同步流程中实际使用的字段
# ============================================================

GENDER = {
    "未知": "wNKMp8Ch7i_option_value_KhKmECpaHp",
    "女士": "wNKMp8Ch7i_option_value_8dMZneOyy8",
    "先生": "wNKMp8Ch7i_option_value_EBgvTdW2pX",
}

SOURCE = {
    "易车二手车": "biauto", "车易拍": "cheyipai", "二手车之家": "che168",
    "直接到店": "arrive-store", "微店": "weidian", "华夏": "huaxia",
    "抖音": "douyin", "快手": "kuaishou", "58同城": "58", "优信": "uxin",
    "易车": "yiche", "淘车": "taoche", "微信": "weixin", "广播": "broadcast",
    "闲鱼": "xianyu", "朋友、老客户介绍": "friend", "同行报车": "thbc",
    "同行介绍": "tonghang", "视频号": "tengxun_live", "其他": "other",
    "大搜车小程序": "DSCxcx", "懂车帝": "dongchedi", "大黄蜂": "dahuangfeng",
    "微信运营平台": "wxyypt", "商家服务小程序": "sjfwxcx", "先试后买": "xshm",
    "查询车型": "cxcx", "车源广场": "cygc", "微店我要卖车": "wdwymc",
    "微店估值": "wdgz", "估价报告": "gjbg", "车型识别报告": "cxsbbg",
    "微店-新车特卖": "xctm", "准新车": "0esc", "高德": "gaode",
    "268v app": "268vapp", "268v 小程序": "268vxcx", "信车智联": "xczl",
    "置换": "dealer_gKABSL75Rj", "陌拜": "dealer_cbslTsCRXn",
    "同行转介绍": "dealer_31OgGLg3hF", "小红书": "xiaohongshu",
    "新链": "xinlian", "工作号": "gzh",
}

GRADE = {
    "H": "Ak4w1BZMgi_option_value_4Ws1V9z6hU",
    "A": "Ak4w1BZMgi_option_value_IOwZgg7Pjo",
    "B": "Ak4w1BZMgi_option_value_SAMJz6ftFo",
    "C": "Ak4w1BZMgi_option_value_uGamiNQBE7",
    "N": "Ak4w1BZMgi_option_value_g6sNRxol3z",
    "战败": "Ak4w1BZMgi_option_value_TC6LKLwU1K",
    "无效": "Ak4w1BZMgi_option_value_ahKE7glJFv",
}

IMPORTANT = {"是": "0ue2M9kYdr_option_value_KBeQ4vo2zW", "否": "0ue2M9kYdr_option_value_4QsHa1icRJ"}
