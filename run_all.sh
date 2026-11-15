#!/usr/bin/env bash
# Runs the whole project (creates .venv on first use). Extra options are passed on, e.g.  ./run_all.sh --ee
cd "$(dirname "$0")"
python3 run_all.py "$@"
