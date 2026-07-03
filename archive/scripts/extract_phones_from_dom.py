#!/usr/bin/env python3
"""直接从 DOM 提取完整手机号。"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_daemon
from playwright.sync_api import sync_playwright


def main():
    config = sync_daemon.load_config(ROOT / "config" / "config.json")
    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
    storage_path = sync_daemon._storage_state_path(config)

    print("启动 Chrome CDP...")
    sync_daemon._start_chrome_cdp(user_data_dir, port=9222, timeout_sec=30)

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()

        if Path(storage_path).exists():
            storage_data = json.loads(Path(storage_path).read_text(encoding="utf-8"))
            if "cookies" in storage_data:
                ctx.add_cookies(storage_data["cookies"])
                print(f"✅ 已加载 {len(storage_data['cookies'])} 个 cookies")

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        list_url = config["jvdc"]["list_url"]
        print(f"\n导航到：{list_url}")
        sync_daemon._navigate_reliable(page, list_url, timeout_ms=30000)

        try:
            page.wait_for_selector('table tbody tr', timeout=20000)
            print("✅ 表格已加载")
        except:
            print("⚠️ 表格加载超时")
            return

        page.wait_for_timeout(3000)

        # 从 DOM 提取所有客户数据
        customers = page.evaluate("""
            () => {
                const rows = document.querySelectorAll('table tbody tr');
                const results = [];
                
                for (const row of rows) {
                    const text = row.innerText;
                    const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
                    
                    // 提取客户ID（第一行数字）
                    let customerId = null;
                    for (const line of lines) {
                        if (/^\\d+$/.test(line)) {
                            customerId = line;
                            break;
                        }
                    }
                    
                    // 提取手机号
                    let phone = null;
                    for (const line of lines) {
                        if (line.includes('手机')) {
                            // 找下一行
                            const idx = lines.indexOf(line);
                            if (idx + 1 < lines.length) {
                                const nextLine = lines[idx + 1];
                                const match = nextLine.match(/(1\\d{10})/);
                                if (match) {
                                    phone = match[1];
                                }
                            }
                            break;
                        }
                    }
                    
                    // 提取客户名称（客户ID后面的行）
                    let name = null;
                    if (customerId) {
                        const idIdx = lines.indexOf(customerId);
                        // 跳过 "-" 行
                        for (let i = idIdx + 1; i < lines.length; i++) {
                            if (lines[i] !== '-' && !lines[i].includes('手机')) {
                                name = lines[i];
                                break;
                            }
                            if (lines[i].includes('手机')) break;
                        }
                    }
                    
                    if (phone) {
                        results.push({
                            customer_id: customerId,
                            name: name,
                            phone: phone,
                            is_masked: phone.includes('*')
                        });
                    }
                }
                
                return results;
            }
        """)

        print(f"\n=== 提取到 {len(customers)} 个客户 ===")
        full_phones = []
        masked_phones = []
        
        for i, c in enumerate(customers):
            status = "✅ 完整" if not c['is_masked'] else "⚠️ 脱敏"
            print(f"\n[{i+1}] {status}")
            print(f"    客户ID: {c['customer_id']}")
            print(f"    姓名: {c['name']}")
            print(f"    手机: {c['phone']}")
            
            if not c['is_masked']:
                full_phones.append(c)
            else:
                masked_phones.append(c)

        print(f"\n=== 统计 ===")
        print(f"完整手机号：{len(full_phones)} 个")
        print(f"脱敏手机号：{len(masked_phones)} 个")

        # 保存到文件
        with open('/tmp/jvdc_customers.json', 'w') as f:
            json.dump({
                'full_phones': full_phones,
                'masked_phones': masked_phones,
                'all': customers
            }, f, ensure_ascii=False, indent=2)
        print(f"\n客户数据已保存到 /tmp/jvdc_customers.json")


if __name__ == "__main__":
    main()
