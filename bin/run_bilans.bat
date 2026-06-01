@echo off
setlocal EnableDelayedExpansion

set "QGIS_PYTHON=C:\Program Files\QGIS 3.44.8\bin\python.exe"

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

set "PROJECT_ROOT=%~dp0..\"
set "PYTHONPATH=%PROJECT_ROOT%src;!OSGEO4W_ROOT!\apps\!QGIS_APPS_DIR!\python;!PYTHONPATH!"

echo Running Python with faulthandler...
"!QGIS_PYTHON!" -X faulthandler -m bilans --profil global --cartes --date-deb 2025-01-01 --date-fin 2025-12-31 --dept-code 21
echo Exit code: !ERRORLEVEL!
