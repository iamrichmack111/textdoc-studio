#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m py_compile textdoc_studio/app.py textdoc/documentary_v4.py textdoc/cinematic_v4.py textdoc/director_v4.py
python3 -c "from textdoc_studio import create_app; a=create_app(); r={str(x) for x in a.url_map.iter_rules()}; need={'/','/api/projects','/api/project/<pid>/render','/api/project/<pid>/render/restart','/download/<pid>/video','/download/<pid>/audio'}; assert not need-r, need-r; print('route smoke test passed')"
