@echo off
setlocal EnableDelayedExpansion

set "QGIS_PYTHON=C:\Program Files\QGIS 3.44.8\bin\python.exe"

for %%A in ("!QGIS_PYTHON!") do set "TMP_BIN=%%~dpA"
set "TMP_ROOT=!TMP_BIN:~0,-4!"
if exist "!TMP_ROOT!\bin\o4w_env.bat" (
    call :configure_osgeo4w_env
)

"!QGIS_PYTHON!" -c "import sys; import qgis.core; print('QGIS OK'); app = qgis.core.QgsApplication([], False); app.initQgis(); print('QGIS Init OK')"
if errorlevel 1 echo ERROR QGIS.CORE IMPORT FAILED.

exit /b

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
