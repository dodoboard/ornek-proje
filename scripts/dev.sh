#!/usr/bin/env bash
# Start the backend API and the frontend dev server. Ctrl+C stops both.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export NEXT_TELEMETRY_DISABLED=1

UVICORN="$ROOT/backend/.venv/bin/uvicorn"
[[ -x "$UVICORN" ]] || { echo "Backend venv not found. See README: Backend setup." >&2; exit 1; }

"$UVICORN" app.main:create_app --factory \
  --app-dir "$ROOT/backend" --host 127.0.0.1 --port 8000 \
  --reload --reload-dir "$ROOT/backend/app" &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM

cd "$ROOT/frontend"
npm run dev
