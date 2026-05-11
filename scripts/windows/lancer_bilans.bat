@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0\..\.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

REM Si des arguments CLI sont fournis, mode non interactif direct.
if not "%~1"=="" (
  python -m bilans %*
  exit /b %errorlevel%
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
echo ================================
echo   Bilans - Par profil (global ou thematiques)
echo ================================
echo.
set /p "DATE_DEB=Date de debut (YYYY-MM-DD ou YYYY) [2025-01-01] > "
set /p "DATE_FIN=Date de fin   (YYYY-MM-DD ou YYYY) [2026-12-31] > "
set /p "DEPT=Code departement (Cote d'Or) [21] > "

if "!DATE_DEB!"=="" set "DATE_DEB=2025-01-01"
if "!DATE_FIN!"=="" set "DATE_FIN=2026-12-31"
if "!DEPT!"=="" set "DEPT=21"

REM Si l'utilisateur saisit uniquement une annee (4 chiffres)
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
python -m bilans --profil global --date-deb "!DATE_DEB!" --date-fin "!DATE_FIN!" --dept-code "!DEPT!"
goto fin

:thematiques
echo.
echo Profils disponibles :
python -m bilans --list-themes
echo.
set /p PROFILS=Profil(s) a lancer (numero(s) ou id, separes par des espaces) [2 3] ^> 
if "!PROFILS!"=="" set "PROFILS=2 3"
set "ARGS="
for %%p in (!PROFILS!) do set "ARGS=!ARGS! --profil %%p"
echo === Bilans thematiques ===
python -m bilans !ARGS! --date-deb "!DATE_DEB!" --date-fin "!DATE_FIN!" --dept-code "!DEPT!"

:fin
echo.
echo ===== Termine =====
pause

endlocal

