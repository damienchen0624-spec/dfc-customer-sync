#!/bin/bash
# 巨懂车客户同步大风车 - 智能安装/更新脚本
# 用法: curl -fsSL https://raw.githubusercontent.com/damienchen0624-spec/dfc-customer-sync/main/install.sh | bash

set -e

# 技能目录
SKILL_DIR="$HOME/Library/Application Support/大风车 AI 龙虾/SKILLs/dfc-customer-sync"
TEMP_DIR="/tmp/dfc-customer-sync-install-$$"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  巨懂车客户同步大风车 - 安装检查"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 获取远程最新版本
get_remote_version() {
    curl -sL "https://raw.githubusercontent.com/damienchen0624-spec/dfc-customer-sync/main/SKILL.md" | grep "^version:" | head -1 | awk '{print $2}'
}

# 获取本地版本
get_local_version() {
    if [ -f "$SKILL_DIR/SKILL.md" ]; then
        grep "^version:" "$SKILL_DIR/SKILL.md" | head -1 | awk '{print $2}'
    else
        echo "0.0.0"
    fi
}

# 比较版本号 (返回 0 表示 v1 >= v2, 1 表示 v1 < v2)
version_compare() {
    local v1=$1
    local v2=$2
    
    # 如果版本相同
    if [ "$v1" = "$v2" ]; then
        return 0
    fi
    
    # 使用 sort -V 比较
    local smaller=$(echo -e "$v1\n$v2" | sort -V | head -n1)
    if [ "$smaller" = "$v1" ]; then
        return 1  # v1 < v2
    else
        return 0  # v1 > v2
    fi
}

# 检查是否已安装
if [ -d "$SKILL_DIR" ] && [ -f "$SKILL_DIR/SKILL.md" ]; then
    LOCAL_VERSION=$(get_local_version)
    echo -e "${GREEN}✅ 检测到已安装技能${NC}"
    echo "   本地版本: $LOCAL_VERSION"
    echo ""
    echo "🔍 检查更新..."
    
    REMOTE_VERSION=$(get_remote_version)
    
    if [ -z "$REMOTE_VERSION" ]; then
        echo -e "${RED}❌ 无法获取远程版本信息${NC}"
        echo "   请检查网络连接"
        exit 1
    fi
    
    echo "   远程版本: $REMOTE_VERSION"
    echo ""
    
    # 比较版本
    if version_compare "$LOCAL_VERSION" "$REMOTE_VERSION"; then
        echo -e "${GREEN}✅ 已是最新版本，无需更新${NC}"
        echo ""
        
        # 询问是否重新安装
        read -p "是否重新安装? (y/n): " -n 1 -r
        echo ""
        
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo ""
            echo "如需启动同步，请说: \"启动客户同步\""
            exit 0
        fi
    else
        echo -e "${YELLOW}📦 发现新版本: $LOCAL_VERSION → $REMOTE_VERSION${NC}"
        echo ""
    fi
    
    # 执行更新
    echo "📥 下载新版本..."
    rm -rf "$TEMP_DIR"
    git clone --depth 1 https://github.com/damienchen0624-spec/dfc-customer-sync.git "$TEMP_DIR" 2>/dev/null
    
    # 备份配置
    if [ -f "$SKILL_DIR/.env" ]; then
        echo "📋 备份配置文件..."
        cp "$SKILL_DIR/.env" "$TEMP_DIR/.env"
    fi
    if [ -f "$SKILL_DIR/config/config.json" ]; then
        cp "$SKILL_DIR/config/config.json" "$TEMP_DIR/config/config.json" 2>/dev/null || true
    fi
    
    # 替换技能目录
    echo "🔄 更新技能文件..."
    rm -rf "$SKILL_DIR"
    mkdir -p "$HOME/Library/Application Support/大风车 AI 龙虾/SKILLs"
    cp -r "$TEMP_DIR" "$SKILL_DIR"
    rm -rf "$TEMP_DIR"
    
    echo -e "${GREEN}✅ 更新完成！${NC}"
    echo ""
    
else
    # 全新安装
    echo "📦 首次安装..."
    echo ""
    
    # 下载代码
    echo "📥 下载代码..."
    rm -rf "$TEMP_DIR"
    git clone --depth 1 https://github.com/damienchen0624-spec/dfc-customer-sync.git "$TEMP_DIR" 2>/dev/null
    
    # 安装到 skills 目录
    echo "📂 安装技能..."
    mkdir -p "$HOME/Library/Application Support/大风车 AI 龙虾/SKILLs"
    cp -r "$TEMP_DIR" "$SKILL_DIR"
    rm -rf "$TEMP_DIR"
fi

# 进入技能目录
cd "$SKILL_DIR"

# 显示安装版本
INSTALLED_VERSION=$(get_local_version)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  当前版本: $INSTALLED_VERSION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 安装依赖
echo "📦 检查依赖..."
python3 -m pip install playwright -q 2>/dev/null || pip3 install playwright -q 2>/dev/null

# 检查 Chromium
if ! python3 -c "import subprocess; subprocess.check_call(['python3', '-m', 'playwright', 'install', '--dry-run', 'chromium'], stderr=subprocess.DEVNULL)" 2>/dev/null; then
    echo "🌐 安装浏览器..."
    python3 -m playwright install chromium 2>/dev/null || python3 -m playwright install chromium
fi

echo ""
echo -e "${GREEN}✅ 安装完成！${NC}"
echo ""

# 检查是否需要设置
if [ ! -f "$SKILL_DIR/.env" ] || ! grep -q "APP_KEY=.*[a-zA-Z0-9]" "$SKILL_DIR/.env" 2>/dev/null; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  启动设置向导..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # 启动设置向导
    python3 scripts/setup_wizard.py
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  配置已完成"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "💡 使用方式:"
    echo "   • 说 \"启动客户同步\" 启动同步服务"
    echo "   • 说 \"同步巨懂车客户\" 同步客户数据"
    echo ""
    echo "   或手动启动:"
    echo "   cd \"$SKILL_DIR\" && python3 scripts/bootstrap.py"
    echo ""
fi
