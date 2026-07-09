#!/usr/bin/env python3
"""跨平台工具模块 - 处理 macOS/Windows/Linux 差异。"""

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional, List


def get_os_type() -> str:
    """返回操作系统类型: 'macos', 'windows', 'linux'"""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    else:
        return "linux"


def get_app_data_dir() -> Path:
    """获取应用程序数据目录（跨平台）。"""
    os_type = get_os_type()
    if os_type == "macos":
        return Path.home() / "Library" / "Application Support" / "大风车 AI 龙虾"
    elif os_type == "windows":
        # Windows: %APPDATA%/大风车 AI 龙虾
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "大风车 AI 龙虾"
        return Path.home() / "AppData" / "Roaming" / "大风车 AI 龙虾"
    else:
        # Linux: ~/.local/share/大风车 AI 龙虾
        return Path.home() / ".local" / "share" / "大风车 AI 龙虾"


def get_playwright_cache_dir() -> Path:
    """获取 Playwright 浏览器缓存目录（跨平台）。"""
    os_type = get_os_type()
    if os_type == "macos":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    elif os_type == "windows":
        # Windows: %LOCALAPPDATA%/ms-playwright
        localappdata = os.environ.get("LOCALAPPDATA", "")
        if localappdata:
            return Path(localappdata) / "ms-playwright"
        return Path.home() / "AppData" / "Local" / "ms-playwright"
    else:
        # Linux: ~/.cache/ms-playwright
        return Path.home() / ".cache" / "ms-playwright"


def find_system_chrome_binary() -> Optional[str]:
    """查找系统安装的 Chrome 或 Edge（非 Playwright 版本）。
    
    系统浏览器不会被注入 Playwright 自动化特征，
    适合用于需要绕过网站反自动化检测的场景。
    优先查找 Chrome，找不到则查找 Edge（Windows 自带）。
    """
    os_type = get_os_type()
    
    if os_type == "macos":
        # 优先 Chrome
        system_chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if Path(system_chrome).exists():
            return system_chrome
        # 回退 Edge
        system_edge = "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
        if Path(system_edge).exists():
            return system_edge
    elif os_type == "windows":
        # 优先 Chrome
        for env_var in ["PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"]:
            base = os.environ.get(env_var, "")
            if base:
                chrome_path = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
                if chrome_path.exists():
                    return str(chrome_path)
        # 回退 Edge（Windows 10/11 自带）
        for env_var in ["PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"]:
            base = os.environ.get(env_var, "")
            if base:
                edge_path = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
                if edge_path.exists():
                    return str(edge_path)
    else:
        # Linux
        for p in ["/usr/bin/google-chrome", "/usr/bin/microsoft-edge", "/usr/bin/chromium-browser", "/usr/bin/chromium"]:
            if Path(p).exists():
                return p
    
    return None


def find_chrome_binary() -> Optional[str]:
    """查找 Chrome/Chromium 可执行文件（跨平台）。
    
    优先返回系统 Chrome（自动化特征更少），
    找不到时回退到 Playwright 的 Chromium。
    """
    # 1. 优先使用系统 Chrome
    system = find_system_chrome_binary()
    if system:
        return system
    
    # 2. 回退到 Playwright 的 Chromium
    os_type = get_os_type()
    pw_cache = get_playwright_cache_dir()
    if pw_cache.exists():
        if os_type == "macos":
            for d in sorted(pw_cache.iterdir(), reverse=True):
                if not d.name.startswith("chromium-"):
                    continue
                for arch in ["arm64", "x64"]:
                    p = d / f"chrome-mac-{arch}" / "Google Chrome for Testing.app" / "Contents" / "MacOS" / "Google Chrome for Testing"
                    if p.exists():
                        return str(p)
        elif os_type == "windows":
            for d in sorted(pw_cache.iterdir(), reverse=True):
                if not d.name.startswith("chromium-"):
                    continue
                p = d / "chrome-win64" / "chrome.exe"
                if p.exists():
                    return str(p)
                p = d / "chrome-win" / "chrome.exe"
                if p.exists():
                    return str(p)
        else:
            for d in sorted(pw_cache.iterdir(), reverse=True):
                if not d.name.startswith("chromium-"):
                    continue
                p = d / "chrome-linux" / "chrome"
                if p.exists():
                    return str(p)
    
    return None


def find_python_executable() -> str:
    """获取当前 Python 可执行文件路径。"""
    return sys.executable


def kill_process_on_port(port: int) -> bool:
    """杀死占用指定端口的进程（跨平台）。返回是否成功。"""
    os_type = get_os_type()
    
    try:
        if os_type == "windows":
            # Windows: 使用 netstat + taskkill
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        subprocess.run(
                            ["taskkill", "/F", "/PID", pid],
                            capture_output=True, timeout=5
                        )
                        return True
        else:
            # macOS/Linux: 使用 lsof + kill
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split()
                for pid in pids:
                    subprocess.run(
                        ["kill", "-9", pid],
                        capture_output=True, timeout=5
                    )
                return True
    except Exception:
        pass
    
    return False


def get_default_browser_data_dir() -> Path:
    """获取默认的浏览器数据目录（跨平台）。"""
    return get_app_data_dir() / "jvdc-browser"


def ensure_dir(path: Path) -> Path:
    """确保目录存在。"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def open_file_with_default(filepath: str):
    """用默认程序打开文件（跨平台）。"""
    os_type = get_os_type()
    try:
        if os_type == "macos":
            subprocess.run(["open", filepath], check=False)
        elif os_type == "windows":
            os.startfile(filepath)
        else:
            subprocess.run(["xdg-open", filepath], check=False)
    except Exception:
        pass
