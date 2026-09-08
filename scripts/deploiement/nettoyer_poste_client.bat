@echo off
chcp 65001 >nul
pushd "%~dp0"

echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0nettoyer_poste_client.ps1" %*
if errorlevel 1 (
    echo.
    echo [ERREUR] Le nettoyage a rencontre un probleme.
)

echo.
pause
popd
