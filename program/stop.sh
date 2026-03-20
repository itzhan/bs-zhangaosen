#!/bin/bash
# 停止所有服务
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "正在停止服务..."

# 通过 PID 文件停止
if [ -f "$PROJECT_DIR/.logs/flask.pid" ]; then
  PID=$(cat "$PROJECT_DIR/.logs/flask.pid")
  kill $PID 2>/dev/null && echo "已停止 Flask (PID: $PID)"
  rm -f "$PROJECT_DIR/.logs/flask.pid"
fi

# 通过端口停止
kill $(lsof -t -i :5001) 2>/dev/null

# 清理 tail 进程
pkill -f "tail -f .logs/flask.log" 2>/dev/null

echo "所有服务已停止"
