@echo off
chcp 65001 >nul
pushd "%~dp0"

echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deployer_vers_serveur.ps1" %*
if errorlevel 1 (
    echo.
    echo [ERREUR] Le deploiement a rencontre un probleme.
)

echo.
pause
popd
