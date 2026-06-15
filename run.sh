#!/usr/bin/env bash
# explainer-engine desktop launcher (macOS / Linux)
set -e
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements.txt 2>/dev/null || true
if python3 -c "import webview" 2>/dev/null; then
  python3 app/desktop.py
else
  echo "Tip: 'pip install pywebview' for a native window. Opening in browser instead."
  python3 app/server.py
fi
