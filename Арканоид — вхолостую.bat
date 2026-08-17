@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Арканоид — сухой прогон
python -u boot.py --dry --start
pause
