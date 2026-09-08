#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHON_BIN=""
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "[ERREUR] Impossible de trouver l'interpréteur Python (python3/python)."
    exit 1
fi

exec "$PYTHON_BIN" "$ROOT_DIR/core/point_entree_cli.py" "$@"
