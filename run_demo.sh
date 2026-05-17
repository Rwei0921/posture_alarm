#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [ ! -f "demo.env" ]; then
  echo "找不到 demo.env，請先執行：python setup_demo.py"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source demo.env
set +a

PYTHON_BIN="python"
if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
fi

echo "使用 demo.env 啟動姿態警報系統..."
exec "$PYTHON_BIN" main.py
