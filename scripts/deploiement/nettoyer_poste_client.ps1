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
    Script de nettoyage complet du poste client pour OFBilan.
.DESCRIPTION
    Supprime toutes les traces locales du programme (raccourcis Bureau, cache,
    paramètres utilisateur, relais QGIS et exports) afin de simuler l'état d'un
    poste vierge n'ayant jamais installé OFBilan.
#>
param (
    [switch]$Force
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "      Nettoyage complet du poste client          " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verification de QGIS en cours d'execution
$qgisProcesses = Get-Process -Name "qgis", "qgis-bin" -ErrorAction SilentlyContinue
if ($qgisProcesses) {
    Write-Host "[ATTENTION] QGIS est actuellement ouvert sur votre poste." -ForegroundColor Yellow
    Write-Host "Il est vivement recommande de fermer QGIS pour permettre la suppression des relais." -ForegroundColor Yellow
    Write-Host ""
}

# 2. Confirmation utilisateur
if (-not $Force) {
    Write-Host "Cette operation va supprimer :" -ForegroundColor White
    Write-Host " - Les raccourcis Bureau (OFBilan.lnk, Serveur OFBilan.lnk)" -ForegroundColor Gray
    Write-Host " - Les donnees locales et caches (%LOCALAPPDATA%\OFBilan)" -ForegroundColor Gray
    Write-Host " - Les preferences de l'utilisateur (~/.ofbilan)" -ForegroundColor Gray
    Write-Host " - Les relais QGIS dans tous les profils utilisateur" -ForegroundColor Gray
    Write-Host " - Le dossier des bilans generes (Documents\OFBilan_Exports)" -ForegroundColor Gray
    Write-Host ""
    
    $confirmation = Read-Host "Confirmez-vous la reinitialisation complete de ce poste ? (O/N)"
    if ($confirmation -notmatch "^[oOyY]") {
        Write-Host ""
        Write-Host "Nettoyage annule. Aucune modification effectuee." -ForegroundColor Yellow
        exit 0
    }
    Write-Host ""
}

# 3. Arret des processus serveur OFBilan en arriere-plan
Write-Host "[1/5] Arret des processus serveur OFBilan..." -ForegroundColor Yellow
$stoppedServers = 0
try {
    $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "serveur\.py|web_api\.py" -and $_.ProcessId -ne $PID }
    foreach ($proc in $processes) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
        $stoppedServers++
    }
    if ($stoppedServers -gt 0) {
        Write-Host "  [OK] $stoppedServers processus serveur arrete(s)." -ForegroundColor Green
    } else {
        Write-Host "  [INFO] Aucun serveur OFBilan actif detecte." -ForegroundColor Gray
    }
} catch {
    Write-Host "  [INFO] Verification des processus effectuee." -ForegroundColor Gray
}

# 4. Suppression des raccourcis Bureau
Write-Host ""
Write-Host "[2/5] Suppression des raccourcis Bureau..." -ForegroundColor Yellow
$desktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$shortcuts = @(
    (Join-Path $desktopPath "OFBilan.lnk"),
    (Join-Path $desktopPath "Serveur OFBilan.lnk")
)
foreach ($lnk in $shortcuts) {
    if (Test-Path -LiteralPath $lnk) {
        try {
            Remove-Item -LiteralPath $lnk -Force -ErrorAction Stop
            Write-Host "  [OK] Raccourci supprime : $(Split-Path $lnk -Leaf)" -ForegroundColor Green
        } catch {
            Write-Host "  [ATTENTION] Impossible de supprimer $lnk : $_" -ForegroundColor Red
        }
    } else {
        Write-Host "  [INFO] Raccourci absent : $(Split-Path $lnk -Leaf)" -ForegroundColor Gray
    }
}

# 5. Suppression des donnees locales et caches
Write-Host ""
Write-Host "[3/5] Suppression des caches et donnees locales..." -ForegroundColor Yellow
$localAppDataDir = Join-Path $env:LOCALAPPDATA "OFBilan"
if (Test-Path -LiteralPath $localAppDataDir) {
    try {
        Remove-Item -LiteralPath $localAppDataDir -Recurse -Force -ErrorAction Stop
        Write-Host "  [OK] Dossier supprime : %LOCALAPPDATA%\OFBilan" -ForegroundColor Green
    } catch {
        Write-Host "  [ATTENTION] Echec lors de la suppression de $localAppDataDir : $_" -ForegroundColor Red
    }
} else {
    Write-Host "  [INFO] Dossier absent : %LOCALAPPDATA%\OFBilan" -ForegroundColor Gray
}

$userSettingsDir = Join-Path $env:USERPROFILE ".ofbilan"
if (Test-Path -LiteralPath $userSettingsDir) {
    try {
        Remove-Item -LiteralPath $userSettingsDir -Recurse -Force -ErrorAction Stop
        Write-Host "  [OK] Dossier supprime : ~/.ofbilan" -ForegroundColor Green
    } catch {
        Write-Host "  [ATTENTION] Echec lors de la suppression de $userSettingsDir : $_" -ForegroundColor Red
    }
} else {
    Write-Host "  [INFO] Dossier absent : ~/.ofbilan" -ForegroundColor Gray
}

# 6. Suppression des relais QGIS
Write-Host ""
Write-Host "[4/5] Suppression des relais dans les profils QGIS..." -ForegroundColor Yellow
$profilesBase = Join-Path $env:APPDATA "QGIS\QGIS3\profiles"
if (Test-Path -LiteralPath $profilesBase) {
    $profiles = Get-ChildItem -LiteralPath $profilesBase -Directory -ErrorAction SilentlyContinue
    $removedRelays = 0
    foreach ($p in $profiles) {
        $pluginDir = Join-Path $p.FullName "python\plugins\OFBilan"
        if (Test-Path -LiteralPath $pluginDir) {
            try {
                $dirInfo = Get-Item -LiteralPath $pluginDir -Force -ErrorAction SilentlyContinue
                if ($dirInfo -and ($dirInfo.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
                    [System.IO.Directory]::Delete($pluginDir)
                } else {
                    Remove-Item -LiteralPath $pluginDir -Recurse -Force -ErrorAction Stop
                }
                Write-Host "  [OK] Extension / jonction supprimee dans le profil : $($p.Name)" -ForegroundColor Green
                $removedRelays++
            } catch {
                Write-Host "  [ATTENTION] Impossible de supprimer l'extension dans $($p.Name) : $_" -ForegroundColor Red
            }
        }
    }
    if ($removedRelays -eq 0) {
        Write-Host "  [INFO] Aucun relais OFBilan trouve dans les profils QGIS." -ForegroundColor Gray
    }
} else {
    Write-Host "  [INFO] Aucun profil QGIS detecte sur ce poste." -ForegroundColor Gray
}

# 7. Suppression du dossier des exports
Write-Host ""
Write-Host "[5/5] Suppression du dossier des exports..." -ForegroundColor Yellow
$myDocs = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::MyDocuments)
$exportsDir = Join-Path $myDocs "OFBilan_Exports"
if (Test-Path -LiteralPath $exportsDir) {
    try {
        Remove-Item -LiteralPath $exportsDir -Recurse -Force -ErrorAction Stop
        Write-Host "  [OK] Dossier supprime : Documents\OFBilan_Exports" -ForegroundColor Green
    } catch {
        Write-Host "  [ATTENTION] Echec lors de la suppression de $exportsDir : $_" -ForegroundColor Red
    }
} else {
    Write-Host "  [INFO] Dossier absent : Documents\OFBilan_Exports" -ForegroundColor Gray
}

# Rafraichissement de l'affichage du Bureau
Start-Process -FilePath "ie4uinit.exe" -ArgumentList "-show" -WindowStyle Hidden -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "Le poste a ete integralement nettoye avec succes." -ForegroundColor Green
Write-Host "Il est maintenant dans l'etat d'un poste vierge." -ForegroundColor White
Write-Host "=================================================" -ForegroundColor Cyan
