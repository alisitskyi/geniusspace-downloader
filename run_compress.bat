@echo off
chcp 65001 >nul
title Video Compression - GeniusSpace No-Code Developer
echo ========================================================
echo   GeniusSpace No-Code Developer Video Compressor
echo   H.265 (HEVC) + Intel QuickSync Hardware Acceleration
echo ========================================================
echo.
python "%~dp0compress_course.py"
echo.
echo ========================================================
echo Done! Press any key to exit.
echo ========================================================
pause
