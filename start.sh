#!/usr/bin/env bash
# Start MoneyMap locally: FastAPI on :8000, Next.js on :3000.
# Installs or updates dependencies when needed, reads settings from .env (see .env.example).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- settings ---
ENV_FILE="$ROOT/.env"
if [ -f "$ENV_FILE" ]; then set -a; source "$ENV_FILE"; set +a; fi
if [ -f "$ROOT/backend/.env" ]; then set -a; source "$ROOT/backend/.env"; set +a; fi  # older setups

# Google login needs two shared secrets; make them once so only the Google ID/secret have to be pasted.
if [ -n "${AUTH_GOOGLE_ID:-}" ]; then
  [ -f "$ENV_FILE" ] || cp "$ROOT/.env.example" "$ENV_FILE"
  for name in AUTH_SECRET INTERNAL_API_SECRET; do
    if [ -z "${!name:-}" ]; then
      value="$(openssl rand -base64 32 | tr -d '\n')"
      if grep -q "^$name=" "$ENV_FILE"; then
        sed -i.bak "s|^$name=.*|$name=$value|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
      else
        echo "$name=$value" >> "$ENV_FILE"
      fi
      export "$name=$value"
      echo "Generated $name in .env"
    fi
  done
  echo "Google login is ON."
else
  echo "Local mode: no login (add AUTH_GOOGLE_ID and AUTH_GOOGLE_SECRET to .env to turn Google login on)."
fi

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
  echo "Setting up the Python environment with $PY…"
  "$PY" -m venv .venv
fi
if [ ! -f .venv/.installed ] || [ requirements.txt -nt .venv/.installed ]; then
  echo "Installing Python packages…"
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
  touch .venv/.installed
fi
if [ ! -f sample_data/lloyds_credit_card.csv ]; then
  .venv/bin/python sample_data/generate.py >/dev/null
fi
.venv/bin/uvicorn app.main:app --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT

# --- frontend ---
cd "$ROOT/frontend"
if ! command -v npm >/dev/null; then
  echo "MoneyMap needs Node.js 20 or newer. On a Mac: brew install node" >&2
  exit 1
fi
if [ ! -f node_modules/.package-lock.json ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
  echo "Installing frontend packages…"
  npm install --silent
fi
echo
echo "MoneyMap is starting: open http://localhost:3000"
echo "(Ctrl+C stops both servers.)"
npm run dev
