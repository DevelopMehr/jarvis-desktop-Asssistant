@echo off
title Install Jarvis
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found.
    echo Install it from python.org and tick "Add Python to PATH", then run this again.
    echo.
    pause
    exit /b 1
)
python install_jarvis.py
echo.
pause
