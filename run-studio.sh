#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [ -x .venv/bin/python ]; then exec .venv/bin/python run_studio.py; fi
exec python3 run_studio.py
