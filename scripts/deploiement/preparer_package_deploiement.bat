@echo off
chcp 65001 >nul
pushd "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0preparer_package_deploiement.ps1" %*

popd
pause
