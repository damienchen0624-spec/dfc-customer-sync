#!/usr/bin/env python3
"""巨懂车 → 大风车 客户同步守护进程。

用法：
  python3 sync_daemon.py --setup     # 首次登录巨懂车，保存登录态
  python3 sync_daemon.py             # 启动守护进程
  python3 sync_daemon.py --status    # 查看状态
  python3 sync_daemon.py --reset     # 重置同步起点
  python3 sync_daemon.py --check     # 运行前自检

认证方式：
  - 巨懂车：浏览器 Cookie（Playwright 持久化登录态）
  - 大风车读写操作：APP_KEY → Token（不再需要浏览器）

v3.6 优化：
  - P0: 浏览器崩溃自动恢复 + 防止多实例运行（PID 锁）
  - P1: 浏览器健康检查 + 登录态过期醒目提示
  - P2: 日志轮转（5MB × 7 份）+ 错误分类（可恢复/不可恢复）
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Optional

import auth
import dfc_client
import error_handler
import jvdc_scraper
import state as state_mod
import platform_utils


# ============================================================
# 日志（P2: 日志轮转）
# ============================================================
def setup_logging(log_file_path: Path) -> logging.Logger:
    """配置日志：控制台 + 轮转文件（5MB × 7 份）。"""
    logger = logging.getLogger("dfc_sync")
    logger.setLevel(logging.INFO)
    # 避免重复添加 handler
    if logger.handlers:
        return logger

    fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # 轮转文件 handler: 5MB per file, keep 7 backups
    log_file_path = Path(log_file_path).expanduser()
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        str(log_file_path), maxBytes=5 * 1024 * 1024,
        backupCount=7, encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


# ============================================================
# PID 锁（P0: 防止多实例运行）
# ============================================================
class PidLock:
    """进程锁：确保只有一个守护进程实例运行。"""

    def __init__(self, pid_file: Path):
        self.pid_file = Path(pid_file).expanduser()
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)

    def is_running(self) -> Optional[int]:
        """检查是否有其他实例在运行。返回运行中的 PID，或 None。"""
        if not self.pid_file.exists():
            return None
        try:
            pid = int(self.pid_file.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            return None
        if pid == os.getpid():
            return None  # 是自己
        # 检查进程是否存活
        try:
            os.kill(pid, 0)
            return pid  # 进程存活
        except OSError:
            return None  # 进程已死，PID 文件是残留的

    def acquire(self) -> bool:
        """获取锁。使用 O_CREAT|O_EXCL 原子操作避免竞态条件。
        
        成功返回 True，已有实例运行返回 False。
        """
        running_pid = self.is_running()
        if running_pid is not None:
            return False
        # 原子创建：O_CREAT|O_EXCL 保证只有一个进程能成功创建
        try:
            fd = os.open(str(self.pid_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.write(fd, str(os.getpid()).encode("utf-8"))
            os.close(fd)
            return True
        except FileExistsError:
            # 竞态：另一个进程刚好创建了文件，再检查一次
            running_pid = self.is_running()
            if running_pid is not None:
                return False
            # 死进程残留，清理后重试一次
            try:
                self.pid_file.unlink()
                fd = os.open(str(self.pid_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                os.write(fd, str(os.getpid()).encode("utf-8"))
                os.close(fd)
                return True
            except (FileExistsError, OSError):
                return False

    def release(self):
        """释放锁。"""
        try:
            self.pid_file.unlink(missing_ok=True)
        except Exception:
            pass


# ============================================================
# 配置加载
# ============================================================
def load_config(path: Path) -> dict:
    """加载配置文件，自动替换 <APP_DATA> 占位符为跨平台的应用数据目录。"""
    config_text = Path(path).expanduser().read_text(encoding="utf-8")
    app_data = str(platform_utils.get_app_data_dir())
    config_text = config_text.replace("<APP_DATA>", app_data)
    return json.loads(config_text)


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _pid_file_path(config) -> Path:
    """PID 文件路径，和 state_file 同目录。"""
    state_file = Path(config["state_file"]).expanduser()
    return state_file.parent / "daemon.pid"


def _storage_state_path(config) -> str:
    """storage_state 文件路径，和 state_file 同目录。"""
    state_file = Path(config["state_file"]).expanduser()
    return str(state_file.parent / "jvdc_state.json")


# ============================================================
# 浏览器工具
# ============================================================
def _is_browser_alive(page) -> bool:
    """检查浏览器页面是否存活（P1: 健康检查）。"""
    try:
        page.evaluate("1")
        return True
    except Exception:
        return False


def _is_browser_crash_error(e: Exception) -> bool:
    """判断异常是否为浏览器崩溃类错误（P2: 错误分类）。"""
    msg = str(e).lower()
    crash_keywords = [
        "has been closed",
        "target page, context or browser",
        "browser has been closed",
        "context has been closed",
        "page has been closed",
        "connection closed",
        "broken pipe",
    ]
    return any(kw in msg for kw in crash_keywords)


def _is_recoverable_error(e: Exception) -> bool:
    """判断异常是否可恢复（P2: 错误分类）。
    
    可恢复：浏览器崩溃、网络超时、页面加载失败
    不可恢复：APP_KEY 无效、配置错误
    """
    if _is_browser_crash_error(e):
        return True
    msg = str(e).lower()
    recoverable_keywords = [
        "timeout", "timed out", "net::", "network",
        "err_connection", "err_name", "loading",
    ]
    return any(kw in msg for kw in recoverable_keywords)


def _navigate_reliable(page, url: str, timeout_ms: int = 30000, max_retries: int = 3):
    """可靠导航：networkidle + 空白页检测 + 自动重试。"""
    for attempt in range(1, max_retries + 1):
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        except Exception:
            pass
        try:
            body_len = page.evaluate("document.body ? document.body.innerText.length : 0")
        except Exception:
            body_len = 0
        if body_len > 50:
            return
        print(f"⚠️ 页面加载不完整（第{attempt}次），重试...")
        time.sleep(2)
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)


def _start_chrome_cdp(user_data_dir: str, port: int = 9222, timeout_sec: int = 30):
    """启动 Chrome 并开启 CDP 调试端口，返回 (进程, CDP URL)。"""
    import urllib.request

    os.makedirs(user_data_dir, exist_ok=True)
    platform_utils.kill_process_on_port(port)
    time.sleep(1)

    chrome_binary = platform_utils.find_chrome_binary()
    if not chrome_binary:
        raise RuntimeError("未找到 Chrome 浏览器，请先运行: playwright install chromium")

    print(f"启动 Chrome: {chrome_binary}")

    args = [
        chrome_binary,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--window-position=200,100",
        "--window-size=1280,800",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
    ]
    if platform_utils.get_os_type() == "macos":
        args.append("--password-store=basic")
    if platform_utils.get_os_type() == "windows":
        args.append("--disable-gpu-sandbox")
    subprocess.Popen(args)

    cdp_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        time.sleep(0.5)
        try:
            resp = urllib.request.urlopen(f"{cdp_url}/json/version", timeout=2)
            data = json.loads(resp.read())
            print(f"✅ Chrome CDP 就绪: {data.get('Browser', '?')}")
            return None, cdp_url
        except Exception:
            continue

    raise RuntimeError(f"Chrome CDP 端口 {port} 未就绪（{timeout_sec}秒超时）")


# ============================================================
# 业务逻辑
# ============================================================
def process_leads(leads, client: dfc_client.DfcClient, state, follower_mapping: Dict = None) -> dict:
    """处理一批新客户：去重 → 写入 → 更新状态。返回计数。"""
    synced = skipped = failed = 0
    failed_times = []
    for lead in leads:
        phone = lead["phone"]
        if state_mod.is_synced(state, phone):
            skipped += 1
            continue
        result = client.add_customer(lead, follower_mapping=follower_mapping)
        if result["ok"]:
            state["synced_phones"].add(phone)
            synced += 1
        else:
            error = result.get("error", {})
            if error.get("kind") == "auth":
                raise dfc_client.DfcApiError(
                    error.get("message", "大风车 Token 过期"), kind="auth"
                )
            failed += 1
            failed_times.append(lead.get("leave_time", ""))
    if leads:
        if failed_times:
            state["last_sync_time"] = min(failed_times)
        else:
            state["last_sync_time"] = max(l.get("leave_time", "") for l in leads)
    return {"synced": synced, "skipped": skipped, "failed": failed}


# ============================================================
# 浏览器启动（提取为独立函数，供恢复时重用）
# ============================================================
def _launch_browser(p, config, logger):
    """启动浏览器并返回 (page, ctx, cleanup_fn)。
    
    根据 config 中的 headless 设置选择启动方式。
    cleanup_fn 用于清理资源（仅非 headless 模式需要手动关闭 Chrome）。
    """
    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
    headless = config["browser"]["headless"]
    storage_path = _storage_state_path(config)
    os.makedirs(user_data_dir, exist_ok=True)

    def _load_cookies(ctx):
        if Path(storage_path).exists():
            try:
                storage_data = json.loads(Path(storage_path).read_text(encoding="utf-8"))
                if "cookies" in storage_data:
                    ctx.add_cookies(storage_data["cookies"])
                    logger.info(f"✅ 已加载 {len(storage_data['cookies'])} 个 cookies")
            except Exception as e:
                logger.warning(f"⚠️ 加载 storage_state 失败: {e}")

    if headless:
        args = ["--disable-blink-features=AutomationControlled"]
        if platform_utils.get_os_type() == "macos":
            args.append("--password-store=basic")
        ctx = p.chromium.launch_persistent_context(
            user_data_dir, headless=True, args=args,
        )
        _load_cookies(ctx)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        return page, ctx, lambda: None
    else:
        try:
            _, cdp_url = _start_chrome_cdp(user_data_dir)
            logger.info(f"Chrome 已启动 (CDP: {cdp_url})")
            browser = p.chromium.connect_over_cdp(cdp_url)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            _load_cookies(ctx)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            return page, ctx, lambda: logger.info("Chrome 需手动关闭（二进制直接启动的）")
        except RuntimeError as e:
            if "未就绪" in str(e) or "timeout" in str(e).lower():
                logger.warning("⚠️ CDP 启动超时，可能是 Keychain 弹窗需要授权")
                logger.info("🔄 自动尝试通过可见浏览器解锁 Keychain...")
                return _launch_browser_unlock_keychain(p, user_data_dir, storage_path, logger)
            raise


def _launch_browser_unlock_keychain(p, user_data_dir: str, storage_path: str, logger):
    """CDP 启动失败后，用 Playwright 可见模式打开浏览器解锁 Keychain。
    
    用户看到浏览器窗口后可能需要输入 Keychain 密码。
    解锁后保存 cookies，然后返回 page/ctx。
    """
    args = [
        "--disable-blink-features=AutomationControlled",
        "--window-position=200,100",
        "--window-size=1280,800",
    ]
    if platform_utils.get_os_type() == "macos":
        args.append("--password-store=basic")

    logger.info("📂 正在打开可见浏览器窗口（如需 Keychain 授权，请在弹窗中输入密码）...")

    ctx = p.chromium.launch_persistent_context(
        user_data_dir, headless=False, args=args,
    )

    # 等待用户处理 Keychain 弹窗（给足时间）
    logger.info("⏳ 等待浏览器就绪（如需 Keychain 授权，请在弹窗中操作）...")
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    # 尝试做一个简单操作来确认浏览器完全就绪
    try:
        page.evaluate("1")
        logger.info("✅ 浏览器已就绪，Keychain 已解锁")
    except Exception:
        # 等待更长时间
        time.sleep(5)
        try:
            page.evaluate("1")
            logger.info("✅ 浏览器已就绪")
        except Exception as e:
            logger.error(f"❌ 浏览器仍未就绪: {e}")
            ctx.close()
            raise RuntimeError("Keychain 解锁失败，请手动运行 --setup")

    # 保存 storage_state 以便后续 CDP 启动也能用
    try:
        storage_data = ctx.storage_state()
        Path(storage_path).parent.mkdir(parents=True, exist_ok=True)
        Path(storage_path).write_text(json.dumps(storage_data, ensure_ascii=False), encoding="utf-8")
        logger.info(f"✅ 登录态已保存到: {storage_path}")
    except Exception as e:
        logger.warning(f"⚠️ 保存 storage_state 失败: {e}")

    # 保持浏览器窗口打开，返回 page/ctx 供同步使用
    def cleanup():
        try:
            ctx.close()
        except Exception:
            pass
        logger.info("Chrome 已关闭")

    return page, ctx, cleanup


# ============================================================
# Setup
# ============================================================
def run_setup(config):
    """首次登录巨懂车。"""
    print("=== 巨懂车客户同步 setup ===\n")
    print("0. 检查依赖...")

    try:
        import playwright
        print("   ✅ playwright 已安装")
    except ImportError:
        print("   ❌ 缺少 playwright，请运行: pip install playwright")
        return

    chrome_binary = platform_utils.find_chrome_binary()
    if chrome_binary:
        print(f"   ✅ Chromium 已安装: {chrome_binary}")
    else:
        print("   ❌ 缺少 Chromium，请运行: playwright install chromium")
        return

    from playwright.sync_api import sync_playwright

    print("\n1. 检测大风车 APP_KEY...")
    app_key = os.environ.get("APP_KEY")
    if not app_key:
        print("   ❌ 未找到环境变量 APP_KEY")
        return
    print(f"   ✅ 找到 APP_KEY: {app_key[:8]}...{app_key[-4:]}")

    print("\n2. 验证 APP_KEY...")
    try:
        token = auth.get_token()
        account = auth.get_account_info(token)
        print(f"   ✅ Token 获取成功")
        print(f"   ✅ 门店: {account['shopName']} ({account['shopCode']})")
    except Exception as e:
        print(f"   ❌ APP_KEY 验证失败: {e}")
        print("   💡 请检查 APP_KEY 是否正确")
        return

    print("\n✅ APP_KEY 自检通过！\n")
    print("3. 打开浏览器，请登录巨懂车平台...")

    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
    storage_path = _storage_state_path(config)
    os.makedirs(user_data_dir, exist_ok=True)
    print(f"📁 浏览器 Profile 目录: {user_data_dir}")

    with sync_playwright() as p:
        # 使用 CDP 模式启动系统浏览器（避免 Playwright 注入 webdriver 特征）
        chrome_binary = platform_utils.find_system_chrome_binary()
        if not chrome_binary:
            print("   ❌ 找不到 Chrome 或 Edge 浏览器")
            print("   💡 请安装 Chrome 或使用 Edge（Windows 自带）")
            return
        
        print(f"   🌐 使用浏览器: {chrome_binary}")
        
        # 启动系统浏览器（CDP 模式）
        import subprocess
        chrome_proc = subprocess.Popen([
            chrome_binary,
            f"--remote-debugging-port=9222",
            f"--user-data-dir={user_data_dir}",
            "--disable-blink-features=AutomationControlled",
            "--window-position=200,100",
            "--window-size=1280,800",
        ])
        
        # 等待浏览器启动
        print("   ⏳ 等待浏览器启动...")
        time.sleep(3)
        
        try:
            # Playwright 通过 CDP 连接
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        except Exception as e:
            print(f"   ❌ 连接浏览器失败: {e}")
            chrome_proc.terminate()
            return
        
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        _navigate_reliable(page, config["jvdc"]["login_url"], timeout_ms=60000)
        print(f"\n🌐 登录页已加载: {page.url}")
        print("👉 请在浏览器中完成登录操作")
        print("⏳ 等待登录完成（最多 5 分钟）...")
        deadline = time.time() + 300
        while time.time() < deadline:
            time.sleep(3)
            current_url = page.url or ""
            if "login" not in current_url:
                try:
                    _navigate_reliable(page, config["jvdc"]["list_url"], timeout_ms=30000)
                    if "login" not in page.url:
                        ctx.storage_state(path=storage_path)
                        page.goto("about:blank", wait_until="domcontentloaded", timeout=10000)
                        time.sleep(2)
                        print("\n✅ 登录成功！登录态已保存")
                        print(f"✅ Cookie 已写入 profile: {user_data_dir}")
                        print(f"✅ storage_state 备份: {storage_path}")
                        print("\n🎉 Setup 完成！你可以关闭浏览器窗口了。")
                        print("💡 现在可以运行 `python scripts/sync_daemon.py` 启动同步守护进程")
                        return
                except Exception:
                    pass
            else:
                try:
                    body_len = page.evaluate("document.body ? document.body.innerText.length : 0")
                    if body_len < 50:
                        print("⚠️ 登录页空白，重新加载...")
                        _navigate_reliable(page, config["jvdc"]["login_url"], timeout_ms=30000)
                except Exception:
                    pass
        print("\n❌ 登录超时（5分钟），请重试")
        chrome_proc.terminate()


# ============================================================
# Daemon（P0: 浏览器崩溃自动恢复 + 多实例防护）
# ============================================================
class _BrowserRestartNeeded(Exception):
    """内部信号：浏览器需要重启。"""
    pass


def run_daemon(config):
    """守护进程主入口（含多实例防护 + 崩溃自动恢复）。"""
    from playwright.sync_api import sync_playwright

    print("=== 启动巨懂车客户同步 ===\n")

    # ---- P0: 多实例防护 ----
    pid_lock = PidLock(_pid_file_path(config))
    running_pid = pid_lock.is_running()
    if running_pid is not None:
        print(f"❌ 已有守护进程在运行 (PID: {running_pid})")
        print(f"💡 如需重启，请先停止旧进程: kill {running_pid}")
        return
    if not pid_lock.acquire():
        print("❌ 无法获取进程锁")
        return
    print(f"✅ 进程锁已获取 (PID: {os.getpid()})")

    # ---- 注册退出清理（占位，logger 创建后重新注册） ----
    _logger_ref = [None]  # 用 list 持有引用，让闭包能访问

    def _cleanup(signum=None, frame=None):
        if signum and _logger_ref[0]:
            _logger_ref[0].info("收到退出信号，守护进程停止")
        pid_lock.release()
        if _logger_ref[0]:
            _logger_ref[0].info("=== 守护进程已退出 ===")
        if signum:
            sys.exit(0)
    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)

    # ---- 前置检查 ----
    app_key = os.environ.get("APP_KEY")
    if not app_key:
        print("❌ 未找到环境变量 APP_KEY，无法启动")
        pid_lock.release()
        return
    print(f"✅ APP_KEY: {app_key[:8]}...{app_key[-4:]}")

    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
    if not Path(user_data_dir).exists():
        print(f"❌ 浏览器数据目录不存在: {user_data_dir}")
        print("💡 请先运行: python scripts/sync_daemon.py --setup")
        pid_lock.release()
        return
    print(f"✅ 浏览器 Profile: {user_data_dir}")

    try:
        token = auth.get_token()
        account = auth.get_account_info(token)
        print(f"✅ 门店: {account['shopName']} ({account['shopCode']})")
    except Exception as e:
        print(f"❌ APP_KEY 验证失败: {e}")
        pid_lock.release()
        return

    print()

    # ---- P2: 日志轮转 ----
    logger = setup_logging(config["log_file"])
    _logger_ref[0] = logger  # 让 signal handler 能访问
    logger.info(f"=== 守护进程启动 (PID: {os.getpid()}) ===")
    logger.info(f"大风车门店: {account['shopName']} ({account['shopCode']})")

    state_file = Path(config["state_file"]).expanduser()
    state = state_mod.load_state(state_file)

    owner_id = config.get("dfc", {}).get("owner_id", "")
    owner_name = config.get("dfc", {}).get("owner_name", "")

    client = dfc_client.DfcClient(
        token=token,
        shop_code=account["shopCode"],
        shop_name=account["shopName"],
        owner_id=owner_id,
        owner_name=owner_name,
    )
    logger.info("✅ 大风车 Token 客户端已就绪（读写均使用 APP_KEY）")

    if not state["last_sync_time"]:
        state["last_sync_time"] = now_str()
        state_mod.save_state(state_file, state)
        logger.info(f"首次启动，从 {state['last_sync_time']} 起同步新留资")

    interval = config["sync"]["interval_minutes"] * 60
    allowed_types = config["sync"]["lead_type_filter"]
    storage_path = _storage_state_path(config)

    # ---- P0: 浏览器崩溃自动恢复（外层循环） ----
    recovery_count = 0
    max_recoveries = 10  # 连续崩溃上限，超过则退出避免死循环

    while True:
        try:
            with sync_playwright() as p:
                page, ctx, cleanup = _launch_browser(p, config, logger)
                recovery_count = 0  # 成功启动后重置计数
                try:
                    _daemon_loop(page, client, state, state_file, logger,
                                 config, interval, allowed_types, storage_path)
                finally:
                    try:
                        cleanup()
                    except Exception:
                        pass
        except _BrowserRestartNeeded as e:
            recovery_count += 1
            if recovery_count > max_recoveries:
                logger.error(f"❌ 浏览器连续崩溃 {max_recoveries} 次，退出守护进程")
                logger.error("💡 请检查浏览器环境，运行 --setup 重新登录")
                break
            wait_sec = min(5 * recovery_count, 30)  # 递增等待：5s, 10s, 15s... 最多30s
            logger.warning(f"⚠️ 浏览器崩溃: {e}")
            logger.warning(f"🔄 第 {recovery_count} 次恢复，{wait_sec}秒后重启浏览器...")
            time.sleep(wait_sec)
        except KeyboardInterrupt:
            logger.info("收到退出信号，守护进程停止")
            break
        except Exception as e:
            logger.error(f"❌ 不可恢复的错误: {e}")
            error_handler.log_error_with_reference(e, "守护进程异常")
            break

    pid_lock.release()
    logger.info("=== 守护进程已退出 ===")


def _daemon_loop(page, client: dfc_client.DfcClient, state, state_file,
                 logger, config, interval, allowed_types, storage_path=None):
    """守护进程核心循环（P1: 浏览器健康检查 + 登录态处理）。"""
    follower_mapping = config.get("dfc", {}).get("follower_mapping", {})
    consecutive_errors = 0

    while True:
        # ---- P1: 浏览器健康检查 ----
        if not _is_browser_alive(page):
            raise _BrowserRestartNeeded("浏览器页面已关闭（健康检查未通过）")

        try:
            # token 可能过期，每轮重取
            token = auth.get_token()
            client.token = token

            logger.info(f"开始抓取巨懂车客户列表 (since={state['last_sync_time']})...")
            leads = jvdc_scraper.fetch_new_leads(
                page, config["jvdc"]["list_url"],
                since=state["last_sync_time"], allowed_types=allowed_types,
            )
            logger.info(f"抓取到 {len(leads)} 条新客户记录")
            result = process_leads(leads, client, state, follower_mapping=follower_mapping)
            state_mod.save_state(state_file, state)
            logger.info(f"同步完成: 新增{result['synced']} 跳过{result['skipped']} 失败{result['failed']}")
            consecutive_errors = 0  # 成功一轮后重置

        except jvdc_scraper.BrowserLoginExpired:
            # ---- P1: 登录态过期处理 ----
            logger.warning("=" * 50)
            logger.warning("🔴 巨懂车登录态过期！")
            logger.warning("🔴 请在浏览器中重新登录巨懂车平台")
            logger.warning("🔴 如使用 headless 模式，请重新运行: python scripts/sync_daemon.py --setup")
            logger.warning("=" * 50)
            error_handler.handle_error(
                "浏览器抓取时: 巨懂车登录态过期，请在浏览器中重新登录"
            )
            # 尝试等待重新登录
            try:
                _navigate_reliable(page, config["jvdc"]["login_url"], timeout_ms=30000)
            except Exception:
                pass
            deadline = time.time() + 600
            relogged = False
            while time.time() < deadline:
                time.sleep(5)
                # 健康检查
                if not _is_browser_alive(page):
                    raise _BrowserRestartNeeded("等待重新登录时浏览器崩溃")
                try:
                    _navigate_reliable(page, config["jvdc"]["list_url"], timeout_ms=15000)
                except Exception:
                    continue
                if "login" not in page.url:
                    if storage_path:
                        try:
                            ctx = page.context
                            ctx.storage_state(path=storage_path)
                        except Exception:
                            pass
                    logger.info("✅ 检测到已重新登录，继续同步")
                    relogged = True
                    break
            if not relogged:
                logger.warning("⚠️ 等待登录超时（10分钟），下一轮重试")

        except dfc_client.DfcApiError as e:
            # ---- P2: 错误分类（不可恢复） ----
            if e.kind == "auth":
                logger.error(f"🔴 大风车 Token 过期: {e.message}")
                logger.error("💡 请检查 APP_KEY 环境变量是否有效")
                error_handler.handle_error(
                    f"API 调用时: 大风车 Token 过期: {e.message}"
                )
            else:
                logger.error(f"❌ 大风车 API 异常: {e.message}")
                error_handler.handle_error(
                    f"API 调用时: 大风车 API 异常: {e.message}"
                )

        except Exception as e:
            # ---- P0/P2: 浏览器崩溃检测 + 错误分类 ----
            if _is_browser_crash_error(e):
                raise _BrowserRestartNeeded(str(e))
            if _is_recoverable_error(e):
                consecutive_errors += 1
                logger.warning(f"⚠️ 可恢复错误（第{consecutive_errors}次）: {e}")
                if consecutive_errors >= 5:
                    raise _BrowserRestartNeeded(f"连续 {consecutive_errors} 次可恢复错误")
                error_handler.log_error_with_reference(e, "同步异常")
            else:
                logger.error(f"❌ 不可恢复错误: {e}")
                error_handler.log_error_with_reference(e, "同步异常")

        time.sleep(interval)


def run_status(config):
    state_file = Path(config["state_file"]).expanduser()
    state = state_mod.load_state(state_file)
    print(f"上次同步时间: {state['last_sync_time']}")
    print(f"已同步手机号数: {len(state['synced_phones'])}")
    print(f"统计: {json.dumps(state.get('stats', {}), ensure_ascii=False)}")


def run_reset(config):
    state_file = Path(config["state_file"]).expanduser()
    state = state_mod.load_state(state_file)
    state["last_sync_time"] = None
    state_mod.save_state(state_file, state)
    print("✅ 已重置同步起点（下次启动重新记录）")


def run_check(config):
    """运行前自检：检查巨懂车和大风车的登录态。"""
    print("=== 同步自检 ===\n")

    print("1. 检查大风车 APP_KEY...")
    try:
        token = auth.get_token()
        account = auth.get_account_info(token)
        print(f"   ✅ 门店: {account['shopName']} ({account['shopCode']})")
        print(f"   ✅ Token 有效（读写操作均可用）")
    except Exception as e:
        print(f"   ❌ {e}")

    print("\n2. 检查巨懂车浏览器...")
    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
    if Path(user_data_dir).exists():
        print(f"   ✅ 浏览器数据目录存在: {user_data_dir}")
    else:
        print(f"   ❌ 浏览器数据目录不存在，请先运行 --setup")

    print("\n3. 检查巨懂车登录态...")
    storage_path = _storage_state_path(config)
    if Path(storage_path).exists():
        try:
            storage_data = json.loads(Path(storage_path).read_text(encoding="utf-8"))
            cookies_count = len(storage_data.get("cookies", []))
            print(f"   ✅ storage_state 存在 ({cookies_count} cookies)")
        except Exception as e:
            print(f"   ⚠️ storage_state 读取失败: {e}")
    else:
        print(f"   ❌ storage_state 不存在，请先运行 --setup")

    # P0: 检查是否有其他实例在运行
    print("\n4. 检查守护进程...")
    pid_lock = PidLock(_pid_file_path(config))
    running_pid = pid_lock.is_running()
    if running_pid:
        print(f"   ⚠️ 守护进程正在运行 (PID: {running_pid})")
    else:
        print(f"   ✅ 无守护进程在运行")

    print()


def check_runtime(config, require_app_key: bool = False) -> list:
    """检查运行时条件，返回问题列表（空列表表示全部通过）。"""
    issues = []
    if require_app_key:
        app_key_env = config.get("dfc", {}).get("app_key_env", "APP_KEY")
        if not os.environ.get(app_key_env):
            issues.append(f"缺少环境变量: {app_key_env}")
    user_data_dir = config.get("browser", {}).get("user_data_dir", "")
    if user_data_dir:
        user_data_path = Path(user_data_dir).expanduser()
        if not user_data_path.exists():
            issues.append(f"浏览器数据目录不存在: {user_data_path}")
    try:
        import playwright
    except ImportError:
        issues.append("缺少 playwright 模块，请运行: pip install playwright")
    chrome_binary = platform_utils.find_chrome_binary()
    if not chrome_binary:
        issues.append("未找到 Chrome 浏览器，请运行: playwright install chromium")
    return issues


def main():
    ap = argparse.ArgumentParser(description="巨懂车客户同步大风车守护进程")
    ap.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "config" / "config.json"))
    ap.add_argument("--setup", action="store_true", help="首次登录巨懂车")
    ap.add_argument("--status", action="store_true", help="查看同步状态")
    ap.add_argument("--reset", action="store_true", help="重置同步起点")
    ap.add_argument("--check", action="store_true", help="运行前自检")
    args = ap.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        print(f"💡 请复制模板: cp config/config.example.json config/config.json")
        sys.exit(1)

    config = load_config(config_path)

    if args.setup:
        run_setup(config)
    elif args.status:
        run_status(config)
    elif args.reset:
        run_reset(config)
    elif args.check:
        run_check(config)
    else:
        run_daemon(config)


if __name__ == "__main__":
    main()