<#
.SYNOPSIS
    Preparation d'un package allege pour deploiement reseau (OFBilan).
#>
param (
    [string]$Destination = "$env:USERPROFILE\Desktop\OFBilan_Deploy"
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "Preparation du package vers : $Destination" -ForegroundColor Cyan

if (Test-Path $Destination) {
    Remove-Item -Recurse -Force $Destination
}
New-Item -ItemType Directory -Path $Destination -Force | Out-Null

# Exclusions explicites pour Robocopy (chemins absolus)
$excludeDirs = @(
    (Join-Path $ProjectRoot ".git"),
    (Join-Path $ProjectRoot ".github"),
    (Join-Path $ProjectRoot ".pytest_cache"),
    (Join-Path $ProjectRoot ".venv"),
    (Join-Path $ProjectRoot "tests"),
    (Join-Path $ProjectRoot "temp"),
    (Join-Path $ProjectRoot "distribution"),
    (Join-Path $ProjectRoot "data\sources"),
    (Join-Path $ProjectRoot "data\sources_archive"),
    (Join-Path $ProjectRoot "data\out"),
    (Join-Path $ProjectRoot "data\cache"),
    "__pycache__"
)

$robocopyArgs = @(
    "$ProjectRoot",
    "$Destination",
    "/E",
    "/XD"
) + $excludeDirs + @(
    "/XF", "*.pyc", "*.pyo", "*.tmp", "geojson_error.log",
    "/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np"
)

& robocopy @robocopyArgs | Out-Null

# Recreer les dossiers vides requis pour l'arborescence
New-Item -ItemType Directory -Path "$Destination\data\sources" -Force | Out-Null
New-Item -ItemType File -Path "$Destination\data\sources\.gitkeep" -Force | Out-Null
New-Item -ItemType Directory -Path "$Destination\data\out" -Force | Out-Null
New-Item -ItemType File -Path "$Destination\data\out\.gitkeep" -Force | Out-Null

Write-Host "[OK] Package allege pret dans : $Destination" -ForegroundColor Green
Write-Host "Vous pouvez copier ce dossier sur votre lecteur reseau R:." -ForegroundColor Green
