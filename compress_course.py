import os
import sys
import shutil
import subprocess
import time
import json
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

SRC_DIR = r"D:\VS_Code_AL\Education\GeniusSpace_No-Code Developer"
DST_DIR = r"D:\VS_Code_AL\Education\GeniusSpace_No-Code Developer (Compressed)"
STATUS_FILE = os.path.join(DST_DIR, "compression_status.json")

FFMPEG = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe")
if not os.path.exists(FFMPEG):
    FFMPEG = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe")

FFPROBE = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffprobe.exe")
if not os.path.exists(FFPROBE):
    FFPROBE = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-essentials_build\bin\ffprobe.exe")

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".ts", ".m4v"}

def get_duration(fpath):
    try:
        cmd = [FFPROBE, "-v", "quiet", "-print_format", "json", "-show_format", fpath]
        res = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
        data = json.loads(res.stdout)
        return float(data.get("format", {}).get("duration", 0))
    except Exception:
        return 0

def copy_non_video_files():
    print("=== Checking non-video files (.pdf, .txt, .vtt, etc.) ===")
    copied = 0
    for root, dirs, files in os.walk(SRC_DIR):
        rel_root = os.path.relpath(root, SRC_DIR)
        target_root = os.path.join(DST_DIR, rel_root)
        os.makedirs(target_root, exist_ok=True)
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in VIDEO_EXTS:
                src_file = os.path.join(root, f)
                dst_file = os.path.join(target_root, f)
                if not os.path.exists(dst_file) or os.path.getsize(dst_file) != os.path.getsize(src_file):
                    shutil.copy2(src_file, dst_file)
                    copied += 1
    if copied > 0:
        print(f"Non-video files synced: {copied}")
    else:
        print("Non-video files already synced.")

def find_all_videos():
    videos = []
    for root, dirs, files in os.walk(SRC_DIR):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in VIDEO_EXTS:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, SRC_DIR)
                size_b = os.path.getsize(full_path)
                videos.append((full_path, rel_path, size_b))
    return sorted(videos, key=lambda x: x[1])

def run_ffmpeg(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors='replace')
    try:
        out, err = p.communicate()
        return p.returncode, err
    except BaseException:
        p.kill()
        p.wait()
        raise

def compress_single_video(src_path, dst_path):
    target_dir = os.path.dirname(dst_path)
    os.makedirs(target_dir, exist_ok=True)
    
    base_name = os.path.basename(dst_path)
    temp_path = os.path.join(target_dir, f"~temp_{base_name}")
    if os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except OSError:
            pass

    # Intel QSV HEVC
    cmd_qsv = [
        FFMPEG, "-y",
        "-i", src_path,
        "-c:v", "hevc_qsv",
        "-global_quality", "24",
        "-preset", "medium",
        "-c:a", "aac",
        "-b:a", "128k",
        "-tag:v", "hvc1",
        temp_path
    ]
    
    rc, err = run_ffmpeg(cmd_qsv)
    
    # Fallback to software libx265 if QSV fails
    if rc != 0:
        print("    [QSV failed, falling back to libx265...]")
        cmd_cpu = [
            FFMPEG, "-y",
            "-i", src_path,
            "-c:v", "libx265",
            "-crf", "25",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "128k",
            "-tag:v", "hvc1",
            temp_path
        ]
        rc, err = run_ffmpeg(cmd_cpu)
        if rc != 0:
            print(f"    [Error]: {err[-300:]}")
            if os.path.exists(temp_path):
                try: os.remove(temp_path)
                except OSError: pass
            return False

    # Verify duration
    src_dur = get_duration(src_path)
    temp_dur = get_duration(temp_path)
    if src_dur > 0 and abs(src_dur - temp_dur) > 3.0:
        print(f"    [Warning]: Duration mismatch! Source: {src_dur:.1f}s vs Output: {temp_dur:.1f}s")
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except OSError: pass
        return False

    # Move temp to final
    if os.path.exists(dst_path):
        try: os.remove(dst_path)
        except OSError: pass
    os.rename(temp_path, dst_path)
    return True

def update_status(data):
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def run(limit=None):
    copy_non_video_files()
    videos = find_all_videos()
    total_videos = len(videos)
    total_orig_bytes = sum(s for _, _, s in videos)
    print(f"\nFound {total_videos} videos ({total_orig_bytes / (1024**3):.2f} GB)")
    
    if limit:
        videos = videos[:limit]
        print(f"Processing {limit} file(s)")

    start_all = time.time()
    processed_orig_bytes = 0
    processed_new_bytes = 0
    completed_count = 0
    
    for idx, (src_path, rel_path, size_b) in enumerate(videos, 1):
        dst_path = os.path.join(DST_DIR, rel_path)
        
        # Check if already done
        if os.path.exists(dst_path):
            dst_size = os.path.getsize(dst_path)
            src_dur = get_duration(src_path)
            dst_dur = get_duration(dst_path)
            if src_dur > 0 and abs(src_dur - dst_dur) <= 3.0:
                print(f"[{idx}/{len(videos)}] Already done: {rel_path} ({dst_size / 1024**2:.1f} MB)")
                processed_orig_bytes += size_b
                processed_new_bytes += dst_size
                completed_count += 1
                update_status({
                    "updated_at": datetime.now().isoformat(),
                    "completed_count": completed_count,
                    "total_count": len(videos),
                    "current_file": rel_path,
                    "original_gb": round(processed_orig_bytes / 1024**3, 2),
                    "compressed_gb": round(processed_new_bytes / 1024**3, 2),
                    "saved_gb": round((processed_orig_bytes - processed_new_bytes) / 1024**3, 2)
                })
                continue

        print(f"\n[{idx}/{len(videos)}] Compressing: {rel_path}")
        print(f"    Original: {size_b / 1024**2:.1f} MB")
        
        t0 = time.time()
        ok = compress_single_video(src_path, dst_path)
        elapsed = time.time() - t0
        
        if ok and os.path.exists(dst_path):
            new_size = os.path.getsize(dst_path)
            processed_orig_bytes += size_b
            processed_new_bytes += new_size
            completed_count += 1
            saved_mb = (size_b - new_size) / 1024**2
            ratio = (1 - (new_size / size_b)) * 100
            print(f"    Done in {elapsed:.1f}s | New: {new_size / 1024**2:.1f} MB (-{ratio:.1f}%) | Saved: {saved_mb:.1f} MB")
            
            total_saved_gb = (processed_orig_bytes - processed_new_bytes) / 1024**3
            print(f"    Total saved so far: {total_saved_gb:.2f} GB | Overall: {completed_count}/{len(videos)} videos")
            
            update_status({
                "updated_at": datetime.now().isoformat(),
                "completed_count": completed_count,
                "total_count": len(videos),
                "current_file": rel_path,
                "original_gb": round(processed_orig_bytes / 1024**3, 2),
                "compressed_gb": round(processed_new_bytes / 1024**3, 2),
                "saved_gb": round(total_saved_gb, 2)
            })
        else:
            print(f"    FAILED to compress: {rel_path}")

    total_time = time.time() - start_all
    print("\n" + "="*50)
    print(f"Finished in {total_time/60:.1f} minutes")
    print(f"Processed: {completed_count}/{len(videos)} videos")
    print(f"Original size:    {processed_orig_bytes / 1024**3:.2f} GB")
    print(f"Compressed size:  {processed_new_bytes / 1024**3:.2f} GB")
    print(f"Total space saved: {(processed_orig_bytes - processed_new_bytes) / 1024**3:.2f} GB")
    print("="*50)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Limit number of videos to process")
    args = parser.parse_args()
    run(limit=args.limit)
