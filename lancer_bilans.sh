#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "[Compat] Utilisez de preference scripts/linux/lancer_bilans.sh"
exec ./scripts/linux/lancer_bilans.sh "$@"
