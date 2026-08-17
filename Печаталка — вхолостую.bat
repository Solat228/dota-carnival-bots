@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Печаталка — сухой прогон
python -u main.py --dry --start
pause
