#!/bin/zsh
cd -- "$(dirname "$0")"
uv sync --frozen
if [ ! -f frontend/dist/index.html ]; then
  npm ci --prefix frontend
  npm run build --prefix frontend
fi
echo "浏览器地址：http://127.0.0.1:8772"
PORT=8772 uv run uvicorn backend.app:app --host 127.0.0.1 --port 8772
