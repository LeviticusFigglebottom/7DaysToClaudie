#!/usr/bin/env bash
# Creates the asset-pipeline virtualenv at .tools/venv with pinned requirements.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="$ROOT/.tools/venv"
PY="${PYTHON:-python3}"
if [[ ! -x "$VENV/bin/python" ]]; then
  "$PY" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install -q --upgrade pip
"$VENV/bin/python" -m pip install -q -r "$ROOT/tools/requirements.txt"
"$VENV/bin/python" -c "import numpy, scipy, PIL; print('[python] venv ok: numpy', numpy.__version__, 'scipy', scipy.__version__, 'Pillow', PIL.__version__)"
