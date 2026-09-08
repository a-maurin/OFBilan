@echo off
chcp 65001 > nul
python "%~dp0build_natinf_concordance.py"
pause
