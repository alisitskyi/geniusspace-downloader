@echo off
chcp 65001 > nul
title Genius.Space Course Downloader
cd /d "%~dp0"

echo =======================================================
echo          Genius.Space Course Downloader
echo =======================================================
echo.

:: Перевірка наявності Python у системі
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ПОМИЛКА] Python не знайдено на цьому комп'ютері!
        echo.
        echo Для роботи потрібен Python 3.10 або новіший:
        echo 1. Завантажте Python з https://www.python.org/downloads/
        echo 2. ПРИ ВСТАНОВЛЕННІ ОБОВ'ЯЗКОВО поставте прапорець:
        echo    [X] "Add python.exe to PATH"
        echo 3. Після встановлення запустіть run.bat знову.
        echo.
        pause
        exit /b 1
    ) else (
        set PY_CMD=py
    )
) else (
    set PY_CMD=python
)

:: Перевірка віртуального оточення
if not exist ".venv\Scripts\python.exe" (
    echo [ІНФО] Перший запуск на цьому комп'ютері.
    echo Створення віртуального оточення (.venv)...
    %PY_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [ПОМИЛКА] Не вдалося створити .venv. Перевірте встановлення Python.
        pause
        exit /b 1
    )
    echo Встановлення необхідних бібліотек (requests, yt-dlp, rich)...
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ПОМИЛКА] Не вдалося встановити бібліотеки. Перевірте підключення до Інтернету.
        pause
        exit /b 1
    )
    echo [OK] Усі залежності успішно встановлено!
    echo.
) else (
    call .venv\Scripts\activate.bat
)

:: Запуск основної програми
python main.py

echo.
pause
