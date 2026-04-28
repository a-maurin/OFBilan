@echo off
setlocal
cd /d "%~dp0"

echo [Compat] Utilisez de preference scripts\windows\lancer_bilans.bat
call scripts\windows\lancer_bilans.bat %*
exit /b %errorlevel%
