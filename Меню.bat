@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Боты мини-игр Dota 2
python -u run.py
pause
