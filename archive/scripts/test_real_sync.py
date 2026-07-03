#!/usr/bin/env python3
"""从巨懂车页面提取完整手机号并测试同步到大风车。"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auth
from dfc_client import DfcClient
import mapping
import sync_daemon
from playwright.sync_api import sync_playwright


def extract_phone_from_task_id(task_id):
    """从 data-feelgood-task-id 中提取手机号。
    
    格式示例: 7324221737971744795
    推测结构: 前缀(7位) + 手机号(11位) + 后缀
    """
    if not task_id or len(task_id) < 18:
        return None
    
    # 尝试提取中间的11位数字作为手机号
    match = re.search(r'(\d{7})(1[3-9]\d{9})(\d+)', task_id)
    if match:
        return match.group(2)
    return None


def main():
    config = sync_daemon.load_config(ROOT / "config" / "config.json")
    user_data_dir = str(Path(config["browser"]["user_data_dir"]).expanduser())
    storage_path = sync_daemon._storage_state_path(config)

    print("启动 Chrome CDP...")
    sync_daemon._start_chrome_cdp(user_data_dir, port=9222, timeout_sec=30)

    customers = []

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()

        # 加载 cookies
        if Path(storage_path).exists():
            storage_data = json.loads(Path(storage_path).read_text(encoding="utf-8"))
            if "cookies" in storage_data:
                ctx.add_cookies(storage_data["cookies"])
                print(f"✅ 已加载 {len(storage_data['cookies'])} 个 cookies")

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        list_url = config["jvdc"]["list_url"]
        print(f"导航到: {list_url}")
        sync_daemon._navigate_reliable(page, list_url, timeout_ms=30000)

        print(f"当前 URL: {page.url}")
        
        # 等待表格加载
        print("等待表格加载...")
        try:
            page.wait_for_selector('table.arco-table tbody tr', timeout=20000)
            print("✅ 表格已加载")
        except:
            print("⚠️ 表格加载超时，尝试继续...")
        
        page.wait_for_timeout(3000)

        # 提取表格行数据
        print("\n=== 提取客户数据 ===")
        rows = page.query_selector_all('table.arco-table tbody tr')
        print(f"找到 {len(rows)} 行数据")

        for i, row in enumerate(rows[:3]):  # 只处理前3条
            try:
                # 获取 data-feelgood-task-id
                task_id_el = row.query_selector('[data-feelgood-task-id]')
                task_id = task_id_el.get_attribute('data-feelgood-task-id') if task_id_el else None
                
                # 提取手机号
                phone = extract_phone_from_task_id(task_id)
                
                # 获取其他字段
                cells = row.query_selector_all('td')
                
                # 客户名称
                name_el = row.query_selector('.name-_8a513 .value-ee2e69')
                customer_name = name_el.inner_text().strip() if name_el else None
                
                # 关注车型
                car_name_el = row.query_selector('.name-c1cf67 .arco-typography')
                car_name = car_name_el.inner_text().strip() if car_name_el else None
                
                # 留资时间
                time_el = cells[4].query_selector('span') if len(cells) > 4 else None
                create_time_str = time_el.inner_text().strip() if time_el else None
                
                if phone:
                    customer = {
                        'name': customer_name,
                        'phone': phone,
                        'intent_model': car_name,
                        'create_time': create_time_str,
                        'task_id': task_id
                    }
                    customers.append(customer)
                    print(f"  [{i+1}] {customer_name} | {phone} | {car_name[:20]}... | {create_time_str}")
                else:
                    print(f"  [{i+1}] 无法提取手机号，task_id={task_id}")
                    
            except Exception as e:
                print(f"  [{i+1}] 提取失败: {e}")

        print(f"\n成功提取 {len(customers)} 条客户数据")

    if not customers:
        print("❌ 没有提取到客户数据")
        return

    # 选择第一条进行测试同步
    test_customer = customers[0]
    print(f"\n=== 测试同步第一条客户到大风车 ===")
    print(f"客户: {test_customer['name']}")
    print(f"手机: {test_customer['phone']}")
    print(f"车型: {test_customer['intent_model']}")
    print(f"时间: {test_customer['create_time']}")

    # 获取大风车认证
    print("\n=== 获取大风车认证 ===")
    token = auth.get_token()
    print(f"✅ Token: {token[:30]}...")
    
    account = auth.get_account_info(token)
    shop_code = account["shopCode"]
    print(f"✅ 门店: {account['shopName']} ({shop_code})")

    # 构造 lead 数据
    lead = {
        'name': test_customer['name'],
        'phone': test_customer['phone'],
        'intent_model': test_customer['intent_model'],
        'source': '懂车帝平台',
        'grade': 'C',
        'status': ''
    }

    # 映射到大风车字段
    dfc_data = mapping.build_dfc_fields(lead, shop_code)
    
    print(f"\n=== 映射后的大风车数据 ===")
    print(json.dumps(dfc_data, ensure_ascii=False, indent=2))

    # 调用大风车 API
    print(f"\n=== 调用大风车 API ===")
    client = DfcClient(token=token, shop_code=shop_code)

    try:
        result = client.add_customer_result(lead)
        print(f"同步结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
        
        # 检查手机号是否已存在
        print(f"\n=== 检查手机号是否已存在于大风车 ===")
        exists_result = client.phone_exists_result(test_customer['phone'])
        print(f"检查结果: {json.dumps(exists_result, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"❌ 同步失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
