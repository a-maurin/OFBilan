@echo off
setlocal EnableDelayedExpansion
REM Lancer python -m bilans avec le Python QGIS / OSGeo4W (PyQGIS pour cartes adaptatives).
REM Sans argument : saisie interactive deleguee entierement a python -m bilans.
REM Detection calquee sur src\bilans\cartographie\lancer_production_cartographique.bat

set "QGIS_PYTHON="
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "PF=C:\Program Files"
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\.."
set "CARTO_DIR=%PROJECT_ROOT%\src\bilans\cartographie\"

REM 0. Priorite : OSGeo4W AppData
set "LOCALAPPDATA_OSGEO=%LOCALAPPDATA%\Programs\OSGeo4W"
if exist "%LOCALAPPDATA_OSGEO%\bin\python.exe" (
    set "QGIS_PYTHON=%LOCALAPPDATA_OSGEO%\bin\python.exe"
    call :configure_osgeo4w_env
    goto :run_bilans
)

REM 1. Priorite : QGIS 3.40.x
if exist "%PF%\QGIS 3.40.15\bin\python.exe" set "QGIS_PYTHON=%PF%\QGIS 3.40.15\bin\python.exe"
if "!QGIS_PYTHON!"=="" if exist "%PF%\QGIS 3.40.15\bin\python3.exe" set "QGIS_PYTHON=%PF%\QGIS 3.40.15\bin\python3.exe"
if "!QGIS_PYTHON!"=="" (
    for /f "delims=" %%p in ('dir "%PF%\QGIS 3.40.15\apps\Python*" /b /ad 2^>nul') do (
        if exist "%PF%\QGIS 3.40.15\apps\%%p\python.exe" set "QGIS_PYTHON=%PF%\QGIS 3.40.15\apps\%%p\python.exe"
    )
)
if "!QGIS_PYTHON!"=="" if exist "%PF%\QGIS 3.40.15\osgeo4w\bin\python.exe" set "QGIS_PYTHON=%PF%\QGIS 3.40.15\osgeo4w\bin\python.exe"

REM 2. Autres versions QGIS
if "!QGIS_PYTHON!"=="" for /f "delims=" %%d in ('dir "%PF%\QGIS*" /b /ad /o-n 2^>nul') do (
    if "!QGIS_PYTHON!"=="" if exist "%PF%\%%d\bin\python.exe" set "QGIS_PYTHON=%PF%\%%d\bin\python.exe"
)

REM 3. OSGeo4W classique
if "!QGIS_PYTHON!"=="" if exist "C:\OSGeo4W64\bin\python.exe" set "QGIS_PYTHON=C:\OSGeo4W64\bin\python.exe"
if "!QGIS_PYTHON!"=="" if exist "C:\OSGeo4W\bin\python.exe" set "QGIS_PYTHON=C:\OSGeo4W\bin\python.exe"

REM 4. Recherche PowerShell (chemin complet, sans dependre du PATH)
if "!QGIS_PYTHON!"=="" if exist "!POWERSHELL!" (
    for /f "delims=" %%p in (`"!POWERSHELL!" -NoProfile -Command "Get-ChildItem -Path 'C:\Program Files', $env:LOCALAPPDATA -Filter 'python.exe' -Recurse -ErrorAction SilentlyContinue 2>$null | Where-Object { $_.FullName -match 'QGIS|OSGeo' } | Select-Object -First 1 -ExpandProperty FullName"`) do (
        if exist "%%p" set "QGIS_PYTHON=%%p"
    )
)

REM 5. Fichier de configuration manuel
if "!QGIS_PYTHON!"=="" if exist "%SCRIPT_DIR%qgis_python_path.txt" (
    set /p QGIS_PYTHON=<"%SCRIPT_DIR%qgis_python_path.txt"
    for /f "tokens=*" %%a in ("!QGIS_PYTHON!") do set "QGIS_PYTHON=%%~a"
)
if "!QGIS_PYTHON!"=="" if exist "%CARTO_DIR%qgis_python_path.txt" (
    set /p QGIS_PYTHON=<"%CARTO_DIR%qgis_python_path.txt"
    for /f "tokens=*" %%a in ("!QGIS_PYTHON!") do set "QGIS_PYTHON=%%~a"
)

if "!QGIS_PYTHON!"=="" (
    echo.
    echo [Erreur] Python QGIS introuvable.
    echo.
    echo Creer scripts\windows\qgis_python_path.txt avec le chemin vers python.exe QGIS.
    echo Ou dans QGIS Console : import sys; print(sys.executable^)
    echo.
    pause
    exit /b 1
)

for %%A in ("!QGIS_PYTHON!") do set "TMP_BIN=%%~dpA"
set "TMP_ROOT=!TMP_BIN:~0,-4!"
if exist "!TMP_ROOT!\bin\o4w_env.bat" call :configure_osgeo4w_env

:run_bilans
cd /d "%PROJECT_ROOT%"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
echo.
echo Python QGIS : !QGIS_PYTHON!
echo.

if not "%~1"=="" (
    echo Execution : python -m bilans %*
    echo.
    "!QGIS_PYTHON!" -m bilans %*
    set "ERR=!ERRORLEVEL!"
    if !ERR! neq 0 (
        echo.
        echo Echec du bilan (code !ERR!^).
        echo Si le module bilans est absent, installer une fois :
        echo   "!QGIS_PYTHON!" -m pip install -e .
    ) else (
        echo.
        echo ===== Termine =====
    )
    echo.
    pause
    exit /b !ERR!
)

echo ===============================================
echo   Bilans avec PyQGIS (cartes adaptatives)
echo ===============================================
echo.
echo Ce script configure l'environnement QGIS puis lance
echo python -m bilans en mode interactif (profils, periode,
echo echelle, options cartes).
echo.
echo Exemple non interactif :
echo   %~nx0 --profil global --cartes --echelle departement --code 21 --date-deb 2025-01-01 --date-fin 2025-12-31
echo.
"!QGIS_PYTHON!" -m bilans
set "ERR=!ERRORLEVEL!"
echo.
if !ERR! neq 0 (
    echo Echec du bilan (code !ERR!^).
    echo Si le module bilans est absent, installer une fois :
    echo   "!QGIS_PYTHON!" -m pip install -e .
) else (
    echo ===== Termine =====
)
echo.
pause
exit /b !ERR!

:configure_osgeo4w_env
for %%A in ("!QGIS_PYTHON!") do set "OSGEO4W_BIN=%%~dpA"
set "OSGEO4W_ROOT=!OSGEO4W_BIN:~0,-4!"
if exist "!OSGEO4W_ROOT!\bin\o4w_env.bat" call "!OSGEO4W_ROOT!\bin\o4w_env.bat"
set "QGIS_APPS_DIR=qgis-ltr"
if not exist "!OSGEO4W_ROOT!\apps\qgis-ltr" if exist "!OSGEO4W_ROOT!\apps\qgis" set "QGIS_APPS_DIR=qgis"
path !OSGEO4W_ROOT!\apps\!QGIS_APPS_DIR!\bin;!PATH!
set "QGIS_PREFIX_PATH=!OSGEO4W_ROOT:\=/!/apps/!QGIS_APPS_DIR!"
set "GDAL_FILENAME_IS_UTF8=YES"
set "QT_QPA_PLATFORM=offscreen"
set "PYTHONPATH=!OSGEO4W_ROOT!\apps\!QGIS_APPS_DIR!\python;!PYTHONPATH!"
exit /b 0
