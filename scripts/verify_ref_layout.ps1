# Vérifie ref/programme et ref/hors_programme (appelle verify_ref_layout.py).
# Usage : .\scripts\verify_ref_layout.ps1 [-RepoRoot "C:\chemin\Bilans_production"]

param(
    [string]$RepoRoot = ""
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyScript = Join-Path $scriptDir "verify_ref_layout.py"

if (-not (Test-Path $pyScript)) {
    Write-Error "Script introuvable : $pyScript"
    exit 1
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python introuvable dans le PATH."
    exit 1
}

$args = @($pyScript)
if (-not [string]::IsNullOrWhiteSpace($RepoRoot)) {
    $args += $RepoRoot
}

& $python.Source @args
exit $LASTEXITCODE
