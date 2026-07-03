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

v3.0 重构：
  - 大风车 CRM 操作统一到 dfc_client.DfcClient
  - 读操作（查重）和写操作（新增）均使用 APP_KEY Token
  - 字段构建与 dfc-create-customer 技能完全对齐
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import auth
import dfc_client
import jvdc_scraper
import state as state_mod
import platform_utils


def load_config(path: Path) -> dict:
    """加载配置文件，自动替换 <APP_DATA> 占位符为跨平台的应用数据目录。"""
    config_text = Path(path).expanduser().read_text(encoding="utf-8")
    # 替换 <APP_DATA> 占位符为跨平台的应用数据目录
    app_data = str(platform_utils.get_app_data_dir())
    config_text = config_text.replace("<APP_DATA>", app_data)
    return json.loads(config_text)


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def log(msg: str, log_file: Path = None):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    if log_file:
        log_file = Path(log_file).expanduser()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def process_leads(leads, client: dfc_client.DfcClient, state) -> dict:
    """处理一批新客户：去重 → 写入 → 更新状态。返回计数。

    Args:
        leads: 巨懂车抓取的客户列表
        client: DfcClient（APP_KEY token，读写操作均使用）
        state: 同步状态
    """
    synced = skipped = failed = 0
    failed_times = []
    for lead in leads:
        phone = lead["phone"]
        if state_mod.is_synced(state, phone):
            skipped += 1
            continue
        # 直接写入（不去重大风车）
        # 用户要求：懂车帝有新留资全量写入，不管大风车内是否重复
        result = client.add_customer(lead)
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
    # 推进水位线：若有失败，停在最早失败记录的时间（保证失败的下轮重试）；
    # 否则推进到本批最新。配合 filter_new_leads 的 >= 比较，失败记录不会被漏掉。
    if leads:
        if failed_times:
            state["last_sync_time"] = min(failed_times)
        else:
            state["last_sync_time"] = max(l.get("leave_time", "") for l in leads)
    return {"synced": synced, "skipped": skipped, "failed": failed}


def _storage_state_path(config) -> str:
    """storage_state 文件路径，和 state_file 同目录。"""
    state_file = Path(config["state_file"]).expanduser()
    return str(state_file.parent / "jvdc_state.json")


def _navigate_reliable(page, url: str, timeout_ms: int = 30000, max_retries: int = 3):
    """可靠导航：networkidle + 空白页检测 + 自动重试。"""
    for attempt in range(1, max_retries + 1):
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        except Exception:
            # networkidle 超时也接受（SPA 可能持续有请求）
            pass
        # 检查是否空白页：body 文本过短视为未加载
        try:
            body_len = page.evaluate("document.body ? document.body.innerText.length : 0")
        except Exception:
            body_len = 0
        if body_len > 50:
            return  # 页面已正常加载
        log(f"⚠️ 页面加载不完整（第{attempt}次），重试...")
        time.sleep(2)
    # 最后一次不强求 networkidle
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)


def _start_chrome_cdp(user_data_dir: str, port: int = 9222, timeout_sec: int = 30):
    """启动 Chrome 并开启 CDP 调试端口，返回 (进程, CDP URL)。"""
    import urllib.request

    os.makedirs(user_data_dir, exist_ok=True)

    # 清理端口上的旧进程（跨平台）
    platform_utils.kill_process_on_port(port)
    time.sleep(1)

    # 查找 Chrome 二进制文件（跨平台）
    chrome_binary = platform_utils.find_chrome_binary()
    if not chrome_binary:
        raise RuntimeError("未找到 Chrome 浏览器，请先运行: playwright install chromium")

    log(f"启动 Chrome: {chrome_binary}")

    args = [
        chrome_binary,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--window-position=200,100",
        "--window-size=1280,800",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    # macOS 需要额外参数：不使用 Keychain，避免每次启动弹窗要求输入系统密码
    if platform_utils.get_os_type() == "macos":
        args.append("--password-store=basic")
    # Windows 需要额外的参数
    if platform_utils.get_os_type() == "windows":
        args.append("--disable-gpu-sandbox")
    subprocess.Popen(args)

    # 等待 CDP 就绪
    cdp_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        time.sleep(0.5)
        try:
            resp = urllib.request.urlopen(f"{cdp_url}/json/version", timeout=2)
            data = json.loads(resp.read())
            log(f"✅ Chrome CDP 就绪: {data.get('Browser', '?')}")
            return None, cdp_url
        except Exception:
            continue

    raise RuntimeError(f"Chrome CDP 端口 {port} 未就绪（{timeout_sec}秒超时）")


def run_setup(config):
    """首次登录巨懂车。"""
    from playwright.sync_api import sync_playwright

    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
    storage_path = _storage_state_path(config)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=["--no-sandbox", "--window-position=200,100", "--window-size=1280,800"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        _navigate_reliable(page, config["jvdc"]["login_url"], timeout_ms=60000)
        print(f"登录页已加载: {page.url}")

        print("等待登录完成（最多 5 分钟）...")
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
                        print("✅ 登录成功！登录态已保存")
                        print(f"✅ Cookie 已写入 profile: {user_data_dir}")
                        print(f"✅ storage_state 备份: {storage_path}")
                        print("你可以关闭浏览器窗口了。")
                        return
                except Exception:
                    pass
            else:
                try:
                    body_len = page.evaluate("document.body ? document.body.innerText.length : 0")
                    if body_len < 50:
                        log("⚠️ 登录页空白，重新加载...")
                        _navigate_reliable(page, config["jvdc"]["login_url"], timeout_ms=30000)
                except Exception:
                    pass

        print(" 登录超时（5分钟），请重试")


def run_daemon(config):
    """守护进程主循环。"""
    from playwright.sync_api import sync_playwright

    state_file = Path(config["state_file"]).expanduser()
    log_file = Path(config["log_file"]).expanduser()
    state = state_mod.load_state(state_file)

    # 大风车认证（APP_KEY token，读写都用）
    token = auth.get_token()
    account = auth.get_account_info(token)
    shop_code = account["shopCode"]
    shop_name = account["shopName"]
    owner_id = config.get("dfc", {}).get("owner_id", "")
    owner_name = config.get("dfc", {}).get("owner_name", "")

    # 统一客户端（读写均使用 APP_KEY Token）
    client = dfc_client.DfcClient(
        token=token,
        shop_code=shop_code,
        shop_name=shop_name,
        owner_id=owner_id,
        owner_name=owner_name,
    )
    log(f"大风车门店: {shop_name} ({shop_code})", log_file)
    log("✅ 大风车 Token 客户端已就绪（读写均使用 APP_KEY）", log_file)

    # 首次启动记录同步起点
    if not state["last_sync_time"]:
        state["last_sync_time"] = now_str()
        state_mod.save_state(state_file, state)
        log(f"首次启动，从 {state['last_sync_time']} 起同步新留资", log_file)

    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
    interval = config["sync"]["interval_minutes"] * 60
    allowed_types = config["sync"]["lead_type_filter"]

    headless = config["browser"]["headless"]
    storage_path = _storage_state_path(config)

    # 启动巨懂车浏览器（用于抓取客户列表）
    with sync_playwright() as p:
        try:
            if headless:
                ctx = p.chromium.launch_persistent_context(
                    user_data_dir, headless=False,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                if Path(storage_path).exists():
                    try:
                        storage_data = json.loads(Path(storage_path).read_text(encoding="utf-8"))
                        if "cookies" in storage_data:
                            ctx.add_cookies(storage_data["cookies"])
                            log(f"✅ 已加载 {len(storage_data['cookies'])} 个 cookies", log_file)
                    except Exception as e:
                        log(f"⚠️ 加载 storage_state 失败: {e}", log_file)
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                _daemon_loop(page, client, state, state_file, log_file, config, interval, allowed_types, storage_path)
            else:
                _, cdp_url = _start_chrome_cdp(user_data_dir)
                log(f"Chrome 已启动 (CDP: {cdp_url})", log_file)
                try:
                    browser = p.chromium.connect_over_cdp(cdp_url)
                    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
                    if Path(storage_path).exists():
                        try:
                            storage_data = json.loads(Path(storage_path).read_text(encoding="utf-8"))
                            if "cookies" in storage_data:
                                ctx.add_cookies(storage_data["cookies"])
                                log(f"✅ 已加载 {len(storage_data['cookies'])} 个 cookies", log_file)
                        except Exception as e:
                            log(f"⚠️ 加载 storage_state 失败: {e}", log_file)
                    page = ctx.pages[0] if ctx.pages else ctx.new_page()
                    _daemon_loop(page, client, state, state_file, log_file, config, interval, allowed_types, storage_path)
                finally:
                    log("Chrome 需手动关闭（二进制直接启动的）", log_file)
        finally:
            pass


def _daemon_loop(page, client: dfc_client.DfcClient, state, state_file, log_file, config, interval, allowed_types, storage_path=None):
    """守护进程核心循环。"""
    while True:
        try:
            # token 可能过期，每轮重取
            token = auth.get_token()
            client.token = token

            log(f"开始抓取巨懂车客户列表 (since={state['last_sync_time']})...", log_file)
            leads = jvdc_scraper.fetch_new_leads(
                page, config["jvdc"]["list_url"],
                since=state["last_sync_time"], allowed_types=allowed_types,
            )
            log(f"抓取到 {len(leads)} 条新客户记录", log_file)
            result = process_leads(leads, client, state)
            state_mod.save_state(state_file, state)
            log(f"同步完成: 新增{result['synced']} 跳过{result['skipped']} 失败{result['failed']}", log_file)
        except jvdc_scraper.BrowserLoginExpired:
            log("⚠️ 巨懂车登录态过期，请在浏览器中重新登录...", log_file)
            _navigate_reliable(page, config["jvdc"]["login_url"], timeout_ms=30000)
            deadline = time.time() + 600
            relogged = False
            while time.time() < deadline:
                time.sleep(5)
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
                    log("✅ 检测到已重新登录，继续同步", log_file)
                    relogged = True
                    break
            if not relogged:
                log("⚠️ 等待登录超时（10分钟），下一轮重试", log_file)
        except dfc_client.DfcApiError as e:
            if e.kind == "auth":
                log(f"⚠️ 大风车 Token 过期: {e.message}", log_file)
                log("请检查 APP_KEY 环境变量是否有效", log_file)
            else:
                log(f"❌ 大风车 API 异常: {e.message}", log_file)
        except Exception as e:
            log(f"❌ 同步异常: {e}", log_file)
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

    # 1. 检查 APP_KEY 和大风车 Token
    print("1. 检查大风车 APP_KEY...")
    try:
        token = auth.get_token()
        account = auth.get_account_info(token)
        print(f"   ✅ 门店: {account['shopName']} ({account['shopCode']})")
        print(f"   ✅ Token 有效（读写操作均可用）")
    except Exception as e:
        print(f"   ❌ {e}")

    # 2. 检查巨懂车登录态
    print("\n2. 检查巨懂车浏览器...")
    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
    if Path(user_data_dir).exists():
        print(f"   ✅ 浏览器数据目录存在: {user_data_dir}")
    else:
        print(f"   ❌ 浏览器数据目录不存在，请先运行 --setup")

    # 3. 检查 storage_state
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

    print()


def check_runtime(config, require_app_key: bool = False) -> list:
    """检查运行时条件，返回问题列表（空列表表示全部通过）。
    
    Args:
        config: 配置字典
        require_app_key: 是否要求 APP_KEY 环境变量已设置
    
    Returns:
        问题描述列表，空列表表示全部通过
    """
    issues = []
    
    # 检查 APP_KEY
    if require_app_key:
        app_key_env = config.get("dfc", {}).get("app_key_env", "APP_KEY")
        if not os.environ.get(app_key_env):
            issues.append(f"缺少环境变量: {app_key_env}")
    
    # 检查浏览器数据目录
    user_data_dir = config.get("browser", {}).get("user_data_dir", "")
    if user_data_dir:
        user_data_path = Path(user_data_dir).expanduser()
        if not user_data_path.exists():
            issues.append(f"浏览器数据目录不存在: {user_data_path}")
    
    # 检查 Playwright
    try:
        import playwright
    except ImportError:
        issues.append("缺少 playwright 模块，请运行: pip install playwright")
    
    # 检查 Chrome 浏览器
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

    config = load_config(args.config)

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
