@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0\..\.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

REM Si des arguments CLI sont fournis, mode non interactif direct.
if not "%~1"=="" (
  python src\bilans\cartographie\generer_cartes.py %*
  exit /b %errorlevel%
)

echo ================================
echo   Generer des cartes - Periode libre
echo ================================
echo.
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "(Get-Date).ToString('yyyy-MM-dd')"`) do set "DATE_FIN_DEFAULT=%%T"
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "$y=(Get-Date).Year; '{0}-01-01' -f $y"`) do set "DATE_DEB_DEFAULT=%%T"

set /p "DATE_DEB=Date de debut (YYYY-MM-DD) [!DATE_DEB_DEFAULT!] > "
set /p "DATE_FIN=Date de fin   (YYYY-MM-DD) [!DATE_FIN_DEFAULT!] > "
set /p "DEPT=Code departement [21] > "

if "!DATE_DEB!"=="" set "DATE_DEB=!DATE_DEB_DEFAULT!"
if "!DATE_FIN!"=="" set "DATE_FIN=!DATE_FIN_DEFAULT!"
if "!DEPT!"=="" set "DEPT=21"

echo.
echo 1 = agrainage  2 = chasse  3 = piegeage  4 = global  5 = types usagers  6 = procedures PVe  7 = toutes
set /p CHOIX=Quelle(s) carte(s) (1 a 7) [7] ^> 

if "!CHOIX!"=="" set "CHOIX=7"
if "!CHOIX!"=="1" set "MAP=agrainage"
if "!CHOIX!"=="2" set "MAP=chasse"
if "!CHOIX!"=="3" set "MAP=piegeage"
if "!CHOIX!"=="4" set "MAP=global"
if "!CHOIX!"=="5" set "MAP=global_usagers"
if "!CHOIX!"=="6" set "MAP=procedures_pve"
if "!CHOIX!"=="7" set "MAP=tous"
if "!MAP!"=="" set "MAP=tous"

echo.
echo Periode : !DATE_DEB! au !DATE_FIN! - Departement !DEPT! - Carte(s) : !MAP!
echo.

call src\bilans\cartographie\lancer_production_cartographique.bat !MAP! --date-deb "!DATE_DEB!" --date-fin "!DATE_FIN!" --dept-code "!DEPT!"
echo.
echo ===== Termine =====
pause

endlocal

