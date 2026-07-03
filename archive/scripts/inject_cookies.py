#!/usr/bin/env python3
"""通过 CDP 注入 cookies 到已运行的 Chrome，保存 storage_state。"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sync_daemon

config = sync_daemon.load_config(ROOT / "config" / "config.json")


def iso_to_ts(iso_str: str) -> float:
    """ISO 8601 → Unix timestamp (seconds)."""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.timestamp()


COOKIES_RAW = """n_mh	r5kaVVYv6H_eYC30UKidtnPV6YCqxWLQiPgsQo8a4oM	.autoengine.com	/	2026-10-27T09:10:59.715Z
odin_tt	e823badcff00d2c09d721ea655ac466e420a430f4ee2e91775ab12aca5cdec78c14a3a9332015dec20d64d9e4d745b02b5f6b642ef70a1c573878873d7b571ba	.autoengine.com	/	2027-06-29T09:11:01.645Z
passport_auth_status	b20036207c7feba0367677f65d30c078%2C	.autoengine.com	/	2026-07-29T09:10:59.715Z
passport_auth_status_ss	b20036207c7feba0367677f65d30c078%2C	.autoengine.com	/	2026-07-29T09:10:59.715Z
passport_csrf_token	f99c2061a4a9f775403617999344eed6	.autoengine.com	/	2026-08-23T05:50:21.358Z
passport_csrf_token_default	f99c2061a4a9f775403617999344eed6	.autoengine.com	/	2026-08-23T05:50:21.358Z
passport_mfa_token	CjYBZ7DwtyWSCzCChL19asABj%2FWpiBQOHWBZ0kJON6NOUrMXbOglDyMkUhtpKFkjFmjLiLqy%2BlMaSgo8AAAAAAAAAAAAAFCZUk2Ur1hgPrJT4bj1xYK86bSSYAcwyfyCgpejENNtTP7ktR4F5GC4XRhMTDWErjSmEJu9lQ4Y9rHRbCACIgEDi7I7pA%3D%3D	.autoengine.com	/	2026-08-28T09:10:59.715Z
s_v_web_id	verify_mqrnmkvd_scONfwun_Dy2s_4mAE_Bdvj_4Rgowl2ysiwO	www.autoengine.com	/	2026-08-23T05:50:22.000Z
session_tlb_tag	sttt%7C19%7CTpsySnH1b7Z0qjxGVAq4T_________-tlC-4UV9MCn8Arr1BfZ7_XEQQlheZMKme58n0nLA4VSY%3D	.autoengine.com	/	2026-08-28T09:10:59.715Z
sessionid	4e9b324a71f56fb674aa3c46540ab84f	.autoengine.com	/	2026-08-28T09:10:59.715Z
sessionid_ss	4e9b324a71f56fb674aa3c46540ab84f	.autoengine.com	/	2026-08-28T09:10:59.715Z
sid_guard	4e9b324a71f56fb674aa3c46540ab84f%7C1782724259%7C5184000%7CFri%2C+28-Aug-2026+09%3A10%3A59+GMT	.autoengine.com	/	2027-06-24T09:10:59.715Z
sid_tt	4e9b324a71f56fb674aa3c46540ab84f	.autoengine.com	/	2026-08-28T09:10:59.715Z
sid_ucp_v1	1.0.0-KDAwMmRjYjY2ZjM4MDA0ZTc0YjRiNjdjMzQ2MGJmNmExZThhYWRiNjIKHwioysCbg4w1EKPtiNIGGIywEiAMMLzvjJAGOAJA8QcaAmxxIiA0ZTliMzI0YTcxZjU2ZmI2NzRhYTNjNDY1NDBhYjg0Zg	.autoengine.com	/	2026-08-28T09:10:59.716Z
ssid_ucp_v1	1.0.0-KDAwMmRjYjY2ZjM4MDA0ZTc0YjRiNjdjMzQ2MGJmNmExZThhYWRiNjIKHwioysCbg4w1EKPtiNIGGIywEiAMMLzvjJAGOAJA8QcaAmxxIiA0ZTliMzI0YTcxZjU2ZmI2NzRhYTNjNDY1NDBhYjg0Zg	.autoengine.com	/	2026-08-28T09:10:59.716Z
ttwid	1%7CU_WSFGHSj6Wlsy_Le22LPBdycpFGLA8IcVACrf2E5gM%7C1782712426%7C5e541e9ac465a0bfb022db98b9572f9bc71310f45d96c1cab22a26c7c49b6044	.autoengine.com	/	2027-06-29T05:53:44.156Z
uid_tt	4f885af13ead07ef47bb278dfd173378	.autoengine.com	/	2026-08-28T09:10:59.715Z
uid_tt_ss	4f885af13ead07ef47bb278dfd173378	.autoengine.com	/	2026-08-28T09:10:59.715Z"""


def parse_cookies() -> list[dict]:
    cookies = []
    for line in COOKIES_RAW.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        name, value, domain, path, expires_iso = parts[0], parts[1], parts[2], parts[3], parts[4]
        cookies.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": path,
            "expires": iso_to_ts(expires_iso),
            "httpOnly": False,
            "secure": False,
            "sameSite": "Lax",
        })
    return cookies


def main():
    cookies = parse_cookies()
    print(f"解析到 {len(cookies)} 个 cookies")

    storage_path = sync_daemon._storage_state_path(config)
    Path(storage_path).parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # 注入 cookies
        ctx.add_cookies(cookies)
        print(f"✅ 已注入 {len(cookies)} 个 cookies")

        # 导航到客户列表页验证登录
        list_url = config["jvdc"]["list_url"]
        print(f"导航到: {list_url}")
        sync_daemon._navigate_reliable(page, list_url, timeout_ms=30000)

        current_url = page.url or ""
        print(f"当前 URL: {current_url}")

        if "login" not in current_url:
            # 登录成功，保存 storage_state
            ctx.storage_state(path=storage_path)
            print(f"✅ 登录成功！storage_state 已保存到: {storage_path}")
        else:
            print("❌ 仍在登录页，cookies 可能已过期")
            sys.exit(1)


if __name__ == "__main__":
    main()
