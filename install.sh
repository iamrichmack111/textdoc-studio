#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "python3 required"; exit 1; }
command -v ffmpeg >/dev/null || { echo "Install FFmpeg first: sudo apt install -y ffmpeg python3-venv"; exit 1; }
python3 -m venv .venv
.venv/bin/python -m pip install -U pip setuptools wheel
.venv/bin/pip install -e . -r requirements-studio.txt
mkdir -p studio-data/projects voices
chmod +x run-studio.sh scripts/*.sh
echo "Installed. Add a Piper voice to ./voices and run ./run-studio.sh"
