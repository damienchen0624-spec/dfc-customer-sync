#!/usr/bin/env python3
"""交互式设置向导 - 一键完成所有配置。

用法：
  python scripts/setup_wizard.py

向导会引导用户完成：
1. 检测并安装依赖（playwright、chromium）
2. 交互式输入 APP_KEY
3. 自动生成 config.json 和 .env
4. 启动浏览器登录巨懂车
5. 登录成功后启动守护进程
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# 添加 scripts 目录到路径
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import platform_utils


def print_header():
    """打印欢迎信息。"""
    print()
    print("=" * 60)
    print("  巨懂车客户同步大风车 - 设置向导")
    print("=" * 60)
    print()
    print("这个向导会帮你完成所有配置，只需要几分钟。")
    print()


def print_step(step_num: int, title: str):
    """打印步骤标题。"""
    print()
    print(f"━━━ 步骤 {step_num}: {title} ━━━")
    print()


def check_python_version() -> bool:
    """检查 Python 版本。"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 版本过低: {version.major}.{version.minor}")
        print("   需要 Python 3.8 或更高版本")
        return False
    print(f"✅ Python 版本: {version.major}.{version.minor}.{version.micro}")
    return True


def check_and_install_playwright() -> bool:
    """检查并安装 playwright。"""
    try:
        import playwright
        print("✅ Playwright 已安装")
        return True
    except ImportError:
        print("⚠️  Playwright 未安装，正在安装...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "-q"])
            print("✅ Playwright 安装成功")
            return True
        except Exception as e:
            print(f"❌ 安装 Playwright 失败: {e}")
            return False


def check_and_install_chromium() -> bool:
    """检查并安装 Chromium 浏览器。"""
    chrome_binary = platform_utils.find_chrome_binary()
    if chrome_binary:
        print(f"✅ Chromium 已安装: {chrome_binary}")
        return True
    
    print("⚠️  Chromium 未安装，正在安装...")
    print("   （这可能需要几分钟，取决于网络速度）")
    try:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("✅ Chromium 安装成功")
        return True
    except Exception as e:
        print(f"❌ 安装 Chromium 失败: {e}")
        return False


def get_app_key() -> str:
    """交互式获取 APP_KEY。"""
    print("APP_KEY 用于连接大风车 CRM 系统。")
    print("获取方式: 大风车开放平台 → 应用管理 → 查看 APP_KEY")
    print()
    
    while True:
        app_key = input("请输入你的 APP_KEY: ").strip()
        if not app_key:
            print("❌ APP_KEY 不能为空，请重新输入")
            continue
        if len(app_key) < 10:
            print("❌ APP_KEY 格式似乎不正确，请检查")
            continue
        
        # 确认输入
        confirm = input(f"确认使用 APP_KEY: {app_key[:6]}...{app_key[-4:]}? (y/n): ").strip().lower()
        if confirm == 'y':
            return app_key
        print("请重新输入")


def create_config_file(app_key: str) -> Path:
    """创建配置文件。"""
    config_dir = ROOT / "config"
    config_dir.mkdir(exist_ok=True)
    
    config_path = config_dir / "config.json"
    app_data = str(platform_utils.get_app_data_dir())
    
    config = {
        "jvdc": {
            "list_url": "https://www.autoengine.com/apps/usedcar-customer/customer/customer-profile-list",
            "login_url": "https://www.autoengine.com/login"
        },
        "browser": {
            "user_data_dir": "<APP_DATA>/jvdc-browser",
            "headless": False
        },
        "sync": {
            "interval_minutes": 10,
            "lead_type_filter": ["表单线索"]
        },
        "dfc": {
            "app_key_env": "APP_KEY",
            "owner_id": "",
            "owner_name": ""
        },
        "state_file": "<APP_DATA>/jvdc-sync/state.json",
        "log_file": "<APP_DATA>/jvdc-sync/sync.log"
    }
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 配置文件已创建: {config_path}")
    return config_path


def create_env_file(app_key: str) -> Path:
    """创建环境变量文件。"""
    env_path = ROOT / ".env"
    
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(f"APP_KEY={app_key}\n")
    
    print(f"✅ 环境变量文件已创建: {env_path}")
    return env_path


def load_app_key_from_env() -> str:
    """从 .env 文件加载 APP_KEY。"""
    env_path = ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("APP_KEY="):
                    return line.split("=", 1)[1].strip()
    return ""


def run_browser_setup():
    """运行浏览器登录设置。"""
    import sync_daemon
    
    config_path = ROOT / "config" / "config.json"
    config = sync_daemon.load_config(config_path)
    
    # 加载 APP_KEY 到环境变量
    app_key = load_app_key_from_env()
    if app_key:
        os.environ["APP_KEY"] = app_key
    
    print()
    print("即将打开浏览器，请在浏览器中登录巨懂车。")
    print("登录成功后，页面会自动跳转到客户列表页面。")
    print()
    input("按 Enter 键继续...")
    
    sync_daemon.run_setup(config)


def run_daemon():
    """启动守护进程。"""
    import sync_daemon
    
    config_path = ROOT / "config" / "config.json"
    config = sync_daemon.load_config(config_path)
    
    # 加载 APP_KEY 到环境变量
    app_key = load_app_key_from_env()
    if app_key:
        os.environ["APP_KEY"] = app_key
    
    print()
    print("🚀 启动同步守护进程...")
    print("   按 Ctrl+C 可以停止")
    print()
    
    sync_daemon.run_daemon(config)


def main():
    """主函数。"""
    print_header()
    
    # 步骤 1: 检查环境
    print_step(1, "检查运行环境")
    
    if not check_python_version():
        sys.exit(1)
    
    if not check_and_install_playwright():
        sys.exit(1)
    
    if not check_and_install_chromium():
        sys.exit(1)
    
    # 步骤 2: 配置 APP_KEY
    print_step(2, "配置大风车 APP_KEY")
    
    # 检查是否已有 APP_KEY
    existing_key = load_app_key_from_env()
    if existing_key:
        print(f"检测到已有的 APP_KEY: {existing_key[:6]}...{existing_key[-4:]}")
        change = input("是否修改? (y/n): ").strip().lower()
        if change == 'y':
            app_key = get_app_key()
        else:
            app_key = existing_key
    else:
        app_key = get_app_key()
    
    # 步骤 3: 创建配置文件
    print_step(3, "创建配置文件")
    
    create_config_file(app_key)
    create_env_file(app_key)
    
    # 步骤 4: 浏览器登录
    print_step(4, "登录巨懂车")
    
    run_browser_setup()
    
    # 步骤 5: 启动守护进程
    print_step(5, "启动同步服务")
    
    print("配置完成！")
    print()
    start_now = input("是否立即启动同步服务? (y/n): ").strip().lower()
    
    if start_now == 'y':
        run_daemon()
    else:
        print()
        print("✅ 设置完成！")
        print()
        print("后续启动方式:")
        print(f"  cd {ROOT}")
        print("  python scripts/sync_daemon.py")
        print()
        print("或使用一键启动:")
        print(f"  python scripts/bootstrap.py")
        print()


if __name__ == "__main__":
    main()
