@echo off
setlocal
cd /d "%~dp0\..\.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

echo ===============================================
echo   OFBilan - Demarrage de l'interface graphique
echo ===============================================
echo.
echo Lancement du serveur local sur http://localhost:8000 ...
echo Appuyez sur Ctrl+C dans cette fenetre pour arreter.
echo.

start http://localhost:8000
python src/ofbilan/web/serveur.py <nul

endlocal
