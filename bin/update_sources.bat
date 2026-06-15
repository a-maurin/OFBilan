@echo off
setlocal

:: Se deplacer a la racine du projet
cd /d "%~dp0.."

:: Activer l'environnement Python de QGIS
set "QGIS_PYTHON=C:\Program Files\QGIS 3.44.8\bin\python.exe"
for %%A in ("%QGIS_PYTHON%") do set "OSGEO4W_BIN=%%~dpA"
set "OSGEO4W_ROOT=%OSGEO4W_BIN:~0,-4%"
call "%OSGEO4W_ROOT%\bin\o4w_env.bat"

:: Lancer le script de récupération
echo Lancement du script de recuperation des sources...
"%QGIS_PYTHON%" scripts\fetch_sources.py

pause
endlocal
