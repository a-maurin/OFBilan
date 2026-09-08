@echo off
setlocal
cd /d "%~dp0\..\.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

REM Ouverture de l'interface de configuration des cartes (QGIS)
python src\bilans\cartographie\gui_config_cartes.py %*

endlocal

