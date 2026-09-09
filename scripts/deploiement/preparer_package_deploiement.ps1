# Copyright (C) 2026 Aguirre MAURIN
#
# Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
# selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
# la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
#
# Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ;
# sans même la garantie implicite de QUALITÉ MARCHANDE ou D'ADÉQUATION À UN USAGE PARTICULIER.
# Voir la Licence Publique Générale GNU pour plus de détails.
#
# CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
# Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
# intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
# clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
# doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
# de l'auteur original (Aguirre MAURIN).

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
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

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
