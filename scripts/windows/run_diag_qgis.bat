@echo off
setlocal EnableDelayedExpansion
set "SCRIPT_DIR=%~dp0..\..\src\bilans\cartographie\"
set "QGIS_PYTHON="

REM Copie allégée de la logique de lancer_production_cartographique.bat pour trouver QGIS
set "LOCALAPPDATA_OSGEO=%LOCALAPPDATA%\Programs\OSGeo4W"
if exist "%LOCALAPPDATA_OSGEO%\bin\python.exe" (
    set "QGIS_PYTHON=%LOCALAPPDATA_OSGEO%\bin\python.exe"
    for %%A in ("!QGIS_PYTHON!") do set "OSGEO4W_BIN=%%~dpA"
    set "OSGEO4W_ROOT=!OSGEO4W_BIN:~0,-4!"
    call "!OSGEO4W_ROOT!\bin\o4w_env.bat"
    set "QGIS_APPS_DIR=qgis-ltr"
    if not exist "!OSGEO4W_ROOT!\apps\qgis-ltr" (
        if exist "!OSGEO4W_ROOT!\apps\qgis" set "QGIS_APPS_DIR=qgis"
    )
    path "!OSGEO4W_ROOT!\apps\!QGIS_APPS_DIR!\bin";!PATH!
    set "PYTHONPATH=!OSGEO4W_ROOT!\apps\!QGIS_APPS_DIR!\python;!PYTHONPATH!"
)
if "!QGIS_PYTHON!"=="" (
    for /f "delims=" %%p in ('powershell -NoProfile -Command "Get-ChildItem -Path 'C:\Program Files' -Filter 'python.exe' -Recurse -ErrorAction SilentlyContinue 2>$null | Where-Object { $_.FullName -match 'QGIS' } | Select-Object -First 1 -ExpandProperty FullName"') do (
        if exist "%%p" set "QGIS_PYTHON=%%p"
    )
)

if "!QGIS_PYTHON!"=="" (
    echo QGIS Python introuvable.
    exit /b 1
)

for %%A in ("!QGIS_PYTHON!") do set "PY_DIR=%%~dpA"
set "OSGEO4W_ROOT=!PY_DIR!"
set "OSGEO4W_ROOT=!OSGEO4W_ROOT:\apps\Python312\=!"
set "OSGEO4W_ROOT=!OSGEO4W_ROOT:\apps\Python311\=!"
set "OSGEO4W_ROOT=!OSGEO4W_ROOT:\apps\Python310\=!"
set "OSGEO4W_ROOT=!OSGEO4W_ROOT:\apps\Python39\=!"
set "OSGEO4W_ROOT=!OSGEO4W_ROOT:\bin\=!"

if exist "!OSGEO4W_ROOT!\bin\o4w_env.bat" (
    call "!OSGEO4W_ROOT!\bin\o4w_env.bat"
    set "QGIS_APPS_DIR=qgis-ltr"
    if not exist "!OSGEO4W_ROOT!\apps\qgis-ltr" (
        if exist "!OSGEO4W_ROOT!\apps\qgis" set "QGIS_APPS_DIR=qgis"
    )
    path "!OSGEO4W_ROOT!\apps\!QGIS_APPS_DIR!\bin";!PATH!
    set "PYTHONPATH=!OSGEO4W_ROOT!\apps\!QGIS_APPS_DIR!\python;!PYTHONPATH!"
)

cd /d "%~dp0..\.."
echo Lancement du diagnostic avec : "!QGIS_PYTHON!"
"!QGIS_PYTHON!" "scripts\windows\test_qgis_zorder.py"
pause
