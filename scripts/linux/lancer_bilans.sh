#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

# Wrapper Linux vers la CLI principale
python3 -m bilans "$@"
