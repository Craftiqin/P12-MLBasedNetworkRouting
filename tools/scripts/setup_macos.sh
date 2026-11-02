#!/bin/sh
set -eu
command -v python3.11 >/dev/null 2>&1 || { echo "Python 3.11 missing; install it first." >&2; exit 1; }
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/validation/validate_environment.py --python-only
