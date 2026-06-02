@echo off
set "QGIS_PYTHON=C:\Program Files\QGIS 3.44.8\bin\python.exe"
for %%A in ("%QGIS_PYTHON%") do set "OSGEO4W_BIN=%%~dpA"
set "OSGEO4W_ROOT=%OSGEO4W_BIN:~0,-4%"
call "%OSGEO4W_ROOT%\bin\o4w_env.bat"
set "PYTHONHOME=%OSGEO4W_ROOT%\apps\Python312"
set "QT_QPA_PLATFORM=offscreen"
set "PYTHONPATH=%OSGEO4W_ROOT%\apps\qgis-ltr\python;C:\Users\aguirre.maurin\Documents\GitHub\Bilans_production\src\bilans\cartographie;%PYTHONPATH%"
"%QGIS_PYTHON%" src\bilans\cartographie\production_cartographique.py --date-deb 2025-01-01 --date-fin 2025-12-31
