# 字段映射明细

## 巨懂车 → 大风车

| 巨懂车字段 | 大风车 code | 映射逻辑 |
|-----------|------------|---------|
| 手机号 | customer_field_phone | 直接取，去重键 |
| 客户姓名 | customer_field_name | 为"-"则不传 |
| 最新来源渠道 | customer_field_source | mapping.map_source() 映射为中文名 |
| 客户级别 | customer_field_grade | H/A/B/C/N，为空时按状态推断 |
| 客户状态 | （级别为空时备用） | 未联系→C 跟进中→B 已成交→A |
| 意向车型 | customer_field_intent | "巨懂车留资：xxx" |

## 自动填充

| 大风车 code | 值 | 来源 |
|------------|-----|------|
| customer_field_shop_code | APP_KEY 门店 | auth.get_account_info |
| customer_field_owner | 自动匹配（巨懂车跟进人 → 大风车销售，失败回退 owner_id） | sync_daemon 启动时自动映射 |
| customer_field_gender | 未知 | 默认（或从巨懂车映射） |
| customer_field_is_important | 否 | 默认 |
| customer_field_create_type | PC-主动创建 | 必填，固定值 |

## 来源映射（mapping.map_source）

| 巨懂车来源 | 大风车 source 中文名 |
|-----------|-------------------|
| 懂车帝-店铺车源 | 其他 |
| 抖音 | 抖音 |
| 微信 | 微信 |
| 电话 | 电话 |
| 直接到店 | 直接到店 |
| 微店 | 微店 |
| 二手车之家 | 二手车之家 |
| 朋友、老客户介绍 | 朋友、老客户介绍 |
| 表单线索 | 其他 |
| 话单线索 | 其他 |
| 私信线索 | 其他 |
| 客户留资 | 其他 |

## 完整枚举字典

与 `dfc-create-customer` 技能的 `crm.py` 完全对齐，见 `scripts/mapping.py`：

- `SOURCE`：客户来源（中文名 → CRM code）
- `GRADE`：意向等级（H/A/B/C/N → CRM code）
- `GENDER`：性别（先生/女士/未知 → CRM code）
- `IMPORTANT`：重点客户（是/否 → CRM code）

## 认证架构

- **读操作**（查重）：APP_KEY → Souche-Security-Token header → queryFindViewRecordPageInfo.json
- **写操作**（新增）：APP_KEY → Souche-Security-Token header → saveCustomer.json

所有操作均使用 APP_KEY Token 认证，不再需要浏览器 Cookie。
