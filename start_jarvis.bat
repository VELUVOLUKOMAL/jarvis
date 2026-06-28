@echo off
title JARVIS — Personal AI Assistant
cd /d "%~dp0"

echo.
echo  ====================================================
echo    JARVIS — Starting up...
echo  ====================================================
echo.

:: Always use the virtual environment Python
set PYTHON=.venv\Scripts\python.exe

if not exist "%PYTHON%" (
    echo [ERROR] Virtual environment not found!
    echo Run: python -m venv .venv
    echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

:: Run Jarvis with the venv Python
"%PYTHON%" jarvis.py

pause
