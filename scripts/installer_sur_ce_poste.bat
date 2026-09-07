@echo off
chcp 65001 >nul
pushd "%~dp0"

echo =================================================
echo     Installation d'OFBilan sur ce poste
echo =================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer_sur_ce_poste.ps1"
if errorlevel 1 (
    echo.
    echo [ERREUR] L'installation a rencontre un probleme.
)

echo.
pause
popd
