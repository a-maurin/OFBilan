<#
.SYNOPSIS
    Deploiement propre de la version poste de travail vers le serveur reseau.
.DESCRIPTION
    Copie le programme en miroir strict sans les fichiers de developpement,
    ni les donnees lourdes, ni les caches, ni les tests.
#>
param (
    [string]$Destination = "R:\sd21\Reste de l’arborescence\Police\OFBilan\programme"
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   Deploiement d'OFBilan vers le serveur         " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "Source locale : $ProjectRoot" -ForegroundColor Gray
Write-Host "Cible reseau  : $Destination" -ForegroundColor Gray
Write-Host ""

# 1. Verification d'acces au lecteur reseau
$drive = Split-Path -Qualifier $Destination
if ($drive -and -not (Test-Path $drive)) {
    Write-Host "[ERREUR] Le lecteur reseau $drive est inaccessible ou non connecte." -ForegroundColor Red
    Write-Host "Veuillez vous connecter au VPN ou au reseau interne avant de relancer." -ForegroundColor Yellow
    exit 1
}

# 2. Creation du dossier cible si inexistant
if (-not (Test-Path $Destination)) {
    try {
        Write-Host "Creation du dossier cible distant..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    } catch {
        Write-Host "[ERREUR] Impossible de creer le repertoire cible : $_" -ForegroundColor Red
        exit 1
    }
}

# 3. Liste des exclusions
$excludeDirs = @(
    (Join-Path $ProjectRoot ".git"),
    (Join-Path $ProjectRoot ".github"),
    (Join-Path $ProjectRoot ".agents"),
    (Join-Path $ProjectRoot ".cursor"),
    (Join-Path $ProjectRoot ".gemini"),
    (Join-Path $ProjectRoot ".vscode"),
    (Join-Path $ProjectRoot ".idea"),
    (Join-Path $ProjectRoot ".venv"),
    (Join-Path $ProjectRoot "venv"),
    (Join-Path $ProjectRoot "env"),
    (Join-Path $ProjectRoot "tests"),
    (Join-Path $ProjectRoot "temp"),
    (Join-Path $ProjectRoot "distribution"),
    (Join-Path $ProjectRoot "releases"),
    (Join-Path $ProjectRoot "demo"),
    (Join-Path $ProjectRoot "data"),
    (Join-Path $ProjectRoot "docs\prompts"),
    (Join-Path $ProjectRoot "ref\hors_programme"),
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache"
)

$excludeFiles = @(
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.log",
    "*.tmp",
    "~$*.docx",
    "carte_code.md",
    "*.zip",
    "*.7z",
    ".gitignore",
    ".gitattributes",
    "*.code-workspace",
    "_*.json",
    "deployer_vers_serveur.ps1",
    "deployer_vers_serveur.bat",
    "preparer_package_deploiement.ps1",
    "preparer_package_deploiement.bat"
)

# 4. Synchronisation miroir avec Robocopy
Write-Host "Synchronisation en cours..." -ForegroundColor Yellow

$robocopyArgs = @(
    "$ProjectRoot",
    "$Destination",
    "/MIR",
    "/R:2",
    "/W:3",
    "/FFT",
    "/XD"
) + $excludeDirs + @(
    "/XF"
) + $excludeFiles + @(
    "/NP",
    "/NDL"
)

& robocopy @robocopyArgs
$exitCode = $LASTEXITCODE

# Codes de retour Robocopy : 0 a 7 representent un succes de transfert
if ($exitCode -ge 8) {
    Write-Host ""
    Write-Host "[ERREUR] Echec du deploiement (code retour Robocopy : $exitCode)." -ForegroundColor Red
    exit $exitCode
}

# 5. Creation des dossiers de travail minimaux attendus par l'application
$sourcesDir = Join-Path $Destination "data\sources"
$outDir = Join-Path $Destination "data\out"

if (-not (Test-Path $sourcesDir)) {
    New-Item -ItemType Directory -Path $sourcesDir -Force | Out-Null
}
$sourcesGitkeep = Join-Path $sourcesDir ".gitkeep"
if (-not (Test-Path $sourcesGitkeep)) {
    New-Item -ItemType File -Path $sourcesGitkeep -Force | Out-Null
}

if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}
$outGitkeep = Join-Path $outDir ".gitkeep"
if (-not (Test-Path $outGitkeep)) {
    New-Item -ItemType File -Path $outGitkeep -Force | Out-Null
}

Write-Host ""
Write-Host "[SUCCES] Le programme a ete deploye avec succes sur le serveur !" -ForegroundColor Green
Write-Host "Dossier : $Destination" -ForegroundColor Green
exit 0
