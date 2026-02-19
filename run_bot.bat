@echo off
setlocal

python --version >nul 2>&1
if errorlevel 1 (
  echo Python is required but was not found in PATH.
  exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,9) else 'Python 3.9+ is required.')"
if errorlevel 1 exit /b 1

if not exist .env (
  echo .env not found. Running setup wizard first...
  python setup_and_run.py
  exit /b %errorlevel%
)

python -m pip install -r requirements.txt
if errorlevel 1 exit /b %errorlevel%

python -m app.interfaces.telegram_bot
