#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but not found in PATH."
  exit 1
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 9):
    raise SystemExit("Python 3.9+ is required.")
print("Python version check passed.")
PY

if [ ! -f .env ]; then
  echo ".env not found. Running setup wizard first..."
  python3 setup_and_run.py
  exit 0
fi

python3 -m pip install -r requirements.txt
python3 -m app.interfaces.telegram_bot
