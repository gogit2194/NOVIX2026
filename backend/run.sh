#!/usr/bin/env bash
# WenShape Backend Startup Script for Linux/Mac
# Linux/Mac 启动脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting WenShape Backend Server..."
echo "正在启动 WenShape 后端服务器..."

# Check if virtual environment exists / 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating..."
    echo "虚拟环境不存在，正在创建..."
    python3 -m venv "venv"
fi

# shellcheck disable=SC1091
source "venv/bin/activate"

echo "Installing dependencies..."
echo "正在安装依赖..."
python -m pip install -r requirements.txt

# Check if .env exists / 检查 .env 是否存在
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Copying from .env.example..."
    echo "警告：.env 文件不存在，正在从 .env.example 复制..."
    if [ ! -f ".env.example" ]; then
        echo "[ERROR] .env.example not found in: $SCRIPT_DIR"
        exit 1
    fi
    cp ".env.example" ".env"
    echo "Created: $SCRIPT_DIR/.env"
    echo "Please edit .env file and add your API keys!"
    echo "请编辑 .env 文件并添加你的 API 密钥！"
    echo "Press Enter to continue..."
    read -r
fi

# Start server / 启动服务器
echo ""
BACKEND_PORT="${PORT:-${WENSHAPE_BACKEND_PORT:-8000}}"
export WENSHAPE_AUTO_PORT="${WENSHAPE_AUTO_PORT:-1}"
echo "Starting server at http://localhost:${BACKEND_PORT}"
echo "服务器启动于 http://localhost:${BACKEND_PORT}"
echo "API Docs: http://localhost:${BACKEND_PORT}/docs"
echo ""

python -m app.main
