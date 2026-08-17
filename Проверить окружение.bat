@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Проверка окружения
python -u run.py doctor
pause
