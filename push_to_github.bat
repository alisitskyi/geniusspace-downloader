@echo off
chcp 65001 > nul
title Git Push to GitHub
cd /d "%~dp0"

:: Додаємо Git та Git Credential Manager до PATH поточної сесії
set "PATH=C:\Program Files\Git\cmd;C:\Program Files\Git\ucrt64\bin;C:\Program Files\Git\bin;%PATH%"

echo =======================================================
echo          Відправка проекту на GitHub
echo =======================================================
echo.
echo [1/2] Перевірка Git та зв'язку з GitHub...
echo [2/2] Зараз відкриється браузер або запит авторизації...
echo.

git push -u origin main

echo.
echo =======================================================
pause
