#!/usr/bin/env bash
# Vérification locale identique à la CI (tests unit + smoke).
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest -q
