#!/usr/bin/env python3
"""巨懂车 DOM 探查脚本。

打开持久化浏览器，等用户登录后，抓取客户列表第一行的真实 HTML，
用于校准 jvdc_scraper.py 的选择器。
"""

import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config.json"
DUMP_PATH = Path(__file__).resolve().parents[1] / "dom_dump.html"


def main():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    list_url = cfg["jvdc"]["list_url"]
    login_url = cfg["jvdc"]["login_url"]
    user_data_dir = str(Path(cfg["browser"]["user_data_dir"]).expanduser())

    print(f"🌐 启动浏览器（用户数据目录: {user_data_dir}）")
    print(f"📋 客户列表: {list_url}")
    print("请在浏览器中登录巨懂车，登录后脚本会自动检测并抓取 DOM...\n")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(user_data_dir, headless=False)
        page = ctx.pages[0]

        # 先尝试直接打开客户列表
        page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        # 检测是否已登录，最多等 5 分钟
        deadline = time.time() + 300
        logged_in = False
        while time.time() < deadline:
            if "login" not in page.url and "customer" in page.url:
                logged_in = True
                break
            print(f"⏳ 等待登录... (当前页: {page.url})")
            # 如果在登录页，主动跳过去方便用户操作
            if "login" in page.url:
                pass
            time.sleep(5)
            # 用户可能已登录，刷新看能否进列表
            try:
                page.goto(list_url, wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)
            except Exception:
                pass

        if not logged_in:
            print("❌ 5 分钟内未检测到登录，退出。")
            ctx.close()
            sys.exit(1)

        print(f"\n✅ 已登录，当前页: {page.url}")
        print("⏳ 等待列表完全加载（10 秒）...")
        time.sleep(10)

        # 抓取整页 HTML 存档
        html = page.content()
        DUMP_PATH.write_text(html, encoding="utf-8")
        print(f"\n💾 整页 HTML 已存: {DUMP_PATH} ({len(html)} 字符)")

        # 探查表格行
        rows = page.query_selector_all("table tbody tr")
        print(f"\n📊 table tbody tr 行数: {len(rows)}")

        # 如果没找到，试其他常见选择器
        if not rows:
            print("⚠️ table tbody tr 无结果，尝试其他容器...")
            for sel in [".ant-table-tbody tr", "[class*='row']", "[class*='item']", "tr"]:
                found = page.query_selector_all(sel)
                print(f"   {sel}: {len(found)} 个")

        # 打印第一行的 HTML（截断到 3000 字符）
        if rows:
            first = rows[0]
            inner = first.inner_html()
            print(f"\n📋 第一行 HTML（前 3000 字符）:\n")
            print(inner[:3000])

            # 打印第一行纯文本
            print(f"\n📋 第一行纯文本:\n")
            print(first.inner_text()[:1000])

        # 不自动关闭，让用户看完
        print("\n🔍 浏览器保持打开。看完后按回车关闭...")
        try:
            input()
        except EOFError:
            time.sleep(30)
        ctx.close()


if __name__ == "__main__":
    main()
