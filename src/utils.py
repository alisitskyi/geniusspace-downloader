import os
import re
import sys
from pathlib import Path

RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

def setup_console_encoding():
    """
    Налаштовує консоль Windows на роботу з UTF-8 та вмикає підтримку ANSI-кольорів (VT100).
    Забезпечує коректне відображення українського тексту та кольорових меню в cmd.exe.
    """
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

        # Вмикаємо підтримку кольорів ANSI у Windows cmd.exe
        try:
            import colorama
            colorama.just_fix_windows_console()
        except Exception:
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                for std_id in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
                    h = kernel32.GetStdHandle(std_id)
                    if h and h != -1:
                        mode = ctypes.c_ulong()
                        if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
                            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                            kernel32.SetConsoleMode(h, mode.value | 0x0004)
            except Exception:
                pass

        # Вимикаємо QuickEdit Mode, щоб кліки або випадкові торкання пальцем на телефоні (RDP) не заморожували процес
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            h_in = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
            if h_in and h_in != -1:
                in_mode = ctypes.c_ulong()
                if kernel32.GetConsoleMode(h_in, ctypes.byref(in_mode)):
                    # ENABLE_QUICK_EDIT_MODE = 0x0040, ENABLE_EXTENDED_FLAGS = 0x0080
                    kernel32.SetConsoleMode(h_in, (in_mode.value & ~0x0040) | 0x0080)
        except Exception:
            pass

def sanitize_filename(name: str, max_length: int = 120) -> str:
    """
    Очищає назву файлу/папки від заборонених символів Windows та обмежує довжину.
    """
    if not name:
        return "unnamed"
    
    # Видаляємо неприпустимі символи Windows
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    # Замінюємо множинні пробіли та символи нового рядка
    cleaned = re.sub(r'\s+', " ", cleaned).strip(". ")
    
    # Якщо ім'я є зарезервованим у Windows
    if cleaned.upper() in RESERVED_NAMES:
        cleaned = f"_{cleaned}"
        
    if not cleaned:
        cleaned = "item"
        
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(". ")
        
    return cleaned

def format_bytes(size: int) -> str:
    """Форматує байти у зручний вигляд (KB, MB, GB)."""
    if size <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    val = float(size)
    while val >= 1024.0 and unit_idx < len(units) - 1:
        val /= 1024.0
        unit_idx += 1
    return f"{val:.2f} {units[unit_idx]}"

def get_ffmpeg_path() -> str:
    """
    Знаходить шлях до ffmpeg.exe:
    1. Перевіряє локальну папку bin у проєкті
    2. Шукає в системному PATH
    3. Шукає в каталогах WinGet
    """
    project_root = Path(__file__).resolve().parent.parent
    local_ffmpeg = project_root / "bin" / "ffmpeg.exe"
    if local_ffmpeg.is_file():
        return str(local_ffmpeg)
    
    # Перевірка в PATH
    import shutil
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return which_ffmpeg

    # Перевірка у WinGet
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_path = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_path.is_dir():
            candidates = list(winget_path.glob("**/ffmpeg.exe"))
            if candidates:
                return str(candidates[0])
                
    return "ffmpeg"
