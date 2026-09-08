@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set QGIS_PYTHON=""

:: Cherche dans les installations standards de QGIS
for /d %%i in ("C:\Program Files\QGIS*") do (
    if exist "%%i\bin\python-qgis.bat" (
        set QGIS_PYTHON="%%i\bin\python-qgis.bat"
        goto :found
    )
    if exist "%%i\bin\python-qgis-ltr.bat" (
        set QGIS_PYTHON="%%i\bin\python-qgis-ltr.bat"
        goto :found
    )
)

:found
if %QGIS_PYTHON%=="" (
    echo [ERREUR] Impossible de trouver une installation standard de QGIS.
    exit /b 1
)

:: %~dp0 correspond au dossier ou se trouve ce script .bat
%QGIS_PYTHON% "%~dp0..\core\point_entree_cli.py" %*
exit /b
