@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Арканоид — Сапожный снос
python -u boot.py --start
pause
