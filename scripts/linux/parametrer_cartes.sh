#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export PYTHONPATH="$(pwd)/src:${PYTHONPATH:-}"

# Wrapper Linux pour l'interface de configuration cartographique
python3 src/bilans/cartographie/gui_config_cartes.py "$@"
