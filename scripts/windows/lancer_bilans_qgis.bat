@echo off
setlocal EnableDelayedExpansion
REM Lancer les bilans (python -m bilans) avec le Python de QGIS / OSGeo4W
REM Detection QGIS calquee sur src\bilans\cartographie\lancer_production_cartographique.bat

set "QGIS_PYTHON="
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
    for /f "delims=" %%p in ('powershell -NoProfile -Command "Get-ChildItem -Path 'C:\Program Files', $env:LOCALAPPDATA -Filter 'python.exe' -Recurse -ErrorAction SilentlyContinue 2^>$null | Where-Object { $_.FullName -match 'QGIS|OSGeo' } | Select-Object -First 1 -ExpandProperty FullName"') do (
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
    if exist "%CARTO_DIR%qgis_python_path.txt" (
        set /p QGIS_PYTHON=<"%CARTO_DIR%qgis_python_path.txt"
        for /f "tokens=*" %%a in ("!QGIS_PYTHON!") do set "QGIS_PYTHON=%%~a"
        if not exist "!QGIS_PYTHON!" set "QGIS_PYTHON="
    )
)

if "!QGIS_PYTHON!"=="" (
    echo QGIS Python introuvable.
    echo.
    echo Solutions :
    echo   1. Creer le fichier qgis_python_path.txt dans scripts\windows\
    echo      ou dans src\bilans\cartographie\
    echo      avec une seule ligne : le chemin complet vers python.exe
    echo      Exemple : C:\Program Files\QGIS 3.40.15\bin\python.exe
    echo.
    echo Pour trouver python.exe : ouvrir QGIS, menu Extensions -^> Console Python,
    echo puis taper : import sys ; print(sys.executable^)
    pause
    exit /b 1
)

for %%A in ("!QGIS_PYTHON!") do set "TMP_BIN=%%~dpA"
set "TMP_ROOT=!TMP_BIN:~0,-4!"
if exist "!TMP_ROOT!\bin\o4w_env.bat" call :configure_osgeo4w_env

:run_bilans
cd /d "%PROJECT_ROOT%"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

REM Si des arguments CLI sont fournis, mode non interactif direct.
if not "%~1"=="" (
    "!QGIS_PYTHON!" -m bilans %*
    set "ERR=!ERRORLEVEL!"
    if !ERR! neq 0 (
        echo.
        echo Le bilan a echoue. Verifier les messages ci-dessus.
        echo Si le module bilans est introuvable : "!QGIS_PYTHON!" -m pip install -e .
    )
    pause
    exit /b !ERR!
)

echo   OOOOOOO   FFFFFFF   BBBBBBB
echo   OOOOOOO   FFFFFFF   BBBBBBB
echo   OO   OO   FF        BB   BB
echo   OO   OO   FFFFFF    BBBBBBB
echo   OO   OO   FFFFFF    BBBBBBB
echo   OO   OO   FF        BB   BB
echo   OOOOOOO   FF        BBBBBBB
echo   OOOOOOO   FF        BBBBBBB
echo.
echo      OFFICE FRANCAIS
echo    DE LA BIODIVERSITE
echo.
echo ===============================================
echo   Bilans (Python QGIS) - global ou thematiques
echo ===============================================
echo Python : !QGIS_PYTHON!
echo.
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "(Get-Date).ToString('yyyy-MM-dd')"`) do set "DATE_FIN_DEFAULT=%%T"
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "$y=(Get-Date).Year; '{0}-01-01' -f $y"`) do set "DATE_DEB_DEFAULT=%%T"
set /p "DATE_DEB=Date de debut (YYYY-MM-DD ou YYYY) [!DATE_DEB_DEFAULT!] > "
set /p "DATE_FIN=Date de fin   (YYYY-MM-DD ou YYYY) [!DATE_FIN_DEFAULT!] > "
set /p "DEPT=Code departement (Cote d'Or) [21] > "

if "!DATE_DEB!"=="" set "DATE_DEB=!DATE_DEB_DEFAULT!"
if "!DATE_FIN!"=="" set "DATE_FIN=!DATE_FIN_DEFAULT!"
if "!DEPT!"=="" set "DEPT=21"

if "!DATE_DEB:~4,1!"=="" if not "!DATE_DEB:~3,1!"=="" (
  set /a "yy_deb=!DATE_DEB!+0" 2>nul
  if !yy_deb! gtr 0 set "DATE_DEB=!DATE_DEB!-01-01"
)
if "!DATE_FIN:~4,1!"=="" if not "!DATE_FIN:~3,1!"=="" (
  set /a "yy_fin=!DATE_FIN!+0" 2>nul
  if !yy_fin! gtr 0 set "DATE_FIN=!DATE_FIN!-12-31"
)

echo.
echo Periode : !DATE_DEB! au !DATE_FIN! - Departement !DEPT!
echo.
echo 1. Bilan global uniquement
echo 2. Bilan(s) thematique(s) - agrainage, chasse, piegeage, etc.
echo.

:choix_menu
set /p CHOIX=Choix (1 ou 2) ^> 
if "!CHOIX!"=="1" goto global
if "!CHOIX!"=="2" goto thematiques
echo Choix invalide. Veuillez saisir 1 ou 2.
echo.
goto choix_menu

:global
echo === Bilan global ===
"!QGIS_PYTHON!" -m bilans --profil global --date-deb "!DATE_DEB!" --date-fin "!DATE_FIN!" --dept-code "!DEPT!"
goto fin

:thematiques
echo.
echo Profils disponibles :
"!QGIS_PYTHON!" -m bilans --list-themes
echo.
set /p PROFILS=Profil(s) a lancer (numero(s) ou id, separes par des espaces) [2 3] ^> 
if "!PROFILS!"=="" set "PROFILS=2 3"
set "ARGS="
for %%p in (!PROFILS!) do set "ARGS=!ARGS! --profil %%p"
echo === Bilans thematiques ===
"!QGIS_PYTHON!" -m bilans !ARGS! --date-deb "!DATE_DEB!" --date-fin "!DATE_FIN!" --dept-code "!DEPT!"

:fin
if errorlevel 1 (
    echo.
    echo Le bilan a echoue. Verifier les messages ci-dessus.
    echo Si le module bilans est introuvable : "!QGIS_PYTHON!" -m pip install -e .
@echo off
setlocal EnableDelayedExpansion
REM Lancer les bilans (python -m bilans) avec le Python de QGIS / OSGeo4W
REM Detection QGIS calquee sur src\bilans\cartographie\lancer_production_cartographique.bat

set "QGIS_PYTHON="
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
    for /f "delims=" %%p in ('powershell -NoProfile -Command "Get-ChildItem -Path 'C:\Program Files', $env:LOCALAPPDATA -Filter 'python.exe' -Recurse -ErrorAction SilentlyContinue 2^>$null | Where-Object { $_.FullName -match 'QGIS|OSGeo' } | Select-Object -First 1 -ExpandProperty FullName"') do (
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
    if exist "%CARTO_DIR%qgis_python_path.txt" (
        set /p QGIS_PYTHON=<"%CARTO_DIR%qgis_python_path.txt"
        for /f "tokens=*" %%a in ("!QGIS_PYTHON!") do set "QGIS_PYTHON=%%~a"
        if not exist "!QGIS_PYTHON!" set "QGIS_PYTHON="
    )
)

if "!QGIS_PYTHON!"=="" (
    echo QGIS Python introuvable.
    echo.
    echo Solutions :
    echo   1. Creer le fichier qgis_python_path.txt dans scripts\windows\
    echo      ou dans src\bilans\cartographie\
    echo      avec une seule ligne : le chemin complet vers python.exe
    echo      Exemple : C:\Program Files\QGIS 3.40.15\bin\python.exe
    echo.
    echo Pour trouver python.exe : ouvrir QGIS, menu Extensions -^> Console Python,
    echo puis taper : import sys ; print(sys.executable^)
    pause
    exit /b 1
)

for %%A in ("!QGIS_PYTHON!") do set "TMP_BIN=%%~dpA"
set "TMP_ROOT=!TMP_BIN:~0,-4!"
if exist "!TMP_ROOT!\bin\o4w_env.bat" call :configure_osgeo4w_env

:run_bilans
cd /d "%PROJECT_ROOT%"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

REM Si des arguments CLI sont fournis, mode non interactif direct.
if not "%~1"=="" (
    "!QGIS_PYTHON!" -m bilans %*
    set "ERR=!ERRORLEVEL!"
    if !ERR! neq 0 (
        echo.
        echo Le bilan a echoue. Verifier les messages ci-dessus.
        echo Si le module bilans est introuvable : "!QGIS_PYTHON!" -m pip install -e .
    )
    pause
    exit /b !ERR!
)

echo   OOOOOOO   FFFFFFF   BBBBBBB
echo   OOOOOOO   FFFFFFF   BBBBBBB
echo   OO   OO   FF        BB   BB
echo   OO   OO   FFFFFF    BBBBBBB
echo   OO   OO   FFFFFF    BBBBBBB
echo   OO   OO   FF        BB   BB
echo   OOOOOOO   FF        BBBBBBB
echo   OOOOOOO   FF        BBBBBBB
echo.
echo      OFFICE FRANCAIS
echo    DE LA BIODIVERSITE
echo.
echo ===============================================
echo   Bilans (Python QGIS) - global ou thematiques
echo ===============================================
echo Python : !QGIS_PYTHON!
echo.
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "(Get-Date).ToString('yyyy-MM-dd')"`) do set "DATE_FIN_DEFAULT=%%T"
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "$y=(Get-Date).Year; '{0}-01-01' -f $y"`) do set "DATE_DEB_DEFAULT=%%T"
set /p "DATE_DEB=Date de debut (YYYY-MM-DD ou YYYY) [!DATE_DEB_DEFAULT!] > "
set /p "DATE_FIN=Date de fin   (YYYY-MM-DD ou YYYY) [!DATE_FIN_DEFAULT!] > "
set /p "DEPT=Code departement (Cote d'Or) [21] > "

if "!DATE_DEB!"=="" set "DATE_DEB=!DATE_DEB_DEFAULT!"
if "!DATE_FIN!"=="" set "DATE_FIN=!DATE_FIN_DEFAULT!"
if "!DEPT!"=="" set "DEPT=21"

if "!DATE_DEB:~4,1!"=="" if not "!DATE_DEB:~3,1!"=="" (
  set /a "yy_deb=!DATE_DEB!+0" 2>nul
  if !yy_deb! gtr 0 set "DATE_DEB=!DATE_DEB!-01-01"
)
if "!DATE_FIN:~4,1!"=="" if not "!DATE_FIN:~3,1!"=="" (
  set /a "yy_fin=!DATE_FIN!+0" 2>nul
  if !yy_fin! gtr 0 set "DATE_FIN=!DATE_FIN!-12-31"
)

echo.
echo Periode : !DATE_DEB! au !DATE_FIN! - Departement !DEPT!
echo.
echo 1. Bilan global uniquement
echo 2. Bilan(s) thematique(s) - agrainage, chasse, piegeage, etc.
echo.

:choix_menu
set /p CHOIX=Choix (1 ou 2) ^> 
if "!CHOIX!"=="1" goto global
if "!CHOIX!"=="2" goto thematiques
echo Choix invalide. Veuillez saisir 1 ou 2.
echo.
goto choix_menu

:global
echo === Bilan global ===
"!QGIS_PYTHON!" -m bilans --profil global --date-deb "!DATE_DEB!" --date-fin "!DATE_FIN!" --dept-code "!DEPT!"
goto fin

:thematiques
echo.
echo Profils disponibles :
"!QGIS_PYTHON!" -m bilans --list-themes
echo.
set /p PROFILS=Profil(s) a lancer (numero(s) ou id, separes par des espaces) [2 3] ^> 
if "!PROFILS!"=="" set "PROFILS=2 3"
set "ARGS="
for %%p in (!PROFILS!) do set "ARGS=!ARGS! --profil %%p"
echo === Bilans thematiques ===
"!QGIS_PYTHON!" -m bilans !ARGS! --date-deb "!DATE_DEB!" --date-fin "!DATE_FIN!" --dept-code "!DEPT!"

:fin
if errorlevel 1 (
    echo.
    echo Le bilan a echoue. Verifier les messages ci-dessus.
    echo Si le module bilans est introuvable : "!QGIS_PYTHON!" -m pip install -e .
)
echo.
echo ===== Termine =====
pause
exit /b %ERRORLEVEL%

:configure_osgeo4w_env
for %%A in ("!QGIS_PYTHON!") do set "OSGEO4W_BIN=%%~dpA"
set "OSGEO4W_ROOT=!OSGEO4W_BIN:~0,-4!"
call "!OSGEO4W_ROOT!\bin\o4w_env.bat"
set "PYTHONHOME=!OSGEO4W_ROOT!\apps\Python312"
    set "QGIS_APPS_DIR=qgis-ltr"
    if not exist "!OSGEO4W_ROOT!\apps\qgis-ltr" (
        if exist "!OSGEO4W_ROOT!\apps\qgis" set "QGIS_APPS_DIR=qgis"
    )
    path !OSGEO4W_ROOT!\apps\!QGIS_APPS_DIR!\bin;!PATH!
    set "QGIS_PREFIX_PATH=!OSGEO4W_ROOT:\=/!/apps/!QGIS_APPS_DIR!"
    set "GDAL_FILENAME_IS_UTF8=YES"
    set "QT_QPA_PLATFORM=offscreen"
    set "QT_PLUGIN_PATH=!OSGEO4W_ROOT!\apps\!QGIS_APPS_DIR!\qtplugins;!OSGEO4W_ROOT!\apps\qt5\plugins"
    set "PYTHONPATH=!OSGEO4W_ROOT!\apps\!QGIS_APPS_DIR!\python;!PYTHONPATH!"
exit /b 0
