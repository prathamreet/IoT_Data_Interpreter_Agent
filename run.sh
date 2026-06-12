#!/usr/bin/env bash
# ── One-command launcher (macOS / Linux) ─────────────────────────────
# Usage:  ./run.sh
set -euo pipefail

echo "IoT Data Interpreter Agent — setup & launch"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment (.venv)..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies..."
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env (no API key required — runs in offline mode)."
fi

echo ""
echo "Starting server at http://127.0.0.1:8000  (Ctrl+C to stop)"
echo ""
uvicorn backend.main:app --host 127.0.0.1 --port 8000
