@echo off
REM explainer-engine desktop launcher (Windows)
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python -c "import webview" 2>NUL
if %errorlevel%==0 (
  python app\desktop.py
) else (
  echo Tip: pip install pywebview  for a native window. Opening in browser instead.
  python app\server.py
)
