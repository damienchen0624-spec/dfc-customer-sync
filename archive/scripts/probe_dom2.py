#!/usr/bin/env python3
"""深度探查巨懂车客户列表 DOM（处理动态加载/iframe/SPA）。"""

import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config.json"
DUMP_PATH = Path(__file__).resolve().parents[1] / "dom_dump2.html"


def main():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    list_url = cfg["jvdc"]["list_url"]
    user_data_dir = str(Path(cfg["browser"]["user_data_dir"]).expanduser())

    print(f"🌐 启动浏览器")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(user_data_dir, headless=False)
        page = ctx.pages[0]

        # 监听网络请求，找客户数据 API
        api_calls = []
        def on_response(resp):
            url = resp.url
            if any(k in url.lower() for k in ["customer", "lead", "clue", "list", "profile"]):
                if "autoengine" in url or "api" in url:
                    api_calls.append((resp.status, url[:150]))
        page.on("response", on_response)

        print(f"📋 打开客户列表: {list_url}")
        page.goto(list_url, wait_until="domcontentloaded", timeout=30000)

        # 等列表加载——轮询直到出现手机号或超时
        print("⏳ 等待客户数据加载（最多 30 秒）...")
        deadline = time.time() + 30
        found_phones = []
        while time.time() < deadline:
            content = page.content()
            import re
            found_phones = re.findall(r'1\d{10}', content)
            if found_phones:
                print(f"✅ 发现 {len(found_phones)} 个手机号")
                break
            time.sleep(2)

        # 存 HTML
        html = page.content()
        DUMP_PATH.write_text(html, encoding="utf-8")
        print(f"\n💾 整页 HTML: {DUMP_PATH} ({len(html)} 字符)")

        # 检查 iframe
        frames = page.frames
        print(f"\n🖼️ Frame 数量: {len(frames)}")
        for f in frames:
            print(f"   {f.url[:100]}")

        # 打印 API 调用
        print(f"\n🌐 客户相关 API 调用 ({len(api_calls)} 个):")
        for status, url in api_calls[:15]:
            print(f"   [{status}] {url}")

        # 找手机号所在的容器
        if found_phones:
            import re
            m = re.search(r'1\d{10}', html)
            if m:
                start = max(0, m.start() - 800)
                snippet = html[start:m.start()+100]
                print(f"\n📋 手机号 {m.group()} 的容器 HTML（前 800 字符）:\n")
                print(snippet[-800:])

        print("\n🔍 浏览器保持打开。按回车关闭...")
        try:
            input()
        except EOFError:
            time.sleep(30)
        ctx.close()


if __name__ == "__main__":
    main()
