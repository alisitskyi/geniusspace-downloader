import os
from pathlib import Path

BASE = Path(__file__).parent

# 1. Update .env
ENV_CONTENT = """# Токен авторизації з браузера
GENIUS_AUTH_TOKEN=eiHWHZYBLAJsha3tFhNXseSJIJK_NVWiXOcp-YDX5ZTD5CZa

# Session-Id з браузера
GENIUS_SESSION_ID=d41fb6feebd5c6fbf133aefcc8ff7fca

# Slug курсу за замовчуванням
DEFAULT_COURSE_SLUG=aimoneymaker

# Папка для цього курсу
DEFAULT_COURSE_DIR=GeniusSpace_AI Спеціаліст

# Базова папка для збереження (. означає поточну папку Education)
DOWNLOAD_BASE_DIR=.

# Завантажувати відео (true/false)
DOWNLOAD_VIDEOS=true

# Завантажувати додаткові файли/презентації (true/false)
DOWNLOAD_FILES=true

# Якість відео (best, 1080p, 720p, 480p, 360p)
VIDEO_QUALITY=720p

# Авто-стиснення та оптимізація відео (Intel QSV / x264)
OPTIMIZE_VIDEOS=true
OPTIMIZE_CRF=26
"""

with open(BASE / ".env", "w", encoding="utf-8") as f:
    f.write(ENV_CONTENT.strip() + "\n")
print("[OK] .env оновлено!")
