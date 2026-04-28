#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export PYTHONPATH="$(pwd)/src:${PYTHONPATH:-}"

# Wrapper Linux vers la CLI principale
python3 -m bilans "$@"
