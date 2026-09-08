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
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "     Lancement du serveur OFBilan" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Recherche de l'interpreteur Python de QGIS..." -ForegroundColor Gray

$qgisPython = $null
$qgisCacheFile = Join-Path $env:LOCALAPPDATA "OFBilan\qgis_path.txt"

# 0. Verification dans le cache local dedie
if (Test-Path $qgisCacheFile) {
    try {
        $cachedPath = (Get-Content $qgisCacheFile -Raw -Encoding UTF8).Trim()
        if ($cachedPath -and (Test-Path $cachedPath)) {
            $qgisPython = $cachedPath
        }
    } catch {}
}

# 1. Verification dans les parametres utilisateur
if (-not $qgisPython) {
    $settingsFiles = @(
        (Join-Path $env:LOCALAPPDATA "OFBilan\user_settings.json"),
        (Join-Path $env:USERPROFILE ".ofbilan\user_settings.json")
    )
    foreach ($userSettings in $settingsFiles) {
        if (Test-Path $userSettings) {
            try {
                $json = Get-Content $userSettings -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($json.tech.qgis_path -and (Test-Path $json.tech.qgis_path)) {
                    $qgisPython = $json.tech.qgis_path
                    break
                }
            } catch {}
        }
    }
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

# Mémorisation dans le cache local pour accélérer les prochains lancements
if ($qgisPython -and $qgisCacheFile) {
    try {
        $cacheDir = Split-Path -Parent $qgisCacheFile
        if (-not (Test-Path $cacheDir)) { [System.IO.Directory]::CreateDirectory($cacheDir) | Out-Null }
        Set-Content -Path $qgisCacheFile -Value $qgisPython -Encoding UTF8 -Force
    } catch {}
}

Write-Host "[OK] Interpreteur trouve : $qgisPython" -ForegroundColor Green
Write-Host ""
Write-Host "[OK] Demarrage du serveur web..." -ForegroundColor Cyan
Write-Host ""

# Cache local du bytecode Python (.pyc) déporté sur C: (aucun conflit ni écriture lente sur réseau)
Remove-Item env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue
$localPycache = Join-Path $env:LOCALAPPDATA "OFBilan\pycache"
if (-not (Test-Path $localPycache)) { [System.IO.Directory]::CreateDirectory($localPycache) | Out-Null }
$env:PYTHONPYCACHEPREFIX = $localPycache

$serveurScript = Join-Path $ProjectRoot "core\web\serveur.py"

$passArgs = @()
if ($env:DEBUG -eq "1" -or $env:OFBILAN_DEBUG -eq "1") {
    $passArgs += "--debug"
}
if ($args) {
    $passArgs += $args
}

Push-Location $env:SystemRoot
try {
    & "$qgisPython" "$serveurScript" $passArgs
} finally {
    Pop-Location
}
