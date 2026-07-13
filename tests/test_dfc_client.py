#!/usr/bin/env python3
"""大风车客户读写的离线单测（mock HTTP）。"""

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dfc_client  # noqa: E402


class PhoneExistsTest(unittest.TestCase):
    def test_phone_exists_true_when_record_found(self):
        fake_resp = {
            "code": "200",
            "data": {
                "common": {
                    "records": [
                        {"fields": [{"code": "customer_field_phone", "value": "17631845820"}]}
                    ]
                }
            }
        }
        with mock.patch.object(dfc_client, "_http_post", return_value=fake_resp):
            client = dfc_client.DfcClient(token="t", shop_code="04848498", shop_name="测试门店")
            self.assertTrue(client.phone_exists("17631845820"))

    def test_phone_exists_false_when_no_record(self):
        fake_resp = {"code": "200", "data": {"common": {"records": []}}}
        with mock.patch.object(dfc_client, "_http_post", return_value=fake_resp):
            client = dfc_client.DfcClient(token="t", shop_code="04848498", shop_name="测试门店")
            self.assertFalse(client.phone_exists("00000000000"))


class AddCustomerTest(unittest.TestCase):
    def test_add_customer_success(self):
        fake_resp = {
            "code": "200",
            "success": True,
            "data": {"customerId": "record_123"}
        }
        with mock.patch.object(dfc_client, "_http_post", return_value=fake_resp) as m:
            client = dfc_client.DfcClient(token="t", shop_code="04848498", shop_name="测试门店")
            lead = {"phone": "13900139001", "name": "张三", "source": "抖音", "grade": "A", "status": ""}
            result = client.add_customer(lead)
            self.assertTrue(result["ok"])
            self.assertEqual(result["customer_id"], "record_123")
            # 验证调用了 saveCustomer.json
            called_url = m.call_args[0][0]
            self.assertIn("saveCustomer.json", called_url)

    def test_add_customer_returns_error_on_failure(self):
        with mock.patch.object(
            dfc_client, "_http_post",
            side_effect=dfc_client.DfcApiError("登录超时", kind="auth")
        ):
            client = dfc_client.DfcClient(token="t", shop_code="04848498", shop_name="测试门店")
            lead = {"phone": "13900139001", "name": "", "source": "抖音", "grade": "A", "status": ""}
            result = client.add_customer(lead)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["kind"], "auth")

    def test_add_customer_returns_error_on_api_error(self):
        # _http_post 在 code != "200" 时 raise DfcApiError
        with mock.patch.object(
            dfc_client, "_http_post",
            side_effect=dfc_client.DfcApiError("服务器错误", kind="business")
        ):
            client = dfc_client.DfcClient(token="t", shop_code="04848498", shop_name="测试门店")
            lead = {"phone": "13900139001", "name": "", "source": "抖音", "grade": "A", "status": ""}
            result = client.add_customer(lead)
            self.assertFalse(result["ok"])


class PhoneExistsResultTest(unittest.TestCase):
    def test_phone_exists_result_returns_error_kind(self):
        with mock.patch.object(
            dfc_client, "_http_post",
            side_effect=dfc_client.DfcApiError("网络错误", kind="network")
        ):
            client = dfc_client.DfcClient(token="t", shop_code="04848498", shop_name="测试门店")
            result = client.phone_exists_result("17631845820")
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["kind"], "network")


class BuildFieldsTest(unittest.TestCase):
    def test_build_fields_includes_required(self):
        data = {
            "phone": "17631845820",
            "name": "张三",
            "source": "其他",
            "grade": "H",
            "gender": "未知",
            "is_important": "否",
            "shop": {"recordId": "04848498", "recordDisplay": "测试门店"},
        }
        fields = dfc_client.build_fields(data)
        codes = {f["code"] for f in fields}
        self.assertIn("customer_field_phone", codes)
        self.assertIn("customer_field_shop_code", codes)
        self.assertIn("customer_field_source", codes)
        self.assertIn("customer_field_grade", codes)
        self.assertIn("customer_field_gender", codes)
        self.assertIn("customer_field_is_important", codes)
        self.assertIn("customer_field_create_type", codes)

    def test_build_fields_omits_empty_name(self):
        data = {
            "phone": "13900139001",
            "source": "抖音",
            "grade": "A",
            "shop": {"recordId": "04848498", "recordDisplay": "测试门店"},
        }
        fields = dfc_client.build_fields(data)
        codes = {f["code"] for f in fields}
        self.assertNotIn("customer_field_name", codes)

    def test_build_fields_includes_intent(self):
        data = {
            "phone": "13900139001",
            "intent": "巨懂车留资：宝马3系",
            "shop": {"recordId": "04848498", "recordDisplay": "测试门店"},
        }
        fields = dfc_client.build_fields(data)
        by_code = {f["code"]: f for f in fields}
        self.assertIn("customer_field_intent", by_code)
        self.assertEqual(by_code["customer_field_intent"]["content"], "巨懂车留资：宝马3系")


if __name__ == "__main__":
    unittest.main()
