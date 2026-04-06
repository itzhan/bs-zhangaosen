#!/bin/bash
# ============================================================
#  京东手机评论分析系统 — 开发模式一键启动
#  用法: ./dev.sh          启动开发环境
#        ./dev.sh stop     停止开发环境
#        ./dev.sh rebuild  重新构建并启动
#        ./dev.sh logs     查看实时日志
# ============================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE="docker compose -f docker-compose.dev.yml"
ACTION="${1:-up}"

case "$ACTION" in
  stop|down)
    echo -e "${BLUE}[停止] 关闭开发环境...${NC}"
    $COMPOSE down
    echo -e "${GREEN}✓ 已停止${NC}"
    exit 0
    ;;
  logs)
    $COMPOSE logs -f app
    exit 0
    ;;
  rebuild)
    echo -e "${BLUE}[重建] 重新构建镜像...${NC}"
    $COMPOSE build --no-cache
    echo -e "${GREEN}✓ 构建完成${NC}"
    ;;
esac

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║   京东手机评论分析系统 — 开发模式               ║"
echo "║   热加载 · 轻量 · 快速启动                      ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# 检查 Docker
if ! command -v docker &>/dev/null; then
    echo -e "${RED}✗ 未安装 Docker，请先安装 Docker Desktop${NC}"
    exit 1
fi

if ! docker info &>/dev/null; then
    echo -e "${RED}✗ Docker 未运行，请先启动 Docker Desktop${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker 就绪${NC}"

# 构建 & 启动
echo -e "${BLUE}[启动] 构建并启动 MySQL + Flask ...${NC}"
$COMPOSE up -d --build 2>&1

echo ""
echo -e "${GREEN}✓ 容器已启动${NC}"
$COMPOSE ps

# 等待 Flask 就绪
echo ""
echo -ne "${BLUE}[等待] Flask 启动中"
for i in $(seq 1 30); do
    if curl -s http://localhost:5001 >/dev/null 2>&1; then
        break
    fi
    echo -ne "."
    sleep 2
done
echo -e "${NC}"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✓ 开发环境就绪！                               ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  前台:     ${CYAN}http://localhost:5001${GREEN}               ║${NC}"
echo -e "${GREEN}║  管理后台: ${CYAN}http://localhost:5001/admin${GREEN}         ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  管理员:   admin / admin123                     ║${NC}"
echo -e "${GREEN}║  测试用户: user / user123                       ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  ${YELLOW}★ 修改 app/ 下代码会自动热加载${GREEN}                ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  停止: ${CYAN}./dev.sh stop${GREEN}                           ║${NC}"
echo -e "${GREEN}║  日志: ${CYAN}./dev.sh logs${GREEN}                           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}实时日志:${NC}"
$COMPOSE logs -f app
