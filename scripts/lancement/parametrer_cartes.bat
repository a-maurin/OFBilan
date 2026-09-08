@echo off
setlocal
cd /d "%~dp0\..\.."
set "PYTHONPATH=%CD%;%PYTHONPATH%"

REM Ouverture de l'interface de configuration des cartes (QGIS)
python core\cartographie\gui_config_cartes.py %*

endlocal

