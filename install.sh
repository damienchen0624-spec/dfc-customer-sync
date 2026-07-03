#!/bin/bash
# dfc-customer-sync 一键安装脚本
# 用法: bash install.sh [version]
# 示例: bash install.sh v3.6.0

set -e

VERSION="${1:-v3.6.0}"
SKILL_DIR="$HOME/Library/Application Support/大风车 AI 龙虾/SKILLs"
TEMP_DIR="/tmp/dfc-customer-sync-install"

echo "=== dfc-customer-sync 安装脚本 ==="
echo "版本: $VERSION"
echo ""

# 清理临时目录
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

# 下载（尝试多个镜像）
echo "1. 下载技能包..."
URLS=(
    "https://mirror.ghproxy.com/https://github.com/damienchen0624-spec/dfc-customer-sync/releases/download/$VERSION/dfc-customer-sync-$VERSION.zip"
    "https://github.moeyy.xyz/https://github.com/damienchen0624-spec/dfc-customer-sync/releases/download/$VERSION/dfc-customer-sync-$VERSION.zip"
    "https://gh-proxy.com/https://github.com/damienchen0624-spec/dfc-customer-sync/releases/download/$VERSION/dfc-customer-sync-$VERSION.zip"
    "https://github.com/damienchen0624-spec/dfc-customer-sync/releases/download/$VERSION/dfc-customer-sync-$VERSION.zip"
)

DOWNLOADED=false
for url in "${URLS[@]}"; do
    echo "   尝试: $url"
    if curl -L --connect-timeout 10 --max-time 60 -f -s -o "$TEMP_DIR/skill.zip" "$url"; then
        echo "   ✅ 下载成功"
        DOWNLOADED=true
        break
    else
        echo "   ⚠️ 下载失败，尝试下一个镜像..."
    fi
done

if [ "$DOWNLOADED" = false ]; then
    echo "❌ 所有镜像均失败，请检查网络连接或手动下载"
    echo "   手动下载地址: https://github.com/damienchen0624-spec/dfc-customer-sync/releases"
    exit 1
fi

# 备份旧版本
echo ""
echo "2. 备份旧版本..."
if [ -d "$SKILL_DIR/dfc-customer-sync" ]; then
    BACKUP_DIR="$SKILL_DIR/dfc-customer-sync-backup-$(date +%Y%m%d%H%M%S)"
    mv "$SKILL_DIR/dfc-customer-sync" "$BACKUP_DIR"
    echo "   ✅ 已备份到: $BACKUP_DIR"
else
    echo "   ℹ️ 无旧版本，跳过备份"
fi

# 解压安装
echo ""
echo "3. 安装技能..."
mkdir -p "$SKILL_DIR"
unzip -q "$TEMP_DIR/skill.zip" -d "$SKILL_DIR"
echo "   ✅ 安装完成"

# 复制配置文件（如果备份存在）
echo ""
echo "4. 恢复配置..."
if [ -d "$BACKUP_DIR" ] && [ -f "$BACKUP_DIR/config/config.json" ]; then
    cp "$BACKUP_DIR/config/config.json" "$SKILL_DIR/dfc-customer-sync/config/"
    echo "   ✅ 已恢复配置文件"
else
    echo "   ℹ️ 无旧配置，跳过（首次安装请运行 --setup）"
fi

# 清理
echo ""
echo "5. 清理临时文件..."
rm -rf "$TEMP_DIR"
echo "   ✅ 清理完成"

# 完成
echo ""
echo "=========================================="
echo "✅ 安装完成！"
echo "=========================================="
echo ""
echo "下一步操作："
echo "  1. 首次使用请运行: python3 scripts/sync_daemon.py --setup"
echo "  2. 启动守护进程: python3 scripts/sync_daemon.py"
echo "  3. 查看状态: python3 scripts/sync_daemon.py --status"
echo ""
echo "技能目录: $SKILL_DIR/dfc-customer-sync"
echo ""
