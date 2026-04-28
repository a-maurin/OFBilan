#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

# Wrapper Linux pour la génération de cartes
python3 scripts/generer_cartes.py "$@"
