@echo off
title JARVIS — Setup and Launch
cd /d "%~dp0"

echo.
echo  ====================================================
echo    JARVIS — Setting up and Starting...
echo  ====================================================
echo.

:: Check for venv
set PYTHON=.venv\Scripts\python.exe
set PIP=.venv\Scripts\pip.exe

if not exist "%PYTHON%" (
    echo [ERROR] Virtual environment not found!
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create venv. Make sure Python is installed.
        pause
        exit /b 1
    )
)

echo [1/3] Installing / updating required packages...
"%PIP%" install pyautogui pygetwindow keyboard --quiet 2>nul
echo      Done.

echo [2/3] Verifying core packages...
"%PYTHON%" -c "import sounddevice, numpy, speech_recognition, requests, psutil, bs4" 2>nul
if errorlevel 1 (
    echo      Installing all requirements...
    "%PIP%" install -r requirements.txt --quiet
)
echo      Done.

echo [3/3] Starting JARVIS...
echo.
echo  ====================================================
echo    Say "Jarvis" to wake me up!
echo    Close this window or say "Jarvis off" to stop.
echo  ====================================================
echo.

"%PYTHON%" jarvis_v2.py

pause
