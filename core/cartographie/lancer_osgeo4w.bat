@echo off
REM Lance l'interface graphique de configuration des cartes
REM en utilisant l'installation OSGeo4W utilisateur.

setlocal

set "OSGEO4W_ROOT=%LOCALAPPDATA%\Programs\OSGeo4W"
if not exist "%OSGEO4W_ROOT%\bin\python.exe" (
    echo OSGeo4W introuvable dans %LOCALAPPDATA%\Programs\OSGeo4W
    echo Verifiez l'installation de QGIS / OSGeo4W.
    pause
    exit /b 1
)

pushd "%~dp0"
call "%OSGEO4W_ROOT%\bin\python-qgis-ltr.bat" "gui_lancement_cartes.py"
popd
pause
exit /b %ERRORLEVEL%
