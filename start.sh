#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--help" ]]; then
  echo 'THISTLE browser. Usage: thistle [--private] [URL or file ...]'
  exit 0
fi
export THISTLE_CWD="$PWD"  # relative file arguments resolve from where the user ran it
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ "$EUID" -eq 0 ]]; then
  echo 'Run THISTLE as your normal desktop user, not with sudo.' >&2
  exit 1
fi
if python3 -c 'from PySide6.QtWebEngineWidgets import QWebEngineView; from PySide6.QtCore import qVersion; assert tuple(map(int,qVersion().split(".")[:2])) >= (6,10)' >/dev/null 2>&1; then
  exec python3 thistle.py "$@"
fi
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'from PySide6.QtWebEngineWidgets import QWebEngineView' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -r requirements.txt
fi
exec .venv/bin/python thistle.py "$@"
