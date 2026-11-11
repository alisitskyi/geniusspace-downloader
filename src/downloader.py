import os
import json
import re
import subprocess
import requests
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import yt_dlp

from .api import GeniusSpaceAPI, UnauthorizedError
from .utils import sanitize_filename, format_bytes, get_ffmpeg_path

class CourseDownloader:
    """Менеджер завантаження курсу з Genius.Space"""

    def __init__(
        self,
        api: GeniusSpaceAPI,
        output_dir: str = ".",
        download_videos: bool = True,
        download_files: bool = True,
        video_quality: str = "best",
        optimize_videos: bool = False,
        optimize_crf: int = 26,
        progress_callback: Optional[Callable[[str], None]] = None
    ):
        self.api = api
        self.output_dir = Path(output_dir)
        self.download_videos = download_videos
        self.download_files = download_files
        self.video_quality = video_quality
        self.optimize_videos = optimize_videos
        self.optimize_crf = optimize_crf
        self.progress_callback = progress_callback or print
        self.ffmpeg_path = get_ffmpeg_path()

    def log(self, message: str):
        self.progress_callback(message)

    def download_file(self, url: str, target_path: Path) -> bool:
        """Завантажує файл за посиланням з авто-визначенням розширення та підтримкою Google Drive/Docs"""
        try:
            # 1. Нормалізація посилань Google Drive / Docs / Slides
            default_ext = ""
            if "drive.google.com" in url or "docs.google.com" in url:
                doc_m = re.search(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)", url)
                pres_m = re.search(r"docs\.google\.com/presentation/d/([a-zA-Z0-9_-]+)", url)
                sheet_m = re.search(r"docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
                file_m = re.search(r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)", url) or re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)

                if doc_m:
                    url = f"https://docs.google.com/document/d/{doc_m.group(1)}/export?format=docx"
                    default_ext = ".docx"
                elif pres_m:
                    url = f"https://docs.google.com/presentation/d/{pres_m.group(1)}/export/pdf"
                    default_ext = ".pdf"
                elif sheet_m:
                    url = f"https://docs.google.com/spreadsheets/d/{sheet_m.group(1)}/export?format=xlsx"
                    default_ext = ".xlsx"
                elif file_m:
                    url = f"https://drive.usercontent.google.com/download?id={file_m.group(1)}&export=download"

            # Перевіряємо, чи файл вже існує (якщо у target_path немає розширення, шукаємо кандидати)
            if target_path.suffix:
                candidates = [target_path]
            else:
                candidates = [
                    target_path,
                    target_path.with_suffix(".pdf"),
                    target_path.with_suffix(".docx"),
                    target_path.with_suffix(".pptx"),
                    target_path.with_suffix(".xlsx"),
                    target_path.with_suffix(".zip"),
                ]
                if default_ext:
                    candidates.insert(1, target_path.with_suffix(default_ext))

            for cand in candidates:
                if cand.exists() and cand.stat().st_size > 0:
                    self.log(f"      [Файл вже існує] {cand.name} ({format_bytes(cand.stat().st_size)})")
                    return True

            self.log(f"      [Завантаження файлу] {target_path.name}...")
            target_path.parent.mkdir(parents=True, exist_ok=True)

            with requests.get(url, stream=True, allow_redirects=True, timeout=90) as resp:
                resp.raise_for_status()

                # Визначення розширення з Content-Disposition або Content-Type
                cd = resp.headers.get("Content-Disposition", "")
                ct = resp.headers.get("Content-Type", "").lower()

                ext = ""
                fn_match = re.search(r'filename\*?=(?:UTF-8\'\')?\"?([^;\"]+)\"?', cd)
                if fn_match:
                    cand_name = fn_match.group(1).strip()
                    ext = os.path.splitext(cand_name)[1]

                content_chunks = []
                first_chunk = b""
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        if not first_chunk:
                            first_chunk = chunk
                        content_chunks.append(chunk)

                if not ext:
                    if first_chunk.startswith(b"%PDF"):
                        ext = ".pdf"
                    elif first_chunk.startswith(b"PK\x03\x04"):
                        if "word" in ct or "document" in ct:
                            ext = ".docx"
                        elif "presentation" in ct:
                            ext = ".pptx"
                        elif "sheet" in ct:
                            ext = ".xlsx"
                        else:
                            ext = default_ext or ".zip"
                    elif default_ext:
                        ext = default_ext
                    elif "pdf" in ct:
                        ext = ".pdf"
                    elif "word" in ct:
                        ext = ".docx"
                    elif "presentation" in ct:
                        ext = ".pptx"

                final_path = target_path.with_suffix(ext) if (ext and not target_path.suffix) else target_path

                with open(final_path, "wb") as f:
                    for chunk in content_chunks:
                        f.write(chunk)

            self.log(f"      [Готово] {final_path.name} ({format_bytes(final_path.stat().st_size)})")
            return True
        except Exception as e:
            self.log(f"      [Помилка завантаження файлу] {target_path.name}: {e}")
            return False

    def download_video(self, video_url: str, output_path_no_ext: Path) -> bool:
        """
        Завантажує відеопотік (HLS master.m3u8 або Vimeo) через yt-dlp у форматі MP4
        """
        for ext in [".mp4", ".mkv"]:
            candidate = output_path_no_ext.with_suffix(ext)
            if candidate.exists() and candidate.stat().st_size > 1024 * 1024:  # більше 1 MB
                self.log(f"      [Відео вже існує] {candidate.name} ({format_bytes(candidate.stat().st_size)})")
                return True

        vq = (self.video_quality or "720p").lower().strip()
        if vq in ["720p", "720"]:
            format_str = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
            quality_label = "720p"
        elif vq in ["1080p", "1080"]:
            format_str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
            quality_label = "1080p"
        elif vq in ["480p", "480"]:
            format_str = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
            quality_label = "480p"
        elif vq in ["360p", "360"]:
            format_str = "bestvideo[height<=360]+bestaudio/best[height<=360]/best"
            quality_label = "360p"
        else:
            format_str = "bestvideo+bestaudio/best"
            quality_label = "best"

        self.log(f"      [Завантаження відео ({quality_label})] {output_path_no_ext.name}...")

        ydl_opts = {
            "format": format_str,
            "outtmpl": f"{str(output_path_no_ext)}.%(ext)s",
            "merge_output_format": "mp4",
            "ffmpeg_location": self.ffmpeg_path,
            "http_headers": {
                "Referer": "https://edu.genius.space/",
                "Origin": "https://edu.genius.space",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
            },
            "quiet": False,
            "no_warnings": True,
            "retries": 10,
            "fragment_retries": 10,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            for ext in [".mp4", ".mkv"]:
                saved = output_path_no_ext.with_suffix(ext)
                if saved.exists():
                    self.log(f"      [Готово] Відео збережено: {saved.name} ({format_bytes(saved.stat().st_size)})")
                    if self.optimize_videos:
                        self.optimize_video_file(saved)
                    return True
            return True
        except Exception as e:
            self.log(f"      [Помилка завантаження відео]: {e}")
            return False

    def optimize_video_file(self, video_path: Path) -> bool:
        """
        Оптимізує та стискає навчальне відео через FFmpeg без втрати візуальної чіткості.
        Використовує апаратне прискорення Intel QuickSync (h264_qsv), якщо доступне,
        або якісний CPU кодек libx264.
        """
        if not video_path.exists() or not self.ffmpeg_path:
            return False

        orig_size = video_path.stat().st_size
        if orig_size < 1024 * 1024:  # менше 1 MB
            return False

        temp_out = video_path.with_name(f"{video_path.stem}.temp_opt.mp4")
        if temp_out.exists():
            try:
                temp_out.unlink()
            except Exception:
                pass

        self.log(f"      [Оптимізація...] Стиснення відео (Intel QSV / x264)...")

        # 1. Спроба через апаратне прискорення Intel QuickSync (h264_qsv)
        qsv_cmd = [
            self.ffmpeg_path, "-y", "-i", str(video_path),
            "-c:v", "h264_qsv", "-global_quality", str(self.optimize_crf), "-preset", "medium",
            "-c:a", "aac", "-b:a", "128k",
            str(temp_out)
        ]

        success = False
        try:
            res = subprocess.run(qsv_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=1200)
            if res.returncode == 0 and temp_out.exists() and temp_out.stat().st_size > 1024:
                success = True
        except Exception:
            success = False

        # 2. Якщо QSV не спрацював, надійний CPU fallback (libx264)
        if not success:
            cpu_cmd = [
                self.ffmpeg_path, "-y", "-i", str(video_path),
                "-c:v", "libx264", "-crf", str(self.optimize_crf), "-preset", "faster",
                "-c:a", "aac", "-b:a", "128k",
                str(temp_out)
            ]
            try:
                res = subprocess.run(cpu_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=1800)
                if res.returncode == 0 and temp_out.exists() and temp_out.stat().st_size > 1024:
                    success = True
            except Exception as e:
                self.log(f"      [Попередження] Помилка стиснення: {e}")
                success = False

        if success and temp_out.exists():
            new_size = temp_out.stat().st_size
            # Замінюємо тільки якщо вдалося заощадити розмір
            if new_size < orig_size:
                ratio = (1 - (new_size / orig_size)) * 100
                video_path.unlink()
                temp_out.rename(video_path)
                self.log(f"      [Оптимізовано] {format_bytes(orig_size)} -> {format_bytes(new_size)} (-{ratio:.1f}%)")
                return True
            else:
                self.log(f"      [Інфо] Оригінальне відео вже має оптимальний розмір.")
                temp_out.unlink()
                return False
        else:
            if temp_out.exists():
                try:
                    temp_out.unlink()
                except Exception:
                    pass
            return False

    def optimize_existing_folder(self, folder_path: Path):
        """Оптимізує всі відео у вказаній папці (рекурсивно)"""
        mp4s = list(folder_path.rglob("*.mp4"))
        if not mp4s:
            self.log(f"[Інфо] У папці {folder_path.name} не знайдено .mp4 файлів.")
            return

        self.log(f"\n=======================================================")
        self.log(f"Оптимізація відео у папці: {folder_path.name} (знайдено: {len(mp4s)} відео)")
        self.log(f"=======================================================")

        total_orig = sum(f.stat().st_size for f in mp4s)
        optimized_count = 0

        for idx, mp4_file in enumerate(mp4s, start=1):
            self.log(f"\n[{idx}/{len(mp4s)}] {mp4_file.name}")
            if self.optimize_video_file(mp4_file):
                optimized_count += 1

        total_new = sum(f.stat().st_size for f in mp4s if f.exists())
        saved_bytes = total_orig - total_new
        ratio = (saved_bytes / total_orig * 100) if total_orig > 0 else 0

        self.log(f"\n=======================================================")
        self.log(f"[ГОТОВО] Оптимізацію завершено!")
        self.log(f"Початковий розмір: {format_bytes(total_orig)}")
        self.log(f"Новий розмір:      {format_bytes(total_new)}")
        self.log(f"Заощаджено місця:  {format_bytes(saved_bytes)} (-{ratio:.1f}%)")
        self.log(f"=======================================================\n")

    def download_course(self, course_slug: str, target_dir_name: Optional[str] = None):
        """Головний метод завантаження курсу цілком"""
        self.log(f"Запит структури курсу: {course_slug}...")
        course_data = self.api.get_course_details(course_slug)

        course_name = course_data.get("name") or course_data.get("title") or course_slug
        if target_dir_name:
            course_dir = self.output_dir / target_dir_name
        else:
            course_dir = self.output_dir / sanitize_filename(course_name)

        course_dir.mkdir(parents=True, exist_ok=True)
        self.log(f"Цільова папка курсу: {course_dir.resolve()}")

        modules_data = course_data.get("modules", {})
        modules = modules_data.get("data", []) if isinstance(modules_data, dict) else modules_data
        if not modules:
            self.log("[Увага] Список модулів курсу порожній або доступ обмежено.")
            return

        self.log(f"Знайдено модулів: {len(modules)}")

        toc_lines = [f"# Зміст курсу: {course_dir.name}\n"]

        total_lessons = sum(
            len(m.get("materials", {}).get("data", []) if isinstance(m.get("materials"), dict) else m.get("materials", []))
            for m in modules
        )
        current_lesson_idx = 0

        for m_num, module in enumerate(modules, start=1):
            mod_title = sanitize_filename(module.get("name") or module.get("title") or f"Модуль {m_num}")
            mod_slug = module.get("slug") or str(module.get("id"))
            mod_dir = course_dir / f"{m_num:02d}_{mod_title}"
            mod_dir.mkdir(parents=True, exist_ok=True)

            self.log(f"\n=======================================================")
            self.log(f"[Модуль {m_num}/{len(modules)}] {mod_title}")
            self.log(f"=======================================================")
            toc_lines.append(f"\n## Модуль {m_num:02d}: {mod_title}\n")

            materials_data = module.get("materials", {})
            materials = materials_data.get("data", []) if isinstance(materials_data, dict) else materials_data

            for l_num, mat in enumerate(materials, start=1):
                current_lesson_idx += 1
                mat_name = sanitize_filename(mat.get("name") or mat.get("title") or f"Урок {l_num}")
                mat_slug = mat.get("slug") or str(mat.get("id"))

                lesson_dir = mod_dir / f"{l_num:02d}_{mat_name}"
                lesson_dir.mkdir(parents=True, exist_ok=True)

                self.log(f"\n   ({current_lesson_idx}/{total_lessons}) Урок {l_num}: {mat_name}")
                toc_lines.append(f"- **Урок {l_num:02d}:** {mat_name}")

                # Отримуємо повні деталі уроку
                try:
                    detail = self.api.get_lesson_detail(course_slug, mod_slug, mat_slug)
                    # Якщо раптом є обгортка data, розпаковуємо її
                    if isinstance(detail, dict) and "data" in detail and isinstance(detail["data"], dict):
                        detail = detail["data"]
                except UnauthorizedError as e:
                    self.log(f"\n[КРИТИЧНО] Токен авторизації закінчився на уроці: {mat_name}!")
                    self.log("[!] Оновіть GENIUS_AUTH_TOKEN та GENIUS_SESSION_ID у .env та перезапустіть завантаження.")
                    raise e
                except Exception as e:
                    self.log(f"   [Попередження при отриманні деталей уроку]: {e}")
                    detail = {}

                # 1. Обробка та завантаження відео
                if self.download_videos:
                    videos_raw = detail.get("video", {})
                    videos_list = videos_raw.get("data", []) if isinstance(videos_raw, dict) else videos_raw
                    if not videos_list and isinstance(videos_raw, dict) and "src" in videos_raw:
                        videos_list = [videos_raw]

                    if videos_list:
                        for v_idx, v_item in enumerate(videos_list, start=1):
                            v_src = v_item.get("src") or v_item.get("url") or ""
                            v_suffix = f"_{v_idx}" if len(videos_list) > 1 else ""
                            video_output_path = lesson_dir / f"{mat_name}{v_suffix}"

                            # Якщо це відео R2 (video.genius.space/watch/...)
                            if "video.genius.space/watch/" in v_src:
                                resolved = self.api.resolve_video_stream(v_src)
                                if resolved and "hls_url" in resolved:
                                    self.download_video(resolved["hls_url"], video_output_path)
                                    # Завантажуємо субтитри, якщо є
                                    for sub in resolved.get("subtitles", []):
                                        sub_url = sub.get("src")
                                        if sub_url:
                                            self.download_file(sub_url, lesson_dir / f"субтитри_{sub.get('lang', 'uk')}.vtt")
                                else:
                                    self.log(f"      [Помилка] Не вдалося отримати HLS потік для: {v_src}")
                            elif v_src:
                                # Якщо це посилання на Vimeo, нормалізуємо до embed-формату player.vimeo.com
                                if "vimeo.com" in v_src and "player.vimeo.com" not in v_src:
                                    vm = re.search(r"vimeo\.com/(\d+)(?:/([a-zA-Z0-9]+))?", v_src)
                                    if vm:
                                        vid = vm.group(1)
                                        vh = vm.group(2)
                                        v_src = f"https://player.vimeo.com/video/{vid}?h={vh}" if vh else f"https://player.vimeo.com/video/{vid}"
                                self.download_video(v_src, video_output_path)
                    else:
                        self.log(f"      [Інфо] У цьому уроці немає відео (текстовий матеріал/завдання).")

                # 2. Обробка та завантаження прикріплених файлів
                if self.download_files:
                    files_data = detail.get("files", {})
                    files_list = files_data.get("data", []) if isinstance(files_data, dict) else files_data
                    if files_list:
                        self.log(f"      Знайдено файлів: {len(files_list)}")
                        for f_idx, file_item in enumerate(files_list, start=1):
                            file_url = file_item.get("url") or file_item.get("src") or file_item.get("download_url")
                            file_name = sanitize_filename(
                                file_item.get("name") or file_item.get("title") or os.path.basename(file_url or f"file_{f_idx}")
                            )
                            # Якщо у назві файлу немає розширення, пробуємо взяти його з URL
                            if not Path(file_name).suffix and file_url:
                                url_ext = os.path.splitext(file_url.split("?")[0])[1]
                                if url_ext:
                                    file_name = f"{file_name}{url_ext}"
                            if file_url:
                                self.download_file(file_url, lesson_dir / file_name)

                # 3. Збереження опису/тексту уроку, якщо він є
                body_content = detail.get("description") or detail.get("body") or detail.get("content") or mat.get("description")
                if body_content and isinstance(body_content, str) and len(body_content.strip()) > 10:
                    info_file = lesson_dir / "конспект_уроку.txt"
                    if not info_file.exists():
                        with open(info_file, "w", encoding="utf-8") as f:
                            f.write(f"Назва: {mat_name}\n\n{body_content}\n")

        # Зберігаємо файл змісту TOC.md
        toc_file = course_dir / "ЗМІСТ_КУРСУ.md"
        with open(toc_file, "w", encoding="utf-8") as f:
            f.write("\n".join(toc_lines))

        self.log(f"\n=======================================================")
        self.log(f"[УСПІШНО] Завантаження курсу '{course_dir.name}' повністю завершено!")
        self.log(f"Всі матеріали збережено в: {course_dir.resolve()}")
        self.log(f"Згенеровано файл зі змістом: {toc_file.resolve()}")
        self.log(f"=======================================================\n")
