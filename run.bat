@echo off
setlocal
cd /d "%~dp0"
title Genius.Space Course Downloader

REM 1. Fast path: virtual environment already exists
if exist ".venv\Scripts\python.exe" goto :launch

REM 2. Check if python is in PATH
where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=python"
    goto :setup_venv
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=py"
    goto :setup_venv
)

echo [ERROR] Python not found in system PATH!
echo.
echo Please install Python 3.10 or newer from https://www.python.org/downloads/
echo Important: check the box [X] "Add python.exe to PATH" during installation.
echo.
pause
exit /b 1

:setup_venv
echo [INFO] First run setup: creating virtual environment (.venv)...
%PY_CMD% -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo [INFO] Installing required libraries (requests, yt-dlp, rich, colorama)...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install packages. Check internet connection.
    pause
    exit /b 1
)
echo [OK] Setup completed successfully!
echo.

:launch
call .venv\Scripts\activate.bat
python main.py
if %errorlevel% neq 0 (
    echo.
    echo Program finished with error code %errorlevel%.
    pause
)
