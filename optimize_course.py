import os
import sys
import subprocess
from pathlib import Path

# Setup UTF-8 console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def format_bytes(bytes_int: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_int < 1024.0:
            return f"{bytes_int:.2f} {unit}"
        bytes_int /= 1024.0
    return f"{bytes_int:.2f} PB"

def get_ffmpeg_path() -> str:
    local_ff = Path(__file__).parent / "bin" / "ffmpeg.exe"
    if local_ff.exists():
        return str(local_ff.resolve())
    return "ffmpeg"

def optimize_file(ffmpeg_path: str, video_path: Path, crf: int = 26) -> bool:
    orig_size = video_path.stat().st_size
    if orig_size < 1024 * 1024:
        return False

    temp_out = video_path.with_name(f"{video_path.stem}.temp_opt.mp4")
    if temp_out.exists():
        try:
            temp_out.unlink()
        except Exception:
            pass

    # 1. Спроба апаратного прискорення Intel QuickSync (h264_qsv)
    cmd_qsv = [
        ffmpeg_path, "-y", "-i", str(video_path),
        "-c:v", "h264_qsv", "-global_quality", str(crf), "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k",
        str(temp_out)
    ]

    success = False
    try:
        res = subprocess.run(cmd_qsv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=1800)
        if res.returncode == 0 and temp_out.exists() and temp_out.stat().st_size > 1024:
            success = True
    except Exception:
        success = False

    # 2. Якщо QSV недоступний — CPU libx264
    if not success:
        cmd_cpu = [
            ffmpeg_path, "-y", "-i", str(video_path),
            "-c:v", "libx264", "-crf", str(crf), "-preset", "faster",
            "-c:a", "aac", "-b:a", "128k",
            str(temp_out)
        ]
        try:
            res = subprocess.run(cmd_cpu, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=2400)
            if res.returncode == 0 and temp_out.exists() and temp_out.stat().st_size > 1024:
                success = True
        except Exception as e:
            print(f"      [Помилка стиснення]: {e}")
            success = False

    if success and temp_out.exists():
        new_size = temp_out.stat().st_size
        if new_size < orig_size:
            ratio = (1 - (new_size / orig_size)) * 100
            video_path.unlink()
            temp_out.rename(video_path)
            print(f"      [OK] Стиснуто: {format_bytes(orig_size)} -> {format_bytes(new_size)} (-{ratio:.1f}%)")
            return True
        else:
            print(f"      [Інфо] Оригінал вже має оптимальний розмір.")
            temp_out.unlink()
            return False
    else:
        if temp_out.exists():
            try:
                temp_out.unlink()
            except Exception:
                pass
        return False

def optimize_directory(target_dir: Path, crf: int = 26):
    ffmpeg = get_ffmpeg_path()
    mp4s = list(target_dir.rglob("*.mp4"))
    if not mp4s:
        print(f"[Увага] У папці {target_dir} не знайдено .mp4 файлів.")
        return

    print("=" * 60)
    print(f"Оптимізація відео: {target_dir.name}")
    print(f"Знайдено відеофайлів: {len(mp4s)}")
    print(f"Використовується FFmpeg: {ffmpeg}")
    print("=" * 60)

    total_orig = sum(f.stat().st_size for f in mp4s)
    optimized_count = 0

    for idx, f in enumerate(mp4s, start=1):
        print(f"\n[{idx}/{len(mp4s)}] {f.name}")
        if optimize_file(ffmpeg, f, crf):
            optimized_count += 1

    total_new = sum(f.stat().st_size for f in target_dir.rglob("*.mp4"))
    saved = total_orig - total_new
    ratio = (saved / total_orig * 100) if total_orig > 0 else 0

    print("\n" + "=" * 60)
    print(f"[УСПІШНО] Оптимізацію завершено!")
    print(f"Оптимізовано відео:   {optimized_count}/{len(mp4s)}")
    print(f"Початковий розмір:    {format_bytes(total_orig)}")
    print(f"Кінцевий розмір:      {format_bytes(total_new)}")
    print(f"Заощаджено місця:     {format_bytes(saved)} (-{ratio:.1f}%)")
    print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_path = Path(sys.argv[1]).resolve()
    else:
        base = Path(__file__).parent
        courses = [d for d in base.iterdir() if d.is_dir() and d.name.startswith("GeniusSpace_")]
        if not courses:
            print("Не знайдено папок з курсами.")
            sys.exit(0)
        print("Оберіть папку для оптимізації:")
        for i, c in enumerate(courses, 1):
            sz = sum(f.stat().st_size for f in c.rglob("*.mp4")) / (1024**3)
            print(f"  {i}. {c.name} ({sz:.2f} ГБ)")
        choice = input("\nНомер папки: ").strip()
        try:
            target_path = courses[int(choice) - 1]
        except Exception:
            print("Невірний вибір.")
            sys.exit(0)

    optimize_directory(target_path)
