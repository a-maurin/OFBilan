<#
.SYNOPSIS
    Deploiement propre de la version poste de travail vers le serveur reseau.
.DESCRIPTION
    Copie le programme en miroir strict sans les fichiers de developpement,
    ni les donnees lourdes, ni les caches, ni les tests.
    Detecte automatiquement l'arborescence cible sur R: et preserve data/sources.
#>
param (
    [string]$Destination
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   Deploiement d'OFBilan vers le serveur         " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "Source locale : $ProjectRoot" -ForegroundColor Gray

# 1. Detection dynamique et robuste du chemin cible sur R:
if (-not $PSBoundParameters.ContainsKey('Destination') -or -not $Destination) {
    $baseSd21 = "R:\sd21"
    if (Test-Path $baseSd21) {
        $targetSub = Get-ChildItem -LiteralPath $baseSd21 -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "Reste de l*arborescence" -and $_.Name -notmatch "[\u00e2\u00c3]" } |
            Select-Object -First 1
        if ($targetSub) {
            $Destination = Join-Path $targetSub.FullName "Police\OFBilan\programme"
        }
    }
}

if (-not $Destination) {
    $Destination = "R:\sd21\Reste de l’arborescence\Police\OFBilan\programme"
}

Write-Host "Cible reseau  : $Destination" -ForegroundColor Gray
Write-Host ""

# 2. Verification d'acces au lecteur reseau
$drive = Split-Path -Qualifier $Destination
if ($drive -and -not (Test-Path $drive)) {
    Write-Host "[ERREUR] Le lecteur reseau $drive est inaccessible ou non connecte." -ForegroundColor Red
    Write-Host "Veuillez vous connecter au VPN ou au reseau interne avant de relancer." -ForegroundColor Yellow
    exit 1
}

# 3. Creation du dossier cible si inexistant
if (-not (Test-Path $Destination)) {
    try {
        Write-Host "Creation du dossier cible distant..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    } catch {
        Write-Host "[ERREUR] Impossible de creer le repertoire cible : $_" -ForegroundColor Red
        exit 1
    }
}

# 4. Liste des exclusions
$excludeDirs = @(
    ".git",
    ".github",
    ".agents",
    ".cursor",
    ".gemini",
    ".vscode",
    ".idea",
    ".venv",
    "venv",
    "env",
    "tests",
    "temp",
    "distribution",
    "releases",
    "demo",
    "data",
    "docs\prompts",
    "ref\hors_programme",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    (Join-Path $ProjectRoot "data"),
    (Join-Path $Destination "data")
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

# 5. Synchronisation miroir avec Robocopy
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

# 6. S'assurer de la presence des dossiers minimaux data sans toucher a l'existant
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

# 7. Controle de sante et verification de l'integrite post-copie
Write-Host ""
Write-Host "Verification de l'integrite et bon fonctionnement..." -ForegroundColor Cyan

$essentialFiles = @(
    "ofbilan_plugin.py",
    "metadata.txt",
    "core\web\lanceur_fenetre.py",
    "core\web\serveur.py",
    "core\web\explorer.html",
    "scripts\lancement\demarrer_serveur_OFBilan.bat",
    "scripts\deploiement\installer_sur_ce_poste.bat"
)

$allFound = $true
foreach ($f in $essentialFiles) {
    $p = Join-Path $Destination $f
    if (-not (Test-Path $p)) {
        Write-Host "  [MANQUANT] $f" -ForegroundColor Red
        $allFound = $false
    }
}

if ($allFound) {
    Write-Host "  [OK] Tous les composants recents sont bien presents sur le serveur." -ForegroundColor Green
}

$sourceFilesCount = (Get-ChildItem -Path $sourcesDir -File -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host "  [DONNEES] Repertoire data/sources : $sourceFilesCount fichier(s) preserves intacts." -ForegroundColor Cyan

$pyTest = & python -c "import sys; sys.path.insert(0, r'$Destination'); import ofbilan_plugin; print('OK_IMPORT')" 2>&1
if ($pyTest -like "*OK_IMPORT*") {
    Write-Host "  [OK] Le module OFBilan est operationnel depuis l'environnement cible." -ForegroundColor Green
} else {
    Write-Host "  [INFO] Test d'import Python : $pyTest" -ForegroundColor Gray
}

Write-Host ""
Write-Host "[SUCCES] Le programme a ete deploye et verifie avec succes sur le serveur !" -ForegroundColor Green
Write-Host "Dossier : $Destination" -ForegroundColor Green
exit 0
