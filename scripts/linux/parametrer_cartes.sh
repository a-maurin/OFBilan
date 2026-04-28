#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

# Wrapper Linux pour l'interface de configuration cartographique
python3 scripts/generateur_de_cartes/gui_config_cartes.py "$@"
