@echo off
chcp 65001 > nul
title Video Optimizer (Genius.Space)
cd /d "%~dp0"

echo =======================================================
echo          Оптимізація та стиснення відео (FFmpeg)
echo =======================================================
echo.

if exist ".venv\Scripts\python.exe" (
    call .venv\Scripts\activate.bat
    python optimize_course.py %*
) else (
    python optimize_course.py %*
)

echo.
pause
