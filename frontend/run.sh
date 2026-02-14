#!/bin/bash
# WenShape Frontend Startup Script for Linux/Mac

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export LANG=${LANG:-en_US.UTF-8}
export LC_ALL=${LC_ALL:-en_US.UTF-8}

echo "Starting WenShape Frontend..."
echo "正在启动 WenShape 前端..."

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    echo "正在安装依赖..."
    npm install
fi

echo ""
FRONTEND_PORT="${VITE_DEV_PORT:-${WENSHAPE_FRONTEND_PORT:-3000}}"
BACKEND_PORT="${VITE_BACKEND_PORT:-${WENSHAPE_BACKEND_PORT:-8000}}"
BACKEND_URL="${VITE_BACKEND_URL:-http://localhost:${BACKEND_PORT}}"
echo "Starting development server at http://localhost:${FRONTEND_PORT}"
echo "开发服务器启动于 http://localhost:${FRONTEND_PORT}"
echo ""
echo "Make sure backend is running at ${BACKEND_URL}"
echo "请确保后端服务运行在 ${BACKEND_URL}"
echo ""

npm run dev
