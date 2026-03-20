#!/bin/bash
# ============================================================
#  京东手机评论分析系统 一键启动脚本 (Mac/Linux)
# ============================================================

set -e

# ---------- 颜色定义 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

# ---------- 项目配置 ----------
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_HOST="localhost"
DB_PORT="3306"
DB_NAME="jd_comment_analysis"
DB_USER="root"
DB_PASS="ab123168"
BACKEND_PORT=5001

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║    京东手机评论分析系统 — 一键启动              ║"
echo "║    基于Python的主流手机品牌数据可视化分析       ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# ---------- 环境检查 ----------
echo -e "${BLUE}[检查] 基础环境...${NC}"
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}✗ 未找到 python3${NC}"; exit 1; }
command -v pip3 >/dev/null 2>&1 || { echo -e "${RED}✗ 未找到 pip3${NC}"; exit 1; }
command -v mysql >/dev/null 2>&1 || { echo -e "${YELLOW}⚠ 未找到 mysql 客户端，跳过数据库检查${NC}"; SKIP_DB=1; }
echo -e "${GREEN}✓ Python3 + pip3 就绪${NC}"

# ---------- 安装依赖 ----------
cd "$PROJECT_DIR"
if [ ! -d "venv" ]; then
  echo -e "${BLUE}[安装] 创建虚拟环境...${NC}"
  python3 -m venv venv
fi
source venv/bin/activate
echo -e "${BLUE}[安装] 安装 Python 依赖...${NC}"
pip install -r requirements.txt -q 2>/dev/null || pip install -r requirements.txt

# ---------- 数据库检查 ----------
if [ -z "$SKIP_DB" ]; then
  echo -e "${BLUE}[检查] MySQL 数据库...${NC}"

  # 检查 MySQL 连接
  if ! mysql -h$DB_HOST -P$DB_PORT -u$DB_USER -p$DB_PASS -e "SELECT 1" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ 无法连接 MySQL，尝试启动...${NC}"
    brew services start mysql 2>/dev/null || true
    sleep 3
  fi

  # 检查/创建数据库
  DB_EXISTS=$(mysql -h$DB_HOST -P$DB_PORT -u$DB_USER -p$DB_PASS -e "SHOW DATABASES LIKE '$DB_NAME'" 2>/dev/null | grep $DB_NAME || true)
  if [ -z "$DB_EXISTS" ]; then
    echo -e "${BLUE}[数据库] 创建数据库 $DB_NAME ...${NC}"
    mysql -h$DB_HOST -P$DB_PORT -u$DB_USER -p$DB_PASS -e "CREATE DATABASE $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>/dev/null
  fi
  echo -e "${GREEN}✓ 数据库就绪${NC}"
fi

# ---------- 数据导入 ----------
echo -e "${BLUE}[数据] 导入评论数据...${NC}"
cd "$PROJECT_DIR"
python import_data.py 2>&1 | head -30

# ---------- 端口检查 ----------
if lsof -i :$BACKEND_PORT >/dev/null 2>&1; then
  echo -e "${YELLOW}⚠ 端口 $BACKEND_PORT 被占用，尝试终止...${NC}"
  kill $(lsof -t -i :$BACKEND_PORT) 2>/dev/null || true
  sleep 1
fi

# ---------- 启动应用 ----------
echo -e "${BLUE}[启动] 启动 Flask 应用 ...${NC}"
mkdir -p .logs
nohup python run.py > .logs/flask.log 2>&1 &
echo $! > .logs/flask.pid

# 等待就绪
echo -ne "${BLUE}[等待] 应用启动中"
for i in $(seq 1 15); do
  if curl -s http://localhost:$BACKEND_PORT >/dev/null 2>&1; then
    break
  fi
  echo -ne "."
  sleep 1
done
echo -e "${NC}"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✓ 系统启动成功！                               ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  前台地址: ${CYAN}http://localhost:$BACKEND_PORT${GREEN}             ║${NC}"
echo -e "${GREEN}║  管理后台: ${CYAN}http://localhost:$BACKEND_PORT/admin${GREEN}       ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  管理员: admin / admin123                       ║${NC}"
echo -e "${GREEN}║  测试用户: user / user123                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止，或运行 ./stop.sh${NC}"

# 实时显示日志
tail -f .logs/flask.log | sed "s/^/[Flask] /"
