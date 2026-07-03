# 故障排除指南 (Troubleshooting)

本文档记录了开发和部署过程中碰到的所有问题及解决方案。当用户遇到问题时，agent 应优先查阅本文档。

---

## 问题 1: Chromium 没有使用保存的 Profile 打开

**症状**: 
- 每次启动浏览器都需要重新登录
- Cookie 没有正确加载
- 提示登录态过期

**原因**: 
`run_setup` 函数中使用了 `--no-sandbox` 参数，这个参数会影响 Chromium 正确加载持久化 profile。

**解决方案**: 
移除 `--no-sandbox` 参数。已在 v3.2.0 修复。

```python
# 错误的启动参数
args=["--no-sandbox", "--window-position=200,100"]

# 正确的启动参数
args=[
    "--window-position=200,100",
    "--window-size=1280,800",
    "--disable-blink-features=AutomationControlled",
]
```

**验证方法**: 
运行 `python scripts/sync_daemon.py --setup`，登录后关闭浏览器，再次运行 `python scripts/sync_daemon.py`，应该不需要重新登录。

---

## 问题 2: macOS 钥匙串弹窗要求输入密码

**症状**: 
- 每次启动浏览器时弹出系统对话框要求输入钥匙串密码
- 阻塞自动化流程

**原因**: 
Chromium 默认使用 macOS Keychain 存储密码，Playwright 启动时会触发 Keychain 访问。

**解决方案**: 
添加 `--password-store=basic` 参数，让 Chromium 使用基本存储而不是 Keychain。

```python
# macOS 特殊处理
if platform_utils.get_os_type() == "macos":
    args.append("--password-store=basic")
```

**注意**: 这个参数只在 macOS 上需要，Windows 使用 DPAPI 加密，不会弹窗。

---

## 问题 3: Playwright 被网站检测为自动化浏览器

**症状**: 
- 页面加载空白
- 被重定向到验证页面
- 某些功能无法使用

**原因**: 
网站检测到 `navigator.webdriver` 属性为 true，识别为自动化工具。

**解决方案**: 
添加 `--disable-blink-features=AutomationControlled` 参数。

```python
args=["--disable-blink-features=AutomationControlled"]
```

**补充**: 某些网站还需要额外的反检测措施，如修改 User-Agent、添加随机延迟等。

---

## 问题 4: 手机号显示为脱敏格式（138****1234）

**症状**: 
- 抓取的手机号是 `138****1234` 格式
- 无法用于大风车去重

**原因**: 
巨懂车页面默认隐藏完整手机号，需要点击"眼睛"图标才能显示。

**解决方案**: 
在抓取前自动点击所有 `EyeInvisible` 图标。

```python
def _reveal_all_phones(page):
    """点击所有 EyeInvisible 图标，让手机号从脱敏变为完整。"""
    eye_icons = page.query_selector_all("svg.icon_-icon-EyeInvisible")
    for icon in eye_icons:
        icon.click()
        time.sleep(0.3)  # 等待 DOM 更新
```

**注意**: 图标可能延迟加载，需要等待表格完全渲染后再点击。

---

## 问题 5: 表格数据未加载完成就抓取

**症状**: 
- 抓取到 0 条数据
- 抓取到部分数据
- 表格显示"暂无内容"

**原因**: 
Arco Design 表格使用异步加载，需要等待 spinner 消失和数据渲染完成。

**解决方案**: 
使用多层等待策略：

```python
# 1. 等待表格容器出现
page.wait_for_selector(".arco-table", timeout=30000)

# 2. 等待加载 spinner 消失（关键！）
page.wait_for_selector(".arco-spin-loading-layer", state="hidden", timeout=30000)

# 3. 额外等待确保 DOM 更新
page.wait_for_timeout(2000)
```

**注意**: 不要只依赖 `networkidle`，SPA 应用的请求可能持续不断。

---

## 问题 6: 跨平台路径问题

**症状**: 
- Windows 用户运行报错找不到路径
- Linux 用户配置文件路径错误

**原因**: 
硬编码了 macOS 路径 `~/Library/Application Support/...`。

**解决方案**: 
使用 `platform_utils.py` 统一处理跨平台路径。

```python
# 获取应用数据目录
app_data = platform_utils.get_app_data_dir()
# macOS: ~/Library/Application Support/大风车 AI 龙虾
# Windows: %APPDATA%/大风车 AI 龙虾
# Linux: ~/.local/share/大风车 AI 龙虾

# 获取浏览器数据目录
browser_data = platform_utils.get_default_browser_data_dir()
```

**配置文件**: 使用 `<APP_DATA>` 占位符，运行时自动替换。

```json
{
  "browser": {
    "user_data_dir": "<APP_DATA>/jvdc-browser"
  }
}
```

---

## 问题 7: Chrome/Chromium 找不到

**症状**: 
- 报错 "未找到 Chrome 浏览器"
- `find_chrome_binary()` 返回 None

**原因**: 
Playwright 安装的 Chromium 路径不在系统 PATH 中。

**解决方案**: 
`platform_utils.find_chrome_binary()` 会自动搜索以下位置：

1. Playwright 缓存目录（优先）
   - macOS: `~/Library/Caches/ms-playwright/chromium-*/chrome-mac-*/...`
   - Windows: `%LOCALAPPDATA%/ms-playwright/chromium-*/chrome-win64/chrome.exe`
   - Linux: `~/.cache/ms-playwright/chromium-*/chrome-linux/chrome`

2. 系统安装的 Chrome
   - macOS: `/Applications/Google Chrome.app/...`
   - Windows: `C:\Program Files\Google\Chrome\Application\chrome.exe`

**手动安装**: 
```bash
python3 -m playwright install chromium
```

---

## 问题 8: Windows 上 Playwright 安装失败

**症状**: 
- 安装 playwright 时报错缺少 Visual C++ 组件
- Chromium 启动失败

**原因**: 
Playwright 依赖 Visual C++ Redistributable。

**解决方案**: 
安装 [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)。

**自动检测**: `install_check.py` 会自动检测并提示安装。

---

## 问题 9: 端口 9222 被占用

**症状**: 
- 报错 "Chrome CDP 端口 9222 未就绪"
- 浏览器启动失败

**原因**: 
上次运行的 Chrome 进程没有正常退出，占用了 CDP 调试端口。

**解决方案**: 
`platform_utils.kill_process_on_port()` 会自动清理端口。

```python
# 跨平台清理端口
platform_utils.kill_process_on_port(9222)
```

**手动清理**: 
```bash
# macOS/Linux
lsof -ti:9222 | xargs kill -9

# Windows
netstat -ano | findstr :9222
taskkill /F /PID <pid>
```

---

## 问题 10: APP_KEY 无效或过期

**症状**: 
- 报错 "大风车 Token 过期"
- API 返回 401

**原因**: 
- APP_KEY 填写错误
- APP_KEY 被禁用
- 门店信息变更

**解决方案**: 
1. 检查 `.env` 文件中的 APP_KEY 是否正确
2. 登录大风车开放平台确认 APP_KEY 状态
3. 重新获取 APP_KEY 并更新 `.env` 文件

**验证**: 
```bash
python scripts/sync_daemon.py --check
```

---

## 问题 11: 登录态频繁过期

**症状**: 
- 每隔几小时就需要重新登录
- Cookie 保存不成功

**原因**: 
- 巨懂车网站设置了较短的 Cookie 有效期
- 浏览器 profile 目录权限问题
- 多设备登录导致 Cookie 失效

**解决方案**: 
1. 确保使用持久化上下文（`launch_persistent_context`）
2. 检查 profile 目录权限：`ls -la ~/.dfc-customer-sync/jvdc-browser`
3. 避免在其他浏览器登录同一账号

**临时方案**: 
运行 `python scripts/sync_daemon.py --setup` 重新登录。

---

## 问题 12: 同步重复客户

**症状**: 
- 大风车中出现重复客户
- 同一个手机号被多次写入

**原因**: 
- 状态文件 `state.json` 丢失或损坏
- 手机号格式不一致（带空格、带国家码）

**解决方案**: 
1. `normalize_phone()` 函数会提取 11 位手机号
2. `state.json` 记录已同步的手机号
3. 如需重置：`python scripts/sync_daemon.py --reset`

**注意**: 大风车 API 本身也有去重逻辑，但依赖手机号格式一致。

---

## 快速诊断命令

```bash
# 运行自检
python scripts/sync_daemon.py --check

# 查看同步状态
python scripts/sync_daemon.py --status

# 重置同步起点（重新同步所有新客户）
python scripts/sync_daemon.py --reset

# 重新登录巨懂车
python scripts/sync_daemon.py --setup
```

---

## 联系支持

如果以上方案都无法解决问题，请提供以下信息：

1. 操作系统版本（macOS/Windows/Linux）
2. Python 版本：`python3 --version`
3. 错误日志：`cat ~/Library/Application\ Support/大风车\ AI\ 龙虾/jvdc-sync/sync.log`
4. 浏览器 profile 目录：`ls -la ~/Library/Application\ Support/大风车\ AI\ 龙虾/jvdc-browser`
