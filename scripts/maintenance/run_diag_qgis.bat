@REM Copyright (C) 2026 Aguirre MAURIN
@REM
@REM Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
@REM selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
@REM la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
@REM
@REM Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ;
@REM sans même la garantie implicite de QUALITÉ MARCHANDE ou D'ADÉQUATION À UN USAGE PARTICULIER.
@REM Voir la Licence Publique Générale GNU pour plus de détails.
@REM
@REM CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
@REM Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
@REM intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
@REM clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
@REM doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
@REM de l'auteur original (Aguirre MAURIN).

@echo off
setlocal EnableDelayedExpansion
set "SCRIPT_DIR=%~dp0..\..\core\cartographie\"
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
"!QGIS_PYTHON!" "%~dp0test_qgis_zorder.py"
pause
