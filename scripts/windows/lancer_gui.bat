@echo off
setlocal
cd /d "%~dp0\..\.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

echo ===============================================
echo   OFBilan - Demarrage de l'interface graphique
echo ===============================================
echo.
echo Lancement du serveur local sur http://localhost:8000 ...
echo Ouverture dans une nouvelle fenetre pour eviter l'invite cmd.exe
echo.

start http://localhost:8000/explorer.html
start "Serveur OFBilan" python src/ofbilan/web/serveur.py

endlocal
