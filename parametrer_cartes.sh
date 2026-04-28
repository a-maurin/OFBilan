#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

echo "[Compat] Utilisez de preference scripts/linux/parametrer_cartes.sh"
exec ./scripts/linux/parametrer_cartes.sh "$@"