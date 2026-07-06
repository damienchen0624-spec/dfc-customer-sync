---
name: dfc-customer-sync
description: >
  巨懂车客户自动同步到大风车。后台守护进程每 10 分钟从巨懂车后台抓取新留资客户,
  手机号去重后写入大风车客户列表。当用户说"同步巨懂车客户"、"巨懂车留资同步大风车"、
  "启动客户同步"时使用。
version: 3.6.1
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
│   ├── error_handler.py      # 错误处理(自动匹配 troubleshooting)
│   ├── jvdc_scraper.py       # 巨懂车抓取器
│   ├── mapping.py            # 字段映射
│   ├── state.py              # 状态管理
│   └── platform_utils.py     # 跨平台工具
├── references/                # 参考文档
│   ├── troubleshooting.md    # 故障排除指南
│   └── field-mapping.md      # 字段映射明细
├── archive/                   # 归档的调试/测试脚本
├── requirements.txt          # Python 依赖
└── SKILL.md                  # 本文档
```

## 安装

### 方式 1: PyPI 安装（推荐）

```bash
# 国内用户使用清华镜像
pip install dfc-customer-sync -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或者使用阿里云镜像
pip install dfc-customer-sync -i https://mirrors.aliyun.com/pypi/simple/

# 国外用户直接安装
pip install dfc-customer-sync
```

安装后使用：
```bash
# 方式 1: 命令行工具
dfc-sync --setup
dfc-sync

# 方式 2: Python 模块
python -m dfc_customer_sync --setup
python -m dfc_customer_sync
```

### 方式 2: GitHub Release 安装

```bash
# 使用安装脚本（自动选择镜像）
curl -sL https://raw.githubusercontent.com/damienchen0624-spec/dfc-customer-sync/main/install.sh | bash

# 或手动下载
curl -L "https://mirror.ghproxy.com/https://github.com/damienchen0624-spec/dfc-customer-sync/releases/download/v3.6.1/dfc-customer-sync-v3.6.1.zip" -o /tmp/dfc-sync.zip && \
unzip -q /tmp/dfc-sync.zip -d ~/Library/Application\ Support/大风车\ AI\ 龙虾/SKILLs/ && \
rm /tmp/dfc-sync.zip
```

### 备选镜像

如果上述镜像不可用，尝试：

```bash
# 镜像 1: github.moeyy.xyz
curl -L "https://github.moeyy.xyz/https://github.com/damienchen0624-spec/dfc-customer-sync/releases/download/v3.6.1/dfc-customer-sync-v3.6.1.zip" -o /tmp/dfc-sync.zip

# 镜像 2: gh-proxy.com
curl -L "https://gh-proxy.com/https://github.com/damienchen0624-spec/dfc-customer-sync/releases/download/v3.6.1/dfc-customer-sync-v3.6.1.zip" -o /tmp/dfc-sync.zip

# 直接下载（需要能访问 GitHub）
curl -L "https://github.com/damienchen0624-spec/dfc-customer-sync/releases/download/v3.6.1/dfc-customer-sync-v3.6.1.zip" -o /tmp/dfc-sync.zip
```

下载后解压：

```bash
unzip -q /tmp/dfc-sync.zip -d ~/Library/Application\ Support/大风车\ AI\ 龙虾/SKILLs/
rm /tmp/dfc-sync.zip
```

### 手动安装

```bash
# 1. 下载 Release
# 访问 https://github.com/damienchen0624-spec/dfc-customer-sync/releases
# 下载 dfc-customer-sync-v3.6.1.zip

# 2. 解压到技能目录
unzip dfc-customer-sync-v3.6.1.zip -d ~/Library/Application\ Support/大风车\ AI\ 龙虾/SKILLs/

# 3. 复制配置文件
cd ~/Library/Application\ Support/大风车\ AI\ 龙虾/SKILLs/dfc-customer-sync
cp config/config.example.json config/config.json
```

## 首次使用

### 快速开始

```bash
# 1. 复制配置(配置文件中的 <APP_DATA> 会自动替换为系统对应路径)
cp config/config.example.json config/config.json

# 2. 首次登录巨懂车(自动检测 APP_KEY 并打开浏览器登录)
python scripts/sync_daemon.py --setup

# 3. 启动守护进程
python scripts/sync_daemon.py
```

### 环境变量说明

技能会自动从用户环境变量中获取大风车 APP_KEY,无需手动配置:
- 使用 `APP_KEY` 环境变量

运行 `--setup` 时会自动检测并验证 APP_KEY 是否有效。

### 各系统依赖要求

| 依赖项 | macOS | Windows | Linux | 说明 |
|--------|-------|---------|-------|------|
| Python 3.8+ | ✅ | ✅ | ✅ | 必需 |
| pip | ✅ | ✅ | ✅ | 必需 |
| playwright | ✅ | ✅ | ✅ | 浏览器自动化 |
| Chromium | ✅ | ✅ | ✅ | 通过 playwright 安装 |
| Xcode Command Line Tools | ✅ | ❌ | ❌ | macOS 专用 |
| Visual C++ Redistributable | ❌ | ✅ | ❌ | Windows 专用 |

### 依赖检查

运行 `--setup` 或 `--check` 时会自动检测:

1. **playwright** - 浏览器自动化库
2. **Chromium** - Playwright 浏览器
3. **APP_KEY** - 大风车认证(从环境变量自动获取)
4. **浏览器 Profile** - 巨懂车登录态

如果检测到缺失的依赖,会提示用户安装命令。

**Windows 用户注意**:
- 使用 `python` 而不是 `python3`
- 首次运行前确保已安装 [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)(Playwright 依赖)

**macOS 用户注意**:
- 脚本已处理 Keychain 弹窗问题(使用 `--password-store=basic` 参数)

## 常用命令

```bash
python scripts/sync_daemon.py            # 启动守护进程
python scripts/sync_daemon.py --setup    # 登录巨懂车
python scripts/sync_daemon.py --check    # 运行前自检
python scripts/sync_daemon.py --status   # 查看同步状态
python scripts/sync_daemon.py --reset    # 重置同步起点
```

Windows 用户将 `python` 替换为 `python` 或 `py`。

## 认证架构(v3.0)

**所有大风车操作均使用 APP_KEY Token**,不再需要浏览器登录态。

- **读操作**(查重):APP_KEY → Token → `queryFindViewRecordPageInfo.json`
- **写操作**(新增):APP_KEY → Token → `pcbotwall/crm/customerObjectAction/saveCustomer.json`

只需配置 `APP_KEY` 环境变量,Token 自动获取,无需手动登录大风车。

## 核心模块

### dfc_client.py - 统一 CRM 客户端

大风车 CRM 的统一读写客户端:

- `DfcClient` 类:统一处理读(查重)和写(新增)操作
- `build_fields()` 函数:将简化数据转换为 CRM 接口需要的完整 fields 数组
- 字段映射:同步流程中实际使用的字段(手机号、姓名、来源、等级、性别、重点客户、销售、意向描述、微信号、门店)

### mapping.py - 字段映射

同步流程中实际使用的映射:

- `map_source()`:巨懂车来源渠道 → 大风车 source 中文名
- `map_grade()`:巨懂车级别/状态 → 大风车意向等级(H/A/B/C/N)
- `map_gender()`:性别映射
- 枚举字典:`SOURCE`, `GRADE`, `GENDER`, `IMPORTANT`(中文名 → CRM code)

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

## 故障排除

如遇问题,查阅 [references/troubleshooting.md](references/troubleshooting.md)

## 项目文件

### 核心文档
- `SKILL.md` - 本文档,技能说明
- `references/troubleshooting.md` - 故障排除指南(**遇到问题必读**)
- `references/field-mapping.md` - 字段映射明细

### 脚本说明
- `scripts/sync_daemon.py` - 主守护进程(setup/daemon/check/status/reset)
- `scripts/auth.py` - 大风车认证模块(APP_KEY → Token)
- `scripts/dfc_client.py` - 大风车 CRM 客户端(读写操作)
- `scripts/error_handler.py` - 错误处理(自动匹配 troubleshooting 章节)
- `scripts/jvdc_scraper.py` - 巨懂车抓取器(浏览器自动化)
- `scripts/mapping.py` - 字段映射(枚举字典)
- `scripts/state.py` - 状态管理(同步进度)
- `scripts/platform_utils.py` - 跨平台工具(macOS/Windows/Linux)

## Must Not Do

- 不同步存量客户(仅新留资)
- 不回写大风车改动到巨懂车
- 巨懂车登录态过期时不静默失败,提示重新 --setup
- APP_KEY 无效时不静默失败,提示检查环境变量

## 升级说明

### v3.6.1（当前）

Bug 修复：
1. **修复 Windows CDP 模式页面空白** — `_start_chrome_cdp()` 启动参数缺少 `--disable-blink-features=AutomationControlled`，导致巨懂车检测到自动化浏览器后返回空白页

### v3.6.0

稳定性优化（P0/P1/P2）：
1. **P0: 浏览器崩溃自动恢复** — 检测到浏览器崩溃时自动重启，无需手动干预
2. **P0: 防止多实例运行** — PID 锁机制，确保只有一个守护进程实例
3. **P1: 浏览器健康检查** — 每轮同步前检查浏览器是否存活
4. **P1: 登录态过期醒目提示** — 登录态过期时输出醒目的警告信息
5. **P2: 日志轮转** — 使用 RotatingFileHandler（5MB × 7 份），避免日志无限增长
6. **P2: 错误分类** — 区分可恢复错误（自动重试）和不可恢复错误

Bug 修复：
1. **修复 `handle_error()` 参数不匹配** — `error_handler.handle_error()` 没有 `context` 参数，调用时传入 `context=...` 会导致 `TypeError` 并使守护进程退出

### v3.5.1

Bug 修复：
1. **修复 `Dict` 类型注解未导入**：sync_daemon.py 添加 `from typing import Dict`
2. **恢复 `error_handler.py`**：该模块在 v3.4.0 被误删，现已恢复，自动匹配 troubleshooting 给 agent 参考
3. **修复 `jvdc_scraper.py` 中 `Path` 未导入**：添加 `from pathlib import Path`
4. **修复 daemon 重复初始化代码**：清理重复的 token/account 获取

优化：
1. **setup 添加依赖检查**：自动检测 playwright 和 chromium 是否安装，给出清晰的安装命令
2. **daemon 添加前置检查**：启动前检查 APP_KEY、浏览器 profile、验证 token，失败时给出明确提示
3. **配置文件检查**：config.json 不存在时提示复制模板

### v3.5.0

主要变更：
1. **APP_KEY 自动检测**：setup 时自动从环境变量获取 APP_KEY（优先 DAFENGCHE_APP_KEY，备选 APP_KEY），不再询问用户
2. **Setup 流程优化**：先自动验证 APP_KEY 有效性，自检通过后再打开浏览器让用户登录
3. **交互体验改进**：更清晰的提示信息，引导用户完成登录操作

### v3.4.0

主要变更:
1. **代码精简**:删除未使用的模块(dfc_writer.py, setup_wizard.py, install_check.py, fix_keychain.py)
2. **字段映射精简**:mapping.py 只保留同步流程中实际使用的映射
3. **CRM 客户端精简**:dfc_client.py 的 build_fields() 只保留实际使用的字段构造器
4. **抓取器精简**:删除未使用的 JudongcheScraper 类
5. **项目结构优化**:从 13 个脚本精简到 8 个,删除约 4000 行未使用代码

注:error_handler.py 在 v3.5.1 中已恢复

### v3.3.0

主要变更:
1. **智能错误处理**:新增 `error_handler.py`,自动捕获错误并查阅 reference 给 agent 参考
2. **灵活处理机制**:reference 仅作为参考,agent 可根据实际情况灵活处理
3. **支持 10+ 种错误类型**:登录态、浏览器启动、端口占用、API 认证等

### v3.2.1

主要变更:
1. **添加故障排除指南**:新增 `references/troubleshooting.md`,记录 12 个常见问题及解决方案
2. **SKILL.md 更新**:添加故障排除章节,指引 agent 在用户遇到问题时查阅 reference
3. **一键安装脚本**:自动安装技能到 OpenClaw skills 目录

### v3.2.0

主要变更:
1. **交互式设置向导**:新增 `setup_wizard.py`,用户只需运行一个命令即可完成所有配置
2. **修复 Profile 加载问题**:移除 `--no-sandbox` 参数,确保 Chromium 正确加载保存的 profile
3. **统一启动参数**:setup 和 daemon 使用相同的浏览器启动参数
4. **添加调试日志**:显示实际使用的 profile 目录路径

### v3.1.1

主要变更:
1. **修复硬编码路径**:`jvdc_scraper.py` 调试路径改为跨平台
2. **修复 os 导入**:`JudongcheScraper` 类方法中正确导入 `os`
3. **配置文件优化**:`config.json` 使用 `<APP_DATA>` 占位符
4. **添加 .env.example**:提供环境变量配置模板
5. **清理废弃文件**:将调试/测试脚本移到 `archive/` 目录
6. **添加项目结构说明**:文档中说明目录结构

### v3.1

主要变更:
1. **跨平台支持**:新增 `platform_utils.py` 模块,支持 macOS / Windows / Linux
2. **配置文件优化**:使用 `<APP_DATA>` 占位符,自动适配不同系统的应用数据目录
3. **Chrome 查找优化**:自动查找 Playwright 安装的 Chrome,支持多架构(arm64/x64)
4. **进程管理跨平台**:端口占用清理支持 Windows(netstat + taskkill)
5. **安装自检**:新增 `install_check.py` 自动检测并安装依赖

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
