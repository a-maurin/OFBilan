@echo off
setlocal
cd /d "%~dp0"

echo [Compat] Utilisez de preference scripts\windows\parametrer_cartes.bat
call scripts\windows\parametrer_cartes.bat %*
exit /b %errorlevel%
