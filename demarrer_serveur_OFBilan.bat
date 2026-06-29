@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo =====================================
echo     Lancement du serveur OFBilan
echo =====================================
echo.
echo Recherche de l'interpreteur Python de QGIS...

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
    echo [ERREUR] Impossible de trouver une installation standard de QGIS dans C:\Program Files\
    echo Veuillez modifier manuellement ce script pour pointer vers votre fichier "python-qgis.bat".
    exit /b 1
)

echo [OK] Interpreteur trouve : %QGIS_PYTHON%
echo [OK] Demarrage du serveur...
echo.

:: %~dp0 correspond au dossier ou se trouve ce script .bat
%QGIS_PYTHON% "%~dp0core\web\serveur.py"
exit /b
