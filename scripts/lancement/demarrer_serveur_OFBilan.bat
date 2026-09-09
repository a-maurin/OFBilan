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
chcp 65001 >nul
setlocal EnableDelayedExpansion

pushd "%~dp0..\.."
set "PROJECT_ROOT=%CD%"

echo.

:: Delegation prioritaire vers PowerShell pour immunite Unicode totale (apostrophes et espaces)
where powershell >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0demarrer_serveur_OFBilan.ps1" %*
    popd
    exit /b %ERRORLEVEL%
)

echo Recherche de l'interpreteur Python de QGIS...
set "QGIS_PYTHON="
set "QGIS_CACHE_FILE=%LOCALAPPDATA%\OFBilan\qgis_path.txt"

if exist "!QGIS_CACHE_FILE!" (
    set /p CACHED_QGIS=<"!QGIS_CACHE_FILE!"
    if exist "!CACHED_QGIS!" set "QGIS_PYTHON=!CACHED_QGIS!"
)

if "!QGIS_PYTHON!"=="" (
    for /d %%i in ("C:\Program Files\QGIS*") do (
        if "!QGIS_PYTHON!"=="" if exist "%%i\bin\python-qgis-ltr.bat" set "QGIS_PYTHON=%%i\bin\python-qgis-ltr.bat"
    )
    for /d %%i in ("C:\Program Files\QGIS*") do (
        if "!QGIS_PYTHON!"=="" if exist "%%i\bin\python-qgis.bat" set "QGIS_PYTHON=%%i\bin\python-qgis.bat"
    )
    if "!QGIS_PYTHON!"=="" if exist "%LOCALAPPDATA%\Programs\OSGeo4W\bin\python-qgis-ltr.bat" set "QGIS_PYTHON=%LOCALAPPDATA%\Programs\OSGeo4W\bin\python-qgis-ltr.bat"
    if "!QGIS_PYTHON!"=="" if exist "%LOCALAPPDATA%\Programs\OSGeo4W\bin\python-qgis.bat" set "QGIS_PYTHON=%LOCALAPPDATA%\Programs\OSGeo4W\bin\python-qgis.bat"
    if "!QGIS_PYTHON!"=="" if exist "C:\OSGeo4W64\bin\python-qgis-ltr.bat" set "QGIS_PYTHON=C:\OSGeo4W64\bin\python-qgis-ltr.bat"

    if defined QGIS_PYTHON (
        if not exist "%LOCALAPPDATA%\OFBilan" mkdir "%LOCALAPPDATA%\OFBilan" >nul 2>&1
        echo !QGIS_PYTHON!>"!QGIS_CACHE_FILE!"
    )
)

if "!QGIS_PYTHON!"=="" (
    echo [ERREUR] Impossible de trouver python-qgis-ltr.bat ou python-qgis.bat.
    echo         Verifiez que QGIS est installe dans C:\Program Files.
    pause
    popd
    exit /b 1
)

echo [OK] Interpreteur trouve : "!QGIS_PYTHON!"
echo.
echo [OK] Demarrage du serveur...
echo.

set "DEBUG_ARG="
if "%DEBUG%"=="1" set "DEBUG_ARG=--debug"
if "%OFBILAN_DEBUG%"=="1" set "DEBUG_ARG=--debug"

set "PYTHONDONTWRITEBYTECODE="
set "PYTHONPYCACHEPREFIX=%LOCALAPPDATA%\OFBilan\pycache"
if not exist "%LOCALAPPDATA%\OFBilan\pycache" mkdir "%LOCALAPPDATA%\OFBilan\pycache" >nul 2>&1

call "!QGIS_PYTHON!" "%PROJECT_ROOT%\core\web\serveur.py" !DEBUG_ARG! %*
if errorlevel 1 (
    echo.
    echo [ERREUR] Le serveur s'est arrete avec une erreur.
    pause
)

popd
