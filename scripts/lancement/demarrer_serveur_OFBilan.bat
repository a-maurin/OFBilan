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

for /d %%i in ("C:\Program Files\QGIS*") do (
    if "!QGIS_PYTHON!"=="" if exist "%%i\bin\python-qgis-ltr.bat" set "QGIS_PYTHON=%%i\bin\python-qgis-ltr.bat"
)
for /d %%i in ("C:\Program Files\QGIS*") do (
    if "!QGIS_PYTHON!"=="" if exist "%%i\bin\python-qgis.bat" set "QGIS_PYTHON=%%i\bin\python-qgis.bat"
)
if "!QGIS_PYTHON!"=="" if exist "%LOCALAPPDATA%\Programs\OSGeo4W\bin\python-qgis-ltr.bat" set "QGIS_PYTHON=%LOCALAPPDATA%\Programs\OSGeo4W\bin\python-qgis-ltr.bat"
if "!QGIS_PYTHON!"=="" if exist "%LOCALAPPDATA%\Programs\OSGeo4W\bin\python-qgis.bat" set "QGIS_PYTHON=%LOCALAPPDATA%\Programs\OSGeo4W\bin\python-qgis.bat"
if "!QGIS_PYTHON!"=="" if exist "C:\OSGeo4W64\bin\python-qgis-ltr.bat" set "QGIS_PYTHON=C:\OSGeo4W64\bin\python-qgis-ltr.bat"

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
set "PYTHONDONTWRITEBYTECODE=1"

call "!QGIS_PYTHON!" "%PROJECT_ROOT%\core\web\serveur.py" !DEBUG_ARG! %*
if errorlevel 1 (
    echo.
    echo [ERREUR] Le serveur s'est arrete avec une erreur.
    pause
)

popd
