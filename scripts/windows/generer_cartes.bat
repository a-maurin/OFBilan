@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0\..\.."

REM Si des arguments CLI sont fournis, mode non interactif direct.
if not "%~1"=="" (
  python scripts\generer_cartes.py %*
  exit /b %errorlevel%
)

echo ================================
echo   Generer des cartes - Periode libre
echo ================================
echo.
set /p DATE_DEB=Date de debut (YYYY-MM-DD) ^> 
set /p DATE_FIN=Date de fin   (YYYY-MM-DD) ^> 
set /p DEPT=Code departement [21] ^> 

if "!DEPT!"=="" set "DEPT=21"

echo.
echo 1 = agrainage  2 = chasse  3 = piegeage  4 = types usagers  5 = procedures PVe  6 = toutes
set /p CHOIX=Quelle(s) carte(s) (1 a 6) [6] ^> 

if "!CHOIX!"=="" set "CHOIX=6"
if "!CHOIX!"=="1" set "MAP=agrainage"
if "!CHOIX!"=="2" set "MAP=chasse"
if "!CHOIX!"=="3" set "MAP=piegeage"
if "!CHOIX!"=="4" set "MAP=global_usagers"
if "!CHOIX!"=="5" set "MAP=procedures_pve"
if "!CHOIX!"=="6" set "MAP=tous"
if "!MAP!"=="" set "MAP=tous"

echo.
echo Periode : !DATE_DEB! au !DATE_FIN! - Departement !DEPT! - Carte(s) : !MAP!
echo.

call scripts\generateur_de_cartes\lancer_production_cartographique.bat !MAP! --date-deb "!DATE_DEB!" --date-fin "!DATE_FIN!" --dept-code "!DEPT!"
echo.
echo ===== Termine =====
pause

endlocal

