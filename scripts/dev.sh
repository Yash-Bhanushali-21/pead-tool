#!/usr/bin/env bash
# Start FastAPI (uvicorn) + Vite dev server together. Ctrl+C stops both.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

UVICORN_PORT="${UVICORN_PORT:-8000}"
VITE_PORT="${VITE_PORT:-5173}"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
elif [[ -x "$ROOT/venv/bin/python" ]]; then
  PY="$ROOT/venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi

cleanup() {
  if [[ -n "${BACK_PID:-}" ]]; then
    kill "$BACK_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "==> PEAD dev (repo: $ROOT)"
echo "    API:  http://127.0.0.1:${UVICORN_PORT}"
echo "    UI:   http://localhost:${VITE_PORT}   (proxies /api → :${UVICORN_PORT})"
echo "    Python: $PY"
echo ""

"$PY" -m uvicorn server.app:app --reload --host 0.0.0.0 --port "$UVICORN_PORT" &
BACK_PID=$!

cd "$ROOT/web"
if [[ "$VITE_PORT" != "5173" ]]; then
  npm run dev -- --port "$VITE_PORT"
else
  npm run dev
fi
