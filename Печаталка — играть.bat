@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Печаталка — Атака автоматонов
python -u main.py --start
pause
