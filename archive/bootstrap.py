#!/usr/bin/env python3
"""一键启动入口。

先检查运行前置条件：
- 运行安装检查（Python 依赖、playwright、Chromium）
- 配置文件
- APP_KEY 环境变量

然后直接拉起 sync_daemon.py 的主循环。
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def run_install_check():
    """运行安装检查，返回是否通过。"""
    try:
        import install_check
        return install_check.main() == 0
    except ImportError:
        print("警告: install_check.py 不存在，跳过安装检查")
        return True


def main() -> None:
    # 首先运行安装检查
    print("正在检查安装环境...")
    if not run_install_check():
        print("\n安装检查未通过，请先安装缺失的依赖。")
        sys.exit(1)
    
    # 导入 sync_daemon（必须在安装检查之后，因为依赖 playwright）
    import sync_daemon  # noqa: E402
    
    config_path = ROOT / "config" / "config.json"
    if not config_path.exists():
        print(f"\n缺少配置文件: {config_path}")
        print(f"请先复制: cp {ROOT / 'config' / 'config.example.json'} {config_path}")
        sys.exit(1)

    config = sync_daemon.load_config(config_path)
    issues = sync_daemon.check_runtime(config, require_app_key=True)
    if issues:
        print("\n运行检查未通过:")
        for issue in issues:
            print(f"- {issue}")
        sys.exit(1)

    app_key_env = config.get("dfc", {}).get("app_key_env", "APP_KEY")
    print(f"\n运行检查通过，准备启动守护进程。使用环境变量: {app_key_env}")
    os.execv(
        sys.executable,
        [
            sys.executable,
            str(ROOT / "scripts" / "sync_daemon.py"),
        ],
    )


if __name__ == "__main__":
    main()
