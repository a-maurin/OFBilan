@echo off
echo === Test Reference (Dep 21) ===
python -m bilans --profil global --echelle departement --code 21 --date-deb 2025-01-01 --date-fin 2025-12-31 --cartes > audit_21.log 2>&1
echo Exit code 21: %errorlevel%

echo === Test Robustesse (Dep 25) ===
python -m bilans --profil global --echelle departement --code 25 --date-deb 2025-01-01 --date-fin 2025-12-31 --cartes > audit_25.log 2>&1
echo Exit code 25: %errorlevel%

echo === Test Robustesse (Dep 39) ===
python -m bilans --profil global --echelle departement --code 39 --date-deb 2025-01-01 --date-fin 2025-12-31 --cartes > audit_39.log 2>&1
echo Exit code 39: %errorlevel%

echo === Test Agregation (Reg 27) ===
python -m bilans --profil global --echelle region --code 27 --date-deb 2025-01-01 --date-fin 2025-12-31 --cartes > audit_27.log 2>&1
echo Exit code 27: %errorlevel%

echo Audit execution finished.
