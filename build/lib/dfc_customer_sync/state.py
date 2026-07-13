#!/usr/bin/env python3
"""本地同步状态：上次同步时间 + 已同步手机号集合。重启不丢进度。"""

import json
from pathlib import Path
from typing import Dict, Set


def load_state(path: Path) -> Dict:
    """读取状态文件；不存在则返回空状态。"""
    path = Path(path).expanduser()
    if not path.exists():
        return {"last_sync_time": None, "synced_phones": set(), "stats": {}}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        "last_sync_time": raw.get("last_sync_time"),
        "synced_phones": set(raw.get("synced_phones", [])),
        "stats": raw.get("stats", {}),
    }


def save_state(path: Path, state: Dict) -> None:
    """写状态文件；synced_phones 序列化为 list。"""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        "last_sync_time": state.get("last_sync_time"),
        "synced_phones": sorted(state.get("synced_phones", set())),
        "stats": state.get("stats", {}),
    }
    path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")


def is_synced(state: Dict, phone: str) -> bool:
    """该手机号是否已在本地同步集合中。"""
    return phone in state.get("synced_phones", set())
