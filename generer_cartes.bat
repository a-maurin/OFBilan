@echo off
setlocal
cd /d "%~dp0"

echo [Compat] Utilisez de preference scripts\windows\generer_cartes.bat
call scripts\windows\generer_cartes.bat %*
exit /b %errorlevel%
