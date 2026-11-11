@echo off
chcp 65001 > nul
title Git Push to GitHub
cd /d "%~dp0"

echo =======================================================
echo          Відправка проекту на GitHub
echo =======================================================
echo.

"C:\Program Files\Git\cmd\git.exe" push -u origin main

echo.
echo =======================================================
pause
