<#
.SYNOPSIS
    Lanceur PowerShell robuste et Unicode pour le serveur web OFBilan.
.DESCRIPTION
    Compatible avec les lecteurs réseau partagés (SMB), les chemins avec espaces
    et apostrophes typographiques. Ne nécessite aucun droit administrateur.
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "     Lancement du serveur OFBilan" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Recherche de l'interpreteur Python de QGIS..." -ForegroundColor Gray

$qgisPython = $null

# 1. Verification dans les parametres utilisateur
$userSettings = Join-Path $env:USERPROFILE ".ofbilan\user_settings.json"
if (Test-Path $userSettings) {
    try {
        $json = Get-Content $userSettings -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($json.tech.qgis_path -and (Test-Path $json.tech.qgis_path)) {
            $qgisPython = $json.tech.qgis_path
        }
    } catch {}
}

# 2. Variables d'environnement
if (-not $qgisPython -and $env:QGIS_PYTHON -and (Test-Path $env:QGIS_PYTHON)) {
    $qgisPython = $env:QGIS_PYTHON
}

# 3. Parcours des Program Files par version decroissante
if (-not $qgisPython) {
    $candidates = @()
    $pfs = @()
    $pf = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::ProgramFiles)
    if ($pf) { $pfs += $pf }
    $pf86 = ${env:ProgramFiles(x86)}
    if ($pf86) { $pfs += $pf86 }

    foreach ($p in $pfs) {
        if (Test-Path $p) {
            $qdirs = Get-ChildItem -Path $p -Filter "QGIS*" -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending
            foreach ($qd in $qdirs) {
                $batLtr = Join-Path $qd.FullName "bin\python-qgis-ltr.bat"
                $batStd = Join-Path $qd.FullName "bin\python-qgis.bat"
                $pyExe = Join-Path $qd.FullName "bin\python.exe"
                if (Test-Path $batLtr) { $candidates += $batLtr }
                elseif (Test-Path $batStd) { $candidates += $batStd }
                elseif (Test-Path $pyExe) { $candidates += $pyExe }
            }
        }
    }
    if ($candidates.Count -gt 0) {
        $qgisPython = $candidates[0]
    }
}

# 4. Fallbacks OSGeo4W
if (-not $qgisPython) {
    $fallbacks = @(
        "$env:LOCALAPPDATA\Programs\OSGeo4W\bin\python-qgis-ltr.bat",
        "$env:LOCALAPPDATA\Programs\OSGeo4W\bin\python-qgis.bat",
        "C:\OSGeo4W64\bin\python-qgis-ltr.bat",
        "C:\OSGeo4W\bin\python-qgis-ltr.bat"
    )
    foreach ($fb in $fallbacks) {
        if (Test-Path $fb) {
            $qgisPython = $fb
            break
        }
    }
}

if (-not $qgisPython) {
    Write-Host "[ERREUR] Impossible de trouver l'interpreteur Python de QGIS." -ForegroundColor Red
    Write-Host "Veuillez verifier que QGIS est installe sur ce poste." -ForegroundColor Yellow
    Read-Host "Appuyez sur Entree pour quitter..."
    exit 1
}

Write-Host "[OK] Interpreteur trouve : $qgisPython" -ForegroundColor Green
Write-Host ""
Write-Host "[OK] Demarrage du serveur web..." -ForegroundColor Cyan
Write-Host ""

$env:PYTHONDONTWRITEBYTECODE = "1"
$serveurScript = Join-Path $ProjectRoot "core\web\serveur.py"

$passArgs = @()
if ($env:DEBUG -eq "1" -or $env:OFBILAN_DEBUG -eq "1") {
    $passArgs += "--debug"
}
if ($args) {
    $passArgs += $args
}

& "$qgisPython" "$serveurScript" $passArgs
