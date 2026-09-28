#!/usr/bin/env bash
# Start the backend API, the job worker (auto-restarted on crash) and the frontend dev server.
# Ctrl+C stops everything.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export NEXT_TELEMETRY_DISABLED=1

VENV="$ROOT/backend/.venv/bin"
[[ -x "$VENV/uvicorn" ]] || { echo "Backend venv not found. See README: Setup." >&2; exit 1; }

cd "$ROOT/backend"
"$VENV/alembic" upgrade head

"$VENV/uvicorn" app.main:create_app --factory --host 127.0.0.1 --port 8000 \
  --reload --reload-dir "$ROOT/backend/app" &
API_PID=$!
"$VENV/python" -m app.workers.supervisor &
WORKER_PID=$!
trap 'kill "$API_PID" "$WORKER_PID" 2>/dev/null || true; wait 2>/dev/null || true' EXIT INT TERM

cd "$ROOT/frontend"
npm run dev
