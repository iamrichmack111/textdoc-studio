#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/pip install -q playwright
.venv/bin/playwright install chromium
.venv/bin/python scripts/screenshots.py
