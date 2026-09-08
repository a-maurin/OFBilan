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
# 2. Installation du relais QGIS (Stub)
# -------------------------------------------------------------
Write-Host ""
Write-Host "[2/2] Configuration du relais pour QGIS..." -ForegroundColor Yellow

$profilesBase = Join-Path $env:APPDATA "QGIS\QGIS3\profiles"
$targetProfiles = @()

if (Test-Path $profilesBase) {
    $foundDirs = Get-ChildItem -Path $profilesBase -Directory -ErrorAction SilentlyContinue
    foreach ($d in $foundDirs) {
        $targetProfiles += $d.FullName
    }
}

if ($targetProfiles.Count -eq 0) {
    # Profil default par defaut
    $targetProfiles += (Join-Path $profilesBase "default")
}

$stubCode = @"
# -*- coding: utf-8 -*-
# Relais dynamique d'OFBilan vers le lecteur reseau
import os
import sys
import json
from pathlib import Path

def _get_source_path():
    cfg = Path(__file__).resolve().parent / "stub_config.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            src = data.get("source_path")
            if src and Path(src).exists():
                return Path(src)
        except Exception:
            pass
    return None

def classFactory(iface):
    src = _get_source_path()
    if not src:
        from qgis.PyQt.QtWidgets import QMessageBox
        QMessageBox.critical(
            iface.mainWindow(),
            "OFBilan - Source introuvable",
            "Le dossier source d'OFBilan sur le reseau est inaccessible.\n"
            "Verifiez que votre lecteur reseau est bien connecte."
        )
        class DummyPlugin:
            def __init__(self, iface): pass
            def initGui(self): pass
            def unload(self): pass
        return DummyPlugin(iface)

    src_str = str(src)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

    # Verification et auto-mise a jour du fichier metadata.txt
    try:
        src_meta = src / "metadata.txt"
        dst_meta = Path(__file__).resolve().parent / "metadata.txt"
        if src_meta.exists() and dst_meta.exists():
            if src_meta.read_text(encoding="utf-8") != dst_meta.read_text(encoding="utf-8"):
                dst_meta.write_text(src_meta.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception:
        pass

    import ofbilan_plugin
    return ofbilan_plugin.OFBilanPlugin(iface)
"@

$installedCount = 0
foreach ($pDir in $targetProfiles) {
    try {
        $pluginDest = Join-Path $pDir "python\plugins\OFBilan"
        if (-not (Test-Path $pluginDest)) {
            New-Item -ItemType Directory -Path $pluginDest -Force | Out-Null
        }

        # 1. Fichier stub_config.json
        $cfgFile = Join-Path $pluginDest "stub_config.json"
        $cfgJson = @{ source_path = $ProjectRoot } | ConvertTo-Json
        [System.IO.File]::WriteAllText($cfgFile, $cfgJson, [System.Text.Encoding]::UTF8)

        # 2. Fichier __init__.py du relais
        $initFile = Join-Path $pluginDest "__init__.py"
        [System.IO.File]::WriteAllText($initFile, $stubCode, [System.Text.Encoding]::UTF8)

        # 3. Copie du metadata.txt
        $srcMeta = Join-Path $ProjectRoot "metadata.txt"
        if (Test-Path $srcMeta) {
            Copy-Item -Path $srcMeta -Destination (Join-Path $pluginDest "metadata.txt") -Force
        }

        Write-Host "  [OK] Relais configure dans le profil : $(Split-Path $pDir -Leaf)" -ForegroundColor Green
        $installedCount++
    } catch {
        Write-Host "  [ATTENTION] Echec sur le profil $pDir : $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "Installation terminee avec succes !" -ForegroundColor Green
Write-Host "Vous pouvez lancer OFBilan depuis l'icone sur votre Bureau." -ForegroundColor White
Write-Host "=================================================" -ForegroundColor Cyan
