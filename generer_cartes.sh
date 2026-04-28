#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "[Compat] Utilisez de preference scripts/linux/generer_cartes.sh"
exec ./scripts/linux/generer_cartes.sh "$@"
