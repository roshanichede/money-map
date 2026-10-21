#!/usr/bin/env bash
# Start MoneyMap locally: FastAPI on :8000, Next.js on :3000.
# First run installs everything (Python venv + npm packages).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- backend ---
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  PY=""
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
      PY="$candidate"; break
    fi
  done
  if [ -z "$PY" ]; then
    echo "MoneyMap needs Python 3.10 or newer. On a Mac: brew install python@3.12" >&2
    exit 1
  fi
  if ! command -v npm >/dev/null; then
    echo "MoneyMap needs Node.js 20 or newer. On a Mac: brew install node" >&2
    exit 1
  fi
  echo "Setting up the Python environment with $PY (first run only)…"
  "$PY" -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
if [ ! -f sample_data/lloyds_statement_2026-09.pdf ]; then
  .venv/bin/python sample_data/generate.py >/dev/null
fi
if [ -f .env ]; then set -a; source .env; set +a; fi
.venv/bin/uvicorn app.main:app --port 8000 &
API_PID=$!

# --- frontend ---
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  echo "Installing frontend packages (first run only)…"
  npm install --silent
fi
trap 'kill $API_PID 2>/dev/null' EXIT
echo
echo "MoneyMap is starting: open http://localhost:3000"
echo "(Ctrl+C stops both servers.)"
npm run dev
