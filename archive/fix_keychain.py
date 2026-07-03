#!/usr/bin/env python3
"""修复 macOS 钥匙串访问权限。

解决 Playwright Chromium 每次启动时要求输入系统密码的问题。
仅在 macOS 上需要运行。
"""

import platform
import subprocess
import sys
from pathlib import Path


def is_macos() -> bool:
    """检查是否为 macOS 系统。"""
    return platform.system().lower() == "darwin"


def find_playwright_chromium() -> str:
    """查找 Playwright Chromium 的路径。"""
    pw_cache = Path.home() / "Library" / "Caches" / "ms-playwright"
    if not pw_cache.exists():
        return None
    
    # 查找最新的 chromium 目录
    for d in sorted(pw_cache.iterdir(), reverse=True):
        if d.name.startswith("chromium-"):
            # 尝试 arm64 和 x64
            for arch in ["arm64", "x64"]:
                chrome_path = d / f"chrome-mac-{arch}" / "Google Chrome for Testing.app" / "Contents" / "MacOS" / "Google Chrome for Testing"
                if chrome_path.exists():
                    return str(chrome_path)
    return None


def get_keychain_password() -> str:
    """从钥匙串获取 Chromium Safe Storage 的密码。"""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-l", "Chromium Safe Storage", "-g"],
            capture_output=True, text=True, timeout=10
        )
        # 密码在 stderr 中，格式: password: "xxx"
        for line in result.stderr.split("\n"):
            if line.strip().startswith("password:"):
                # 提取引号中的密码
                parts = line.split('"')
                if len(parts) >= 2:
                    return parts[1]
    except Exception as e:
        print(f"获取钥匙串密码失败: {e}")
    return None


def fix_keychain_access():
    """修复钥匙串访问权限。"""
    if not is_macos():
        print("❌ 此脚本仅适用于 macOS")
        return False
    
    print("🔍 正在检查 macOS 钥匙串设置...\n")
    
    # 1. 查找 Playwright Chromium
    chrome_path = find_playwright_chromium()
    if not chrome_path:
        print("❌ 未找到 Playwright Chromium")
        print("请先运行: playwright install chromium")
        return False
    
    print(f"✅ 找到 Chromium: {chrome_path}")
    
    # 2. 获取 Python 路径
    python_path = sys.executable
    print(f"✅ Python 路径: {python_path}")
    
    # 3. 检查钥匙串项目是否存在
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-l", "Chromium Safe Storage"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            print("ℹ️  Chromium Safe Storage 钥匙串项目不存在")
            print("这通常意味着还没有运行过 Chromium，可以跳过此修复")
            return True
    except Exception as e:
        print(f"❌ 检查钥匙串失败: {e}")
        return False
    
    print("✅ 找到 Chromium Safe Storage 钥匙串项目")
    
    # 4. 获取当前密码
    password = get_keychain_password()
    if not password:
        print("❌ 无法获取钥匙串密码")
        print("请手动在钥匙串访问应用中修改 Chromium Safe Storage 的访问控制")
        return False
    
    print("✅ 获取到钥匙串密码")
    
    # 5. 删除旧的钥匙串项目
    print("\n🔄 正在更新钥匙串访问控制...")
    try:
        subprocess.run(
            ["security", "delete-generic-password", "-l", "Chromium Safe Storage"],
            capture_output=True, text=True, timeout=10
        )
        print("✅ 已删除旧的钥匙串项目")
    except Exception as e:
        print(f"⚠️  删除旧项目失败: {e}")
    
    # 6. 重新创建，添加允许的应用程序
    try:
        result = subprocess.run(
            [
                "security", "add-generic-password",
                "-a", "Chromium",
                "-s", "Chromium Safe Storage",
                "-w", password,
                "-T", chrome_path,
                "-T", python_path,
                "-T", "/usr/bin/security",
            ],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print("✅ 已创建新的钥匙串项目")
            print(f"✅ 已授权: Chromium")
            print(f"✅ 已授权: Python")
            return True
        else:
            print(f"❌ 创建新项目失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 创建新项目失败: {e}")
        return False


def main():
    """主函数。"""
    print("="*50)
    print("  macOS 钥匙串修复工具")
    print("="*50)
    print()
    
    if not is_macos():
        print("❌ 此工具仅适用于 macOS")
        return 1
    
    print("此工具将修复 Playwright Chromium 每次启动时")
    print("要求输入系统密码的问题。")
    print()
    
    response = input("是否继续？[y/N]: ").strip().lower()
    if response not in ["y", "yes", "是"]:
        print("已取消")
        return 0
    
    print()
    success = fix_keychain_access()
    
    print()
    print("="*50)
    if success:
        print("✅ 修复完成！")
        print("现在 Playwright Chromium 应该可以无需密码访问了。")
    else:
        print("❌ 修复失败")
        print("请手动在钥匙串访问应用中修改 Chromium Safe Storage 的访问控制")
    print("="*50)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
