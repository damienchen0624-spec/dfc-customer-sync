---
name: dfc-customer-sync
description: >
  巨懂车客户自动同步到大风车。后台守护进程每 10 分钟从巨懂车后台抓取新留资客户,
  手机号去重后写入大风车客户列表。当用户说"同步巨懂车客户"、"巨懂车留资同步大风车"、
  "启动客户同步"时使用。
version: 3.1.1
author: Hermes Agent
license: MIT
---

# 巨懂车客户同步大风车 (dfc-customer-sync)

## Overview

后台守护进程,每 10 分钟自动把巨懂车后台的新留资客户同步到大风车客户列表。

- **巨懂车**:浏览器自动化抓取(Playwright,持久化登录态)
- **大风车读写操作**:APP_KEY 认证(Token),不再需要浏览器
- **跨平台支持**:macOS / Windows / Linux

## 跨平台支持

本技能支持以下操作系统:

| 系统 | 应用数据目录 |
|------|-------------|
| macOS | `~/Library/Application Support/大风车 AI 龙虾` |
| Windows | `%APPDATA%/大风车 AI 龙虾` |
| Linux | `~/.local/share/大风车 AI 龙虾` |

配置文件中的 `<APP_DATA>` 占位符会自动替换为对应系统的路径。

## 环境变量

- `APP_KEY`(必需)- 大风车认证,读写操作均使用 Token

## 项目结构

```
dfc-customer-sync/
├── config/                    # 配置文件
│   ├── config.json           # 运行时配置(自动生成)
│   └── config.example.json   # 配置模板
├── scripts/                   # 核心脚本
│   ├── sync_daemon.py        # 主守护进程
│   ├── auth.py               # 大风车认证模块
│   ├── dfc_client.py         # 大风车 CRM 客户端
│   ├── dfc_writer.py         # 兼容包装
│   ├── jvdc_scraper.py       # 巨懂车抓取器
│   ├── mapping.py            # 字段映射
│   ├── state.py              # 状态管理
│   ├── platform_utils.py     # 跨平台工具
│   ├── install_check.py      # 安装检查
│   ├── fix_keychain.py       # macOS 钥匙串修复
│   └── bootstrap.py          # 一键启动
├── tests/                     # 单元测试
├── archive/                   # 归档的调试/测试脚本
├── .env.example              # 环境变量模板
├── requirements.txt          # Python 依赖
└── SKILL.md                  # 本文档
```

## 首次使用

### 快速开始(推荐)

```bash
# 一键检查并启动(会自动检测并安装缺失的依赖)
python scripts/bootstrap.py
```

### 手动安装

```bash
# 1. 运行安装检查(检测并安装缺失的依赖)
python scripts/install_check.py

# 2. 复制配置(配置文件中的 <APP_DATA> 会自动替换为系统对应路径)
cp config/config.example.json config/config.json

# 3. 设置环境变量
cp .env.example .env
# 编辑 .env 文件,填入你的 APP_KEY

# 4. 首次登录巨懂车(打开浏览器手动登录)
python scripts/sync_daemon.py --setup

# 5. 运行自检
python scripts/sync_daemon.py --check

# 6. 启动守护进程
python scripts/sync_daemon.py
```

### 环境变量配置

复制 `.env.example` 为 `.env`,然后编辑填入你的 APP_KEY:

```bash
cp .env.example .env
```

编辑 `.env` 文件:
```bash
APP_KEY=your_app_key_here
```

APP_KEY 从大风车开放平台获取,用于 API 认证。

### 各系统依赖要求

| 依赖项 | macOS | Windows | Linux | 说明 |
|--------|-------|---------|-------|------|
| Python 3.8+ | ✅ | ✅ | ✅ | 必需 |
| pip | ✅ | ✅ | ✅ | 必需 |
| playwright | ✅ | ✅ | ✅ | 浏览器自动化 |
| Chromium | ✅ | ✅ | ✅ | 通过 playwright 安装 |
| Xcode Command Line Tools | ✅ | ❌ | ❌ | macOS 专用 |
| Visual C++ Redistributable | ❌ | ✅ | ❌ | Windows 专用 |

### 安装自检流程

运行 `python scripts/install_check.py` 会自动检测:

1. **Python 版本** - 需要 >= 3.8
2. **pip** - Python 包管理器
3. **playwright** - 浏览器自动化库
4. **Chromium** - Playwright 浏览器
5. **系统特定依赖**:
   - macOS: Xcode Command Line Tools
   - Windows: Visual C++ Redistributable

如果检测到缺失的依赖,会提示用户确认并自动安装。

**Windows 用户注意**:
- 使用 `python` 而不是 `python3`
- 首次运行前确保已安装 [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)(Playwright 依赖)
- Windows 的 cookie 加密使用 DPAPI,无需额外配置,不会弹窗要求输入密码

**macOS 用户注意**:
- 首次运行可能需要安装 Xcode Command Line Tools
- 如果遇到钥匙串弹窗问题,运行 `python scripts/fix_keychain.py`

## 常用命令

```bash
python scripts/sync_daemon.py            # 启动守护进程
python scripts/sync_daemon.py --setup    # 登录巨懂车
python scripts/sync_daemon.py --check    # 运行前自检
python scripts/sync_daemon.py --status   # 查看同步状态
python scripts/sync_daemon.py --reset    # 重置同步起点
python scripts/bootstrap.py              # 一键检查并启动
```

Windows 用户将 `python` 替换为 `python` 或 `py`。

## 认证架构(v3.0)

**所有大风车操作均使用 APP_KEY Token**,不再需要浏览器登录态。

- **读操作**(查重):APP_KEY → Token → `queryFindViewRecordPageInfo.json`
- **写操作**(新增):APP_KEY → Token → `pcbotwall/crm/customerObjectAction/saveCustomer.json`

只需配置 `APP_KEY` 环境变量,Token 自动获取,无需手动登录大风车。

## 核心模块

### dfc_client.py - 统一 CRM 客户端

大风车 CRM 的统一读写客户端,参考 `dfc-create-customer` 技能实现:

- `DfcClient` 类:统一处理读(查重)和写(新增/编辑)操作
- `build_fields()` 函数:将简化数据转换为 CRM 接口需要的完整 fields 数组
- 完整枚举字典:与 `dfc-create-customer` 技能完全对齐

### mapping.py - 字段映射

完整的枚举字典和映射函数:

- `map_source()`:巨懂车来源渠道 → 大风车 source 中文名
- `map_grade()`:巨懂车级别/状态 → 大风车意向等级(H/A/B/C/N)
- `map_gender()`:性别映射
- 完整枚举字典:`SOURCE`, `GRADE`, `GENDER`, `IMPORTANT` 等(中文名 → CRM code)

### dfc_writer.py - 兼容包装

向后兼容包装,实际逻辑委托给 `DfcClient`。新代码请直接使用 `dfc_client.DfcClient`。

### platform_utils.py - 跨平台工具

处理 macOS / Windows / Linux 差异的工具模块:

- `get_os_type()`:检测操作系统类型
- `get_app_data_dir()`:获取跨平台的应用数据目录
- `get_playwright_cache_dir()`:获取 Playwright 浏览器缓存目录
- `find_chrome_binary()`:自动查找 Chrome/Chromium 可执行文件
- `kill_process_on_port()`:跨平台清理端口占用
- `get_default_browser_data_dir()`:获取默认浏览器数据目录

## 字段映射

见 `references/field-mapping.md`。核心:
- 手机号 → customer_field_phone(去重键)
- 来源 → customer_field_source(通过 mapping.map_source 映射)
- 级别 → customer_field_grade(H/A/B/C/N)
- 门店 → APP_KEY 对应门店(自动获取)
- 销售 → 留空(或从 config 读取)

## 与 dfc-create-customer 技能的关系

本技能的 CRM 操作参考了 `dfc-create-customer` 技能:
- 使用相同的 API 端点(`/pcbotwall/crm/customerObjectAction/saveCustomer.json`)
- 使用相同的认证方式(APP_KEY → Token)
- 使用相同的字段构建方式(`build_fields` 函数)
- 使用相同的枚举字典(中文名 → CRM code)

## Must Not Do

- 不同步存量客户(仅新留资)
- 不回写大风车改动到巨懂车
- 巨懂车登录态过期时不静默失败,提示重新 --setup
- APP_KEY 无效时不静默失败,提示检查环境变量

## 升级说明

### v3.1.1（当前）

主要变更：
1. **修复硬编码路径**：`jvdc_scraper.py` 调试路径改为跨平台
2. **修复 os 导入**：`JudongcheScraper` 类方法中正确导入 `os`
3. **配置文件优化**：`config.json` 使用 `<APP_DATA>` 占位符
4. **添加 .env.example**：提供环境变量配置模板
5. **清理废弃文件**：将调试/测试脚本移到 `archive/` 目录
6. **添加项目结构说明**：文档中说明目录结构

### v3.1

主要变更：
1. **跨平台支持**：新增 `platform_utils.py` 模块，支持 macOS / Windows / Linux
2. **配置文件优化**：使用 `<APP_DATA>` 占位符，自动适配不同系统的应用数据目录
3. **Chrome 查找优化**：自动查找 Playwright 安装的 Chrome，支持多架构（arm64/x64）
4. **进程管理跨平台**：端口占用清理支持 Windows（netstat + taskkill）
5. **安装自检**：新增 `install_check.py` 自动检测并安装依赖

### v3.0

主要变更:
1. 统一 CRM 客户端:`dfc_client.DfcClient` 同时处理读写操作
2. 完整枚举字典:与 `dfc-create-customer` 技能完全对齐
3. 删除过时的 `dfc_browser_writer.py`(浏览器 Cookie 方式)
4. 简化 `dfc_writer.py` 为兼容包装

### v2.0

主要变更:
1. 移除大风车浏览器登录要求(`--dfc-setup` 命令已删除)
2. 写操作改用 APP_KEY Token 认证
3. 简化部署流程,只需配置 `APP_KEY` 环境变量
