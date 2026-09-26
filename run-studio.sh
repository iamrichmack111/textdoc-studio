#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Run the documentary renderer from THIS checkout.
export TEXTDOC_ROOT="$ROOT"

# Keep existing Studio projects/media in their current location.
export TEXTDOC_STUDIO_DATA="${TEXTDOC_STUDIO_DATA:-$HOME/textdoc-cli/studio-data}"
if [ -x .venv/bin/python ]; then exec .venv/bin/python run_studio.py; fi
exec python3 run_studio.py
