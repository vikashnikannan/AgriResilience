#!/usr/bin/env bash
# Creates the project-only environment (.venv inside this folder) and installs everything.
cd "$(dirname "$0")"
[ -x .venv/bin/python ] && { echo ".venv already exists. Use ./run_all.sh"; exit 0; }
python3 -m venv .venv && .venv/bin/python -m pip install --upgrade pip && .venv/bin/python -m pip install -r requirements.txt \
  && echo "Environment ready. Now run ./run_all.sh"
