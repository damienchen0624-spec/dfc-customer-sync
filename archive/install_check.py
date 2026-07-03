#!/usr/bin/env python3
"""安装前检查和自动安装依赖。

检测操作系统，检查所需依赖，提示用户安装缺失的组件。
支持 macOS / Windows / Linux。
"""

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def get_os_type() -> str:
    """返回操作系统类型: 'macos', 'windows', 'linux'"""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    else:
        return "linux"


def print_header(text: str):
    """打印带样式的标题。"""
    print(f"\n{'='*50}")
    print(f"  {text}")
    print(f"{'='*50}\n")


def print_success(text: str):
    """打印成功信息。"""
    print(f"  ✅ {text}")


def print_error(text: str):
    """打印错误信息。"""
    print(f"  ❌ {text}")


def print_warning(text: str):
    """打印警告信息。"""
    print(f"  ⚠️  {text}")


def print_info(text: str):
    """打印普通信息。"""
    print(f"  ℹ️  {text}")


def check_python_version() -> Tuple[bool, str]:
    """检查 Python 版本是否 >= 3.8。"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    return False, f"Python {version.major}.{version.minor}.{version.micro} (需要 >= 3.8)"


def check_pip() -> Tuple[bool, str]:
    """检查 pip 是否可用。"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip().split()[1]
            return True, f"pip {version}"
    except Exception:
        pass
    return False, "pip 未安装"


def check_playwright() -> Tuple[bool, str]:
    """检查 playwright Python 包是否已安装。"""
    try:
        import playwright
        # playwright 没有 __version__，通过 pip 获取版本
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", "playwright"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.split("\n"):
                if line.startswith("Version:"):
                    version = line.split(":", 1)[1].strip()
                    return True, f"playwright {version}"
        except Exception:
            pass
        return True, "playwright 已安装"
    except ImportError:
        return False, "playwright 未安装"


def check_chromium() -> Tuple[bool, str]:
    """检查 Playwright Chromium 是否已安装。"""
    os_type = get_os_type()
    
    # 查找 Playwright 缓存目录
    if os_type == "macos":
        pw_cache = Path.home() / "Library" / "Caches" / "ms-playwright"
    elif os_type == "windows":
        localappdata = os.environ.get("LOCALAPPDATA", "")
        if localappdata:
            pw_cache = Path(localappdata) / "ms-playwright"
        else:
            pw_cache = Path.home() / "AppData" / "Local" / "ms-playwright"
    else:
        pw_cache = Path.home() / ".cache" / "ms-playwright"
    
    if not pw_cache.exists():
        return False, "Playwright 浏览器缓存目录不存在"
    
    # 查找 chromium 目录
    for d in pw_cache.iterdir():
        if d.name.startswith("chromium-"):
            return True, f"Chromium 已安装 ({d.name})"
    
    return False, "Chromium 未安装"


def check_xcode_tools() -> Tuple[bool, str]:
    """检查 macOS Xcode Command Line Tools（仅 macOS）。"""
    if get_os_type() != "macos":
        return True, "N/A (非 macOS)"
    
    try:
        result = subprocess.run(
            ["xcode-select", "-p"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True, "Xcode Command Line Tools 已安装"
    except Exception:
        pass
    return False, "Xcode Command Line Tools 未安装"


def check_vc_redist() -> Tuple[bool, str]:
    """检查 Windows Visual C++ Redistributable（仅 Windows）。"""
    if get_os_type() != "windows":
        return True, "N/A (非 Windows)"
    
    # 检查常见的 VC++ 运行时 DLL
    system32 = Path(os.environ.get("SYSTEMROOT", "C:\\Windows")) / "System32"
    vc_dlls = ["vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"]
    
    found = []
    for dll in vc_dlls:
        if (system32 / dll).exists():
            found.append(dll)
    
    if found:
        return True, f"Visual C++ Redistributable 已安装 ({', '.join(found)})"
    return False, "Visual C++ Redistributable 可能未安装"


def install_playwright():
    """安装 playwright Python 包。"""
    print_info("正在安装 playwright...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "playwright"],
        capture_output=False, text=True
    )
    return result.returncode == 0


def install_chromium():
    """安装 Playwright Chromium 浏览器。"""
    print_info("正在安装 Chromium 浏览器...")
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=False, text=True
    )
    return result.returncode == 0


def install_xcode_tools():
    """安装 Xcode Command Line Tools（macOS）。"""
    print_info("正在安装 Xcode Command Line Tools...")
    print_info("系统会弹出安装对话框，请点击\"安装\"并等待完成。")
    result = subprocess.run(
        ["xcode-select", "--install"],
        capture_output=False, text=True
    )
    # xcode-select --install 会弹出 GUI 对话框，这里只是触发
    print_info("请按照系统提示完成安装，然后重新运行此检查。")
    return False  # 需要用户手动完成


def prompt_user(message: str) -> bool:
    """提示用户确认。"""
    while True:
        response = input(f"\n{message} [y/N]: ").strip().lower()
        if response in ["y", "yes", "是"]:
            return True
        if response in ["n", "no", "否", ""]:
            return False
        print("请输入 y 或 n")


def run_all_checks() -> dict:
    """运行所有检查，返回结果字典。"""
    os_type = get_os_type()
    
    checks = [
        ("Python 版本", check_python_version()),
        ("pip", check_pip()),
        ("playwright", check_playwright()),
        ("Chromium", check_chromium()),
    ]
    
    if os_type == "macos":
        checks.append(("Xcode Tools", check_xcode_tools()))
    elif os_type == "windows":
        checks.append(("VC++ Redistributable", check_vc_redist()))
    
    return dict(checks)


def main():
    """主函数。"""
    print_header("巨懂车客户同步 - 安装检查")
    
    os_type = get_os_type()
    os_names = {"macos": "macOS", "windows": "Windows", "linux": "Linux"}
    print_info(f"检测到操作系统: {os_names.get(os_type, os_type)}")
    print_info(f"Python: {sys.executable}")
    
    # 运行检查
    print("\n正在检查依赖项...\n")
    results = run_all_checks()
    
    # 显示结果
    all_passed = True
    for name, (passed, msg) in results.items():
        if passed:
            print_success(f"{name}: {msg}")
        else:
            print_error(f"{name}: {msg}")
            all_passed = False
    
    if all_passed:
        print("\n" + "="*50)
        print_success("所有检查通过！可以开始使用。")
        print("="*50)
        return 0
    
    # 处理缺失的依赖
    print("\n" + "="*50)
    print_warning("部分依赖缺失，需要安装。")
    print("="*50)
    
    # 检查并安装 pip
    if not results.get("pip", (True, ""))[0]:
        print_error("pip 未安装，无法继续。")
        print_info("请手动安装 pip: https://pip.pypa.io/en/stable/installation/")
        return 1
    
    # 检查并安装 Xcode Tools (macOS)
    if os_type == "macos" and not results.get("Xcode Tools", (True, ""))[0]:
        if prompt_user("是否安装 Xcode Command Line Tools？"):
            install_xcode_tools()
            return 1  # 需要重新运行
    
    # 检查并安装 VC++ Redistributable (Windows)
    if os_type == "windows" and not results.get("VC++ Redistributable", (True, ""))[0]:
        print_warning("Visual C++ Redistributable 可能未安装。")
        print_info("Chromium 可能无法正常运行。")
        print_info("下载地址: https://aka.ms/vs/17/release/vc_redist.x64.exe")
        if not prompt_user("是否继续安装其他依赖？"):
            return 1
    
    # 安装 playwright
    if not results.get("playwright", (True, ""))[0]:
        if prompt_user("是否安装 playwright？"):
            if not install_playwright():
                print_error("playwright 安装失败")
                return 1
            print_success("playwright 安装完成")
    
    # 安装 Chromium
    if not results.get("Chromium", (True, ""))[0]:
        if prompt_user("是否安装 Chromium 浏览器？"):
            if not install_chromium():
                print_error("Chromium 安装失败")
                return 1
            print_success("Chromium 安装完成")
    
    print("\n" + "="*50)
    print_success("安装完成！请重新运行此检查确认所有依赖已就绪。")
    print("="*50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
