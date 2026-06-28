@echo off
title JARVIS — Personal AI Assistant
cd /d "%~dp0"

:: Always use the virtual environment Python
set PYTHON=.venv\Scripts\pythonw.exe
if not exist "%PYTHON%" set PYTHON=.venv\Scripts\python.exe

:: Run Jarvis silently using jarvis_temp.py (fully unlocked copy)
start "" /B "%PYTHON%" jarvis_temp.py
