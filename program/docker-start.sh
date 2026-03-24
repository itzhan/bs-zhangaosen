#!/bin/bash
# ============================================================
#  京东手机评论分析系统 — Docker 一键启动 (Hadoop + Spark 集群版)
# ============================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║   京东手机评论分析系统 — Docker 一键启动         ║"
echo "║   Hadoop + Spark + MySQL + Flask 集群            ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# ---------- 检查 Docker ----------
echo -e "${BLUE}[检查] Docker 环境...${NC}"
if ! command -v docker &>/dev/null; then
    echo -e "${RED}✗ 未安装 Docker，请先安装 Docker Desktop${NC}"
    exit 1
fi

if ! docker info &>/dev/null; then
    echo -e "${RED}✗ Docker 未运行，请先启动 Docker Desktop${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker 环境就绪${NC}"

# ---------- 构建镜像 ----------
echo ""
echo -e "${BLUE}[构建] 构建 Docker 镜像 (含 Hadoop 客户端 + PySpark + PyTorch)...${NC}"
echo -e "${YELLOW}  ⏳ 首次构建需要下载依赖，预计 5-15 分钟，请耐心等待${NC}"
echo -e "${YELLOW}  📋 下方会实时显示构建进度${NC}"
echo ""

# 显示完整构建日志，不用 tail 截断
docker compose --progress=plain build 2>&1

echo ""
echo -e "${GREEN}✓ 镜像构建完成${NC}"

# ---------- 启动服务 ----------
echo ""
echo -e "${BLUE}[启动] 启动 Hadoop + MySQL + Flask 集群...${NC}"
docker compose up -d

echo ""
echo -e "${GREEN}✓ 所有容器已启动${NC}"

# 显示容器状态
echo ""
echo -e "${BLUE}[状态] 容器运行情况:${NC}"
docker compose ps

# ---------- 等待 Flask 就绪 ----------
echo ""
echo -e "${BLUE}[等待] 等待 Flask 应用就绪 (自动导入数据 + 训练模型)...${NC}"
echo -e "${YELLOW}  ⏳ 首次启动会自动: 初始化HDFS → 导入数据 → 训练LSTM模型${NC}"
echo -e "${YELLOW}  📋 查看详细日志: docker compose logs -f app${NC}"
echo ""

READY=0
for i in $(seq 1 90); do
    if curl -s http://localhost:5001 >/dev/null 2>&1; then
        READY=1
        break
    fi
    # 每10秒显示一次进度
    if [ $((i % 5)) -eq 0 ]; then
        ELAPSED=$((i * 2))
        echo -e "  ⏳ 已等待 ${ELAPSED}s ... (Flask 仍在初始化)"
    fi
    sleep 2
done

echo ""
if [ $READY -eq 1 ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ 系统启动成功！                                   ║${NC}"
    echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║  前台地址:    ${CYAN}http://localhost:5001${GREEN}                ║${NC}"
    echo -e "${GREEN}║  管理后台:    ${CYAN}http://localhost:5001/admin${GREEN}          ║${NC}"
    echo -e "${GREEN}║  行为分析:    ${CYAN}http://localhost:5001/analysis/behavior${GREEN}║${NC}"
    echo -e "${GREEN}║  模型对比:    ${CYAN}http://localhost:5001/analysis/model-compare${GREEN}║${NC}"
    echo -e "${GREEN}║  系统监控:    ${CYAN}http://localhost:5001/analysis/monitor${GREEN} ║${NC}"
    echo -e "${GREEN}║  HDFS Web UI: ${CYAN}http://localhost:9870${GREEN}                ║${NC}"
    echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║  管理员:   admin / admin123                         ║${NC}"
    echo -e "${GREEN}║  测试用户: user / user123                           ║${NC}"
    echo -e "${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║  停止服务: docker compose down                      ║${NC}"
    echo -e "${GREEN}║  查看日志: docker compose logs -f app               ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
else
    echo -e "${YELLOW}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ⏳ 服务仍在初始化中 (可能在训练 LSTM 模型)         ║${NC}"
    echo -e "${YELLOW}║  请用以下命令查看实时日志:                          ║${NC}"
    echo -e "${YELLOW}║  ${CYAN}docker compose logs -f app${YELLOW}                       ║${NC}"
    echo -e "${YELLOW}║                                                      ║${NC}"
    echo -e "${YELLOW}║  初始化完成后访问: ${CYAN}http://localhost:5001${YELLOW}          ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════╝${NC}"
fi

echo ""
echo -e "${BLUE}常用命令:${NC}"
echo -e "  docker compose logs -f app               # 查看应用日志"
echo -e "  docker compose ps                        # 查看容器状态"
echo -e "  docker exec jd-comment-app hdfs dfs -ls -R /jd_comment_analysis  # 查看HDFS"
echo -e "  docker exec jd-comment-app python spark_analysis.py  # Spark分析"
echo -e "  docker compose down                      # 停止所有服务"
