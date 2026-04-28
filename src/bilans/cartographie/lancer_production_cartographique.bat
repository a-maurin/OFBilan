@echo off
setlocal EnableDelayedExpansion
REM Lancer la production cartographique avec le Python de QGIS
REM Détecte automatiquement la version la plus récente de QGIS installée

set "QGIS_PYTHON="
set "PF=C:\Program Files"
set "SCRIPT_DIR=%~dp0"

REM 0. Priorité : OSGeo4W AppData
set "LOCALAPPDATA_OSGEO=%LOCALAPPDATA%\Programs\OSGeo4W"
if exist "%LOCALAPPDATA_OSGEO%\bin\python.exe" (
    if "%~1"=="--gui" (
        call "%SCRIPT_DIR%lancer_osgeo4w.bat" %*
        exit /b %ERRORLEVEL%
    )
    set "QGIS_PYTHON=%LOCALAPPDATA_OSGEO%\bin\python.exe"
    for %%A in ("!QGIS_PYTHON!") do set "OSGEO4W_BIN=%%~dpA"
    set "OSGEO4W_ROOT=!OSGEO4W_BIN:~0,-4!"
    call "!OSGEO4W_ROOT!\bin\o4w_env.bat"
    set "PYTHONHOME=!OSGEO4W_ROOT!\apps\Python312"
    path "!OSGEO4W_ROOT!\apps\qgis-ltr\bin";!PATH!
    set "QGIS_PREFIX_PATH=!OSGEO4W_ROOT:/=!/apps/qgis-ltr"
    set "GDAL_FILENAME_IS_UTF8=YES"
    set "QT_QPA_PLATFORM=offscreen"
    set "PYTHONPATH=!OSGEO4W_ROOT!\apps\qgis-ltr\python;!PYTHONPATH!"
    cd /d "%SCRIPT_DIR%..\.."
    "!QGIS_PYTHON!" "%SCRIPT_DIR%production_cartographique.py" %*
    if errorlevel 1 (
        echo.
        echo Le script a echoue. Verifier les messages ci-dessus.
    )
    pause
    exit /b %ERRORLEVEL%
)

REM 1. Priorité : QGIS 3.40.x
if exist "%PF%\QGIS 3.40.15\bin\python.exe" set "QGIS_PYTHON=%PF%\QGIS 3.40.15\bin\python.exe"
if "!QGIS_PYTHON!"=="" if exist "%PF%\QGIS 3.40.15\bin\python3.exe" set "QGIS_PYTHON=%PF%\QGIS 3.40.15\bin\python3.exe"
if "!QGIS_PYTHON!"=="" (
    for /f "delims=" %%p in ('dir "%PF%\QGIS 3.40.15\apps\Python*" /b /ad 2^>nul') do (
        if exist "%PF%\QGIS 3.40.15\apps\%%p\python.exe" set "QGIS_PYTHON=%PF%\QGIS 3.40.15\apps\%%p\python.exe"
    )
)
if "!QGIS_PYTHON!"=="" if exist "%PF%\QGIS 3.40.15\osgeo4w\bin\python.exe" set "QGIS_PYTHON=%PF%\QGIS 3.40.15\osgeo4w\bin\python.exe"
if "!QGIS_PYTHON!"=="" (
    for /f "delims=" %%p in ('dir "%PF%\QGIS 3.40.15\osgeo4w\apps\Python*" /b /ad 2^>nul') do (
        if exist "%PF%\QGIS 3.40.15\osgeo4w\apps\%%p\python.exe" set "QGIS_PYTHON=%PF%\QGIS 3.40.15\osgeo4w\apps\%%p\python.exe"
    )
)

REM 2. Parcourir les autres versions QGIS
if "!QGIS_PYTHON!"=="" for /f "delims=" %%d in ('dir "%PF%\QGIS*" /b /ad /o-n 2^>nul') do (
    if "!QGIS_PYTHON!"=="" (
        if exist "%PF%\%%d\bin\python.exe" set "QGIS_PYTHON=%PF%\%%d\bin\python.exe"
    )
    if "!QGIS_PYTHON!"=="" (
        for /f "delims=" %%p in ('dir "%PF%\%%d\apps\Python*" /b /ad 2^>nul') do (
            if exist "%PF%\%%d\apps\%%p\python.exe" set "QGIS_PYTHON=%PF%\%%d\apps\%%p\python.exe"
        )
    )
)

REM 3. Fallback : OSGeo4W classique
if "!QGIS_PYTHON!"=="" if exist "C:\OSGeo4W64\bin\python.exe" set "QGIS_PYTHON=C:\OSGeo4W64\bin\python.exe"
if "!QGIS_PYTHON!"=="" if exist "C:\OSGeo4W\bin\python.exe" set "QGIS_PYTHON=C:\OSGeo4W\bin\python.exe"

REM 4. Recherche PowerShell
if "!QGIS_PYTHON!"=="" (
    for /f "delims=" %%p in ('powershell -NoProfile -Command "Get-ChildItem -Path 'C:\Program Files', $env:LOCALAPPDATA -Filter 'python.exe' -Recurse -ErrorAction SilentlyContinue 2>$null | Where-Object { $_.FullName -match 'QGIS|OSGeo' } | Select-Object -First 1 -ExpandProperty FullName"') do (
        if exist "%%p" set "QGIS_PYTHON=%%p"
    )
)

REM 5. Fichier de configuration manuel
if "!QGIS_PYTHON!"=="" (
    if exist "%SCRIPT_DIR%qgis_python_path.txt" (
        set /p QGIS_PYTHON=<"%SCRIPT_DIR%qgis_python_path.txt"
        for /f "tokens=*" %%a in ("!QGIS_PYTHON!") do set "QGIS_PYTHON=%%~a"
        if not exist "!QGIS_PYTHON!" set "QGIS_PYTHON="
    )
)

if "!QGIS_PYTHON!"=="" (
    echo QGIS Python introuvable.
    echo.
    echo Solutions :
    echo   1. Creer le fichier qgis_python_path.txt dans scripts\generateur_de_cartes\
    echo      avec une seule ligne : le chemin complet vers python.exe
    echo      Exemple : C:\Program Files\QGIS 3.40.15\bin\python.exe
    echo.
    echo Pour trouver python.exe : ouvrir QGIS, menu Extensions -^> Console Python,
    echo puis taper : import sys ; print(sys.executable)
    pause
    exit /b 1
)

cd /d "%SCRIPT_DIR%..\.."
REM Configuration environnement OSGeo4W
echo !QGIS_PYTHON! | findstr /i "OSGeo4W" >nul
if not errorlevel 1 (
    for %%A in ("!QGIS_PYTHON!") do set "OSGEO4W_BIN=%%~dpA"
    set "OSGEO4W_ROOT=!OSGEO4W_BIN:~0,-4!"
    call "!OSGEO4W_ROOT!\bin\o4w_env.bat"
    set "PYTHONHOME=!OSGEO4W_ROOT!\apps\Python312"
    path "!OSGEO4W_ROOT!\apps\qgis-ltr\bin";!PATH!
    set "QGIS_PREFIX_PATH=!OSGEO4W_ROOT:/=!/apps/qgis-ltr"
    set "GDAL_FILENAME_IS_UTF8=YES"
    set "QT_QPA_PLATFORM=offscreen"
    set "PYTHONPATH=!OSGEO4W_ROOT!\apps\qgis-ltr\python;!PYTHONPATH!"
)
"%QGIS_PYTHON%" "%SCRIPT_DIR%production_cartographique.py" %*
if errorlevel 1 (
    echo.
    echo Le script a echoue. Verifier les messages ci-dessus.
)
pause
