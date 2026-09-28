@echo off
title Linx
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Setting up Linx for the first time...
    py -m venv .venv
    if errorlevel 1 (
        echo Python 3 is required. Install it from https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

.venv\Scripts\python -c "import discord, dotenv" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    .venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt
)

.venv\Scripts\python bot.py
pause
