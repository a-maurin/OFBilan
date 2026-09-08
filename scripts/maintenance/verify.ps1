# Vérification locale identique à la CI (tests unit + smoke).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
