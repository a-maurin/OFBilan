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
