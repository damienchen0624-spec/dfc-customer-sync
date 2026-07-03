#!/usr/bin/env python3
"""深度探查巨懂车客户列表（等用户登录后抓取）。

流程：
1. 打开客户列表 URL（未登录会跳转到登录页）
2. 每 5 秒检测一次：URL 是否已离开 /login/（说明用户登录成功）
3. 登录后自动跳回客户列表，等待数据加载（检测手机号出现）
4. 抓取整页 HTML + 第一行客户结构 + 监听到的客户 API
"""

import json
import re
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.json"
DUMP_PATH = ROOT / "dom_dump3.html"
RESULT_PATH = ROOT / "probe_result.txt"


def main():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    list_url = cfg["jvdc"]["list_url"]
    user_data_dir = str(Path(cfg["browser"]["user_data_dir"]).expanduser())

    print(f"🌐 启动浏览器", flush=True)
    print(f"📋 客户列表: {list_url}", flush=True)
    print("=" * 50, flush=True)
    print("⚠️  如果浏览器跳到登录页，请在浏览器窗口里登录巨懂车。", flush=True)
    print("    脚本会自动检测登录完成，最多等 5 分钟。", flush=True)
    print("=" * 50, flush=True)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(user_data_dir, headless=False)
        page = ctx.pages[0]

        api_calls = []
        def on_response(resp):
            url = resp.url
            if any(k in url.lower() for k in ["customer", "member", "lead", "clue", "profile"]):
                if resp.request.method in ("GET", "POST"):
                    api_calls.append((resp.status, resp.request.method, url[:200]))
        page.on("response", on_response)

        # 打开客户列表
        page.goto(list_url, wait_until="domcontentloaded", timeout=30000)

        # 阶段1：等登录（URL 离开 /login/）
        print("\n[阶段1] 等待登录...", flush=True)
        deadline = time.time() + 300
        logged_in = False
        while time.time() < deadline:
            current = page.url
            if "/login/" not in current and "customer" in current:
                logged_in = True
                print(f"✅ 登录成功: {current}", flush=True)
                break
            time.sleep(5)
            print(f"   当前: {current[:80]} (请在浏览器登录)", flush=True)

        if not logged_in:
            print("❌ 5 分钟未登录，退出", flush=True)
            ctx.close()
            sys.exit(1)

        # 阶段2：等数据加载（手机号出现）
        print("\n[阶段2] 等待客户数据加载...", flush=True)
        deadline = time.time() + 40
        found_phones = []
        while time.time() < deadline:
            content = page.content()
            found_phones = re.findall(r'1\d{10}', content)
            if found_phones:
                print(f"✅ 发现 {len(found_phones)} 个手机号", flush=True)
                break
            time.sleep(2)

        # 存 HTML
        html = page.content()
        DUMP_PATH.write_text(html, encoding="utf-8")
        print(f"\n💾 整页 HTML: {DUMP_PATH} ({len(html)} 字符)", flush=True)

        # 收集结果
        result = []
        result.append(f"手机号数量: {len(found_phones)}")
        result.append(f"前 5 个手机号: {found_phones[:5]}")
        result.append(f"\nFrame 数量: {len(page.frames)}")
        for f in page.frames:
            result.append(f"  {f.url[:120]}")

        result.append(f"\n客户相关 API 调用 ({len(api_calls)} 个):")
        for status, method, url in api_calls[:20]:
            result.append(f"  [{status}] {method} {url}")

        # 找手机号容器
        if found_phones:
            m = re.search(r'1\d{10}', html)
            if m:
                start = max(0, m.start() - 600)
                snippet = html[start:m.start()+50]
                result.append(f"\n手机号 {m.group()} 的容器 HTML（截取）:")
                result.append(snippet[-600:])

                # 提取该片段的 class
                classes = re.findall(r'class="([^"]+)"', snippet)
                result.append(f"\n该片段的 class 列表:")
                for c in classes[-10:]:
                    result.append(f"  .{c[:80]}")

        RESULT_PATH.write_text("\n".join(result), encoding="utf-8")
        print(f"\n📝 结果已存: {RESULT_PATH}", flush=True)
        print("\n" + "=" * 50, flush=True)
        print("✅ 探查完成，浏览器保持打开 60 秒供查看", flush=True)
        time.sleep(60)
        ctx.close()


if __name__ == "__main__":
    main()
