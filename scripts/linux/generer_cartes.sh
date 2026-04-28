#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export PYTHONPATH="$(pwd)/src:${PYTHONPATH:-}"

# Wrapper Linux pour la génération de cartes
python3 src/bilans/cartographie/generer_cartes.py "$@"
