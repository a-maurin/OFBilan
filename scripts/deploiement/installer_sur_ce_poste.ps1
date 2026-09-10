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
    Script d'installation en un clic pour OFBilan sur le poste client.
.DESCRIPTION
    1. Crée un raccourci de lancement sur le Bureau Windows avec icône.
    2. Installe le relais (stub) OFBilan dans les profils QGIS de l'utilisateur sans aucun droit administrateur.
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "     Installation d'OFBilan sur ce poste         " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "Dossier source detecte : $ProjectRoot" -ForegroundColor Gray
Write-Host ""

# -------------------------------------------------------------
# 1. Creation du raccourci sur le Bureau
# -------------------------------------------------------------
try {
    Write-Host "[1/2] Creation du raccourci sur le Bureau..." -ForegroundColor Yellow
    $desktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
    $shortcutPath = Join-Path $desktopPath "OFBilan.lnk"

    $wshShell = New-Object -ComObject WScript.Shell
    $shortcut = $wshShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "powershell.exe"

    $scriptLauncher = Join-Path $ProjectRoot "scripts\lancement\demarrer_serveur_OFBilan.ps1"
    $shortcut.Arguments = "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptLauncher`""
    $shortcut.WorkingDirectory = $ProjectRoot

    # Copie locale de l'icone dans LOCALAPPDATA (immunite contre restrictions reseau et apostrophes)
    $localIconDir = Join-Path $env:LOCALAPPDATA "OFBilan"
    if (-not (Test-Path $localIconDir)) {
        New-Item -ItemType Directory -Path $localIconDir -Force | Out-Null
    }
    $localIconPath = Join-Path $localIconDir "icon.ico"
    $sourceIcon = Join-Path $ProjectRoot "icon.ico"
    if (Test-Path $sourceIcon) {
        Copy-Item -Path $sourceIcon -Destination $localIconPath -Force
    }
    
    if (Test-Path $localIconPath) {
        $shortcut.IconLocation = "$localIconPath,0"
    }
    $shortcut.Description = "OFBilan - Edition de bilans et cartographie"
    $shortcut.Save()

    # Rafraichissement doux du cache d'icones Windows
    Start-Process -FilePath "ie4uinit.exe" -ArgumentList "-show" -WindowStyle Hidden -ErrorAction SilentlyContinue

    Write-Host "  [OK] Raccourci 'OFBilan' cree sur le Bureau." -ForegroundColor Green
} catch {
    Write-Host "  [ATTENTION] Impossible de creer le raccourci Bureau : $_" -ForegroundColor Red
}

# -------------------------------------------------------------
# 2. Initialisation du miroir local et de la jonction QGIS
# -------------------------------------------------------------
Write-Host ""
Write-Host "[2/2] Configuration de la jonction pour QGIS..." -ForegroundColor Yellow

$LocalAppDir = Join-Path $env:LOCALAPPDATA "OFBilan\app"
$SourceConfigFile = Join-Path $env:LOCALAPPDATA "OFBilan\source_serveur.txt"

function Test-IsNetworkLocation([string]$PathToCheck) {
    if (-not $PathToCheck) { return $false }
    if ($PathToCheck.StartsWith("\\") -or $PathToCheck.StartsWith("//")) { return $true }
    $driveName = Split-Path -Qualifier $PathToCheck
    if ($driveName) {
        $cleanDrive = $driveName.TrimEnd('\')
        $dInfo = [System.IO.DriveInfo]::GetDrives() | Where-Object { $_.Name.TrimEnd('\') -eq $cleanDrive } | Select-Object -First 1
        if ($dInfo -and $dInfo.DriveType -eq [System.IO.DriveType]::Network) {
            return $true
        }
    }
    return $false
}

$isNetwork = Test-IsNetworkLocation $ProjectRoot
if ($isNetwork) {
    Write-Host "  Synchronisation initiale vers le miroir local SSD..." -ForegroundColor Gray
    $cfgDir = Split-Path -Parent $SourceConfigFile
    if (-not (Test-Path $cfgDir)) { [System.IO.Directory]::CreateDirectory($cfgDir) | Out-Null }
    Set-Content -Path $SourceConfigFile -Value $ProjectRoot -Encoding UTF8 -Force

    if (-not (Test-Path $LocalAppDir)) {
        [System.IO.Directory]::CreateDirectory($LocalAppDir) | Out-Null
    }

    $excludeDirs = @(".git", ".github", ".agents", ".cursor", ".gemini", ".vscode", ".idea", ".venv", "venv", "env", "tests", "temp", "distribution", "releases", "demo", "docs\prompts", "ref\hors_programme", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "data")
    $excludeFiles = @("*.pyc", "*.pyo", "*.pyd", "*.log", "*.tmp", "~$*.docx", "*.zip", "*.7z")

    $robocopyArgs = @("$ProjectRoot", "$LocalAppDir", "/MIR", "/FFT", "/MT:8", "/R:1", "/W:1", "/XD") + $excludeDirs + @("/XF") + $excludeFiles + @("/NDL", "/NJH", "/NJS")
    & robocopy @robocopyArgs | Out-Null

    $targetPluginDir = $LocalAppDir
} else {
    $targetPluginDir = $ProjectRoot
}

$profilesBase = Join-Path $env:APPDATA "QGIS\QGIS3\profiles"
$targetProfiles = @()

if (Test-Path $profilesBase) {
    $foundDirs = Get-ChildItem -Path $profilesBase -Directory -ErrorAction SilentlyContinue
    foreach ($d in $foundDirs) {
        $targetProfiles += $d.FullName
    }
}

if ($targetProfiles.Count -eq 0) {
    $targetProfiles += (Join-Path $profilesBase "default")
}

$installedCount = 0
foreach ($pDir in $targetProfiles) {
    try {
        $pluginsDir = Join-Path $pDir "python\plugins"
        if (-not (Test-Path $pluginsDir)) {
            New-Item -ItemType Directory -Path $pluginsDir -Force | Out-Null
        }
        $pluginDest = Join-Path $pluginsDir "OFBilan"

        if (Test-Path -LiteralPath $pluginDest) {
            $destItem = Get-Item -LiteralPath $pluginDest -Force -ErrorAction SilentlyContinue
            if ($destItem -and ($destItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
                [System.IO.Directory]::Delete($pluginDest)
            } else {
                Remove-Item -LiteralPath $pluginDest -Recurse -Force -ErrorAction Stop
            }
        }

        cmd.exe /c "mklink /J `"$pluginDest`" `"$targetPluginDir`"" | Out-Null

        if (Test-Path -LiteralPath $pluginDest) {
            Write-Host "  [OK] Jonction QGIS configuree dans le profil : $(Split-Path $pDir -Leaf)" -ForegroundColor Green
            $installedCount++
        } else {
            Write-Host "  [ATTENTION] La jonction n'a pas pu etre creee dans : $(Split-Path $pDir -Leaf)" -ForegroundColor Red
        }
    } catch {
        Write-Host "  [ATTENTION] Echec sur le profil $pDir : $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "Installation terminee avec succes !" -ForegroundColor Green
Write-Host "Vous pouvez lancer OFBilan depuis l'icone sur votre Bureau." -ForegroundColor White
Write-Host "=================================================" -ForegroundColor Cyan
