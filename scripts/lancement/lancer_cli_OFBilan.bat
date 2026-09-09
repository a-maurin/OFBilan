@REM Copyright (C) 2026 Aguirre MAURIN
@REM
@REM Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
@REM selon les termes de la Licence Publique Générale GNU (GPL) telle que publiée par
@REM la Free Software Foundation, version 3 de la licence, ou (à votre choix) toute version ultérieure.
@REM
@REM Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE GARANTIE ;
@REM sans même la garantie implicite de QUALITÉ MARCHANDE ou D'ADÉQUATION À UN USAGE PARTICULIER.
@REM Voir la Licence Publique Générale GNU pour plus de détails.
@REM
@REM CONDITIONS SUPPLÉMENTAIRES D'ATTRIBUTION (SECTION 7(b) DE LA GPL v3) :
@REM Conformément à la section 7(b) de la GNU GPL v3, vous devez expressément conserver
@REM intactes et lisibles toutes les mentions d'auteur, notices de copyright et la présente
@REM clause dans chaque fichier source ou interface utilisateur redistribué. Toute version modifiée
@REM doit clairement indiquer qu'elle a été altérée et ne doit en aucun cas supprimer le nom
@REM de l'auteur original (Aguirre MAURIN).

@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set QGIS_PYTHON=""

:: Cherche dans les installations standards de QGIS
for /d %%i in ("C:\Program Files\QGIS*") do (
    if exist "%%i\bin\python-qgis.bat" (
        set QGIS_PYTHON="%%i\bin\python-qgis.bat"
        goto :found
    )
    if exist "%%i\bin\python-qgis-ltr.bat" (
        set QGIS_PYTHON="%%i\bin\python-qgis-ltr.bat"
        goto :found
    )
)

:found
if %QGIS_PYTHON%=="" (
    echo [ERREUR] Impossible de trouver une installation standard de QGIS.
    exit /b 1
)

:: %~dp0 correspond au dossier ou se trouve ce script .bat
%QGIS_PYTHON% "%~dp0..\..\core\point_entree_cli.py" %*
exit /b
