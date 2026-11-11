import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from src.utils import setup_console_encoding, get_ffmpeg_path
from src.api import GeniusSpaceAPI, UnauthorizedError, APIError
from src.downloader import CourseDownloader

setup_console_encoding()

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

def ensure_authenticated() -> GeniusSpaceAPI:
    load_dotenv(override=True)
    token = os.getenv("GENIUS_AUTH_TOKEN", "").strip()
    session_id = os.getenv("GENIUS_SESSION_ID", "").strip() or None

    if token:
        api = GeniusSpaceAPI(token, session_id)
        try:
            api.validate_connection()
            console.print("[bold green][OK] Авторизація успішна![/bold green]\n")
            return api
        except UnauthorizedError:
            console.print("[bold red][!] Токен у .env застарів або недійсний.[/bold red]")

    while True:
        console.print(Panel(
            "[bold yellow]Необхідні дані авторизації![/bold yellow]\n\n"
            "Вставте токен із браузера (значення authorization):",
            title="Авторизація"
        ))
        token_input = Prompt.ask("[bold green]GENIUS_AUTH_TOKEN[/bold green]").strip()
        sid_input = Prompt.ask("[bold green]GENIUS_SESSION_ID[/bold green]").strip()
        if not token_input:
            console.print("[red]Вихід з програми.[/red]")
            sys.exit(1)

        api = GeniusSpaceAPI(token_input, sid_input or None)
        try:
            api.validate_connection()
            console.print("[bold green][OK] Успішно підключено![/bold green]\n")
            # зберігаємо в .env
            env_path = Path(__file__).parent / ".env"
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(f"GENIUS_AUTH_TOKEN={token_input}\n")
                f.write(f"GENIUS_SESSION_ID={sid_input}\n")
                f.write("DEFAULT_COURSE_SLUG=nocodedeveloper\n")
                f.write("DEFAULT_COURSE_DIR=GeniusSpace_No-Code Developer\n")
                f.write("DOWNLOAD_BASE_DIR=.\n")
                f.write("DOWNLOAD_VIDEOS=true\n")
                f.write("DOWNLOAD_FILES=true\n")
                f.write("VIDEO_QUALITY=720p\n")
            return api
        except UnauthorizedError:
            console.print("[bold red][!] Введені дані не підійшли. Спробуйте ще раз.[/bold red]")

def main():
    console.print(Panel.fit(
        "[bold cyan]GENIUS.SPACE COURSE DOWNLOADER[/bold cyan]\n"
        "[dim]Автоматичне збереження курсу: Відео (1080p Full HD) + Презентації + Конспекти[/dim]",
        border_style="cyan"
    ))

    ffmpeg_p = get_ffmpeg_path()
    console.print(f"[green][OK][/green] FFmpeg: [dim]{ffmpeg_p}[/dim]")

    api = ensure_authenticated()

    default_slug = os.getenv("DEFAULT_COURSE_SLUG", "nocodedeveloper").strip()
    default_dir_name = os.getenv("DEFAULT_COURSE_DIR", "GeniusSpace_No-Code Developer").strip()
    base_download_dir = os.getenv("DOWNLOAD_BASE_DIR", ".").strip()
    download_videos = os.getenv("DOWNLOAD_VIDEOS", "true").lower() == "true"
    download_files = os.getenv("DOWNLOAD_FILES", "true").lower() == "true"
    video_quality = os.getenv("VIDEO_QUALITY", "720p").strip()
    optimize_videos = os.getenv("OPTIMIZE_VIDEOS", "true").lower() == "true"
    optimize_crf = int(os.getenv("OPTIMIZE_CRF", "26"))

    target_path_display = (Path(__file__).parent / base_download_dir / default_dir_name).resolve()
    console.print(f"[bold]Цільова папка курсу:[/bold] [cyan]{target_path_display}[/cyan]")
    console.print(f"[bold]Авто-оптимізація відео:[/bold] [green]{'УВІМКНЕНО (Intel QSV / x264, стиснення в 3-5 разів)' if optimize_videos else 'ВИМКНЕНО'}[/green]\n")

    while True:
        console.print("[bold]Оберіть дію:[/bold]")
        console.print(f"  [cyan]1.[/cyan] Завантажити курс [bold yellow]{default_slug}[/bold yellow] (у папку [green]{default_dir_name}[/green])")
        console.print("  [cyan]2.[/cyan] Переглянути всі мої доступні курси (78 курсів!) та обрати для завантаження")
        console.print("  [cyan]3.[/cyan] Ввести довільний slug курсу вручну")
        console.print("  [cyan]4.[/cyan] Оптимізувати вже завантажену папку курсу (зменшити розмір відео в 3-5 разів)")
        console.print("  [cyan]5.[/cyan] Налаштування (.env)")
        console.print("  [cyan]6.[/cyan] Вихід")

        choice = Prompt.ask("\nВаш вибір", choices=["1", "2", "3", "4", "5", "6"], default="1")

        target_slug = None
        target_dir = None

        if choice == "1":
            target_slug = default_slug
            target_dir = default_dir_name

        elif choice == "2":
            console.print("\n[dim]Запит списку курсів на акаунті...[/dim]")
            try:
                courses = api.get_my_courses()
                if not courses:
                    console.print("[yellow]Не знайдено курсів у вашому профілі.[/yellow]\n")
                    continue

                table = Table(title="Ваші доступні курси", show_header=True, header_style="bold magenta")
                table.add_column("№", style="dim", width=4)
                table.add_column("Назва курсу", style="bold")
                table.add_column("Slug", style="cyan")

                for idx, c in enumerate(courses, start=1):
                    table.add_row(str(idx), c.get("title") or "Без назви", c.get("slug") or "")

                console.print(table)
                idx_choice = Prompt.ask(
                    "Введіть номер курсу для завантаження (або 0 для повернення)",
                    default="1"
                )
                try:
                    selected_num = int(idx_choice)
                    if 1 <= selected_num <= len(courses):
                        target_slug = courses[selected_num - 1].get("slug")
                    else:
                        continue
                except ValueError:
                    continue

            except Exception as e:
                console.print(f"[red]Помилка отримання списку курсів: {e}[/red]\n")
                continue

        elif choice == "3":
            target_slug = Prompt.ask("Введіть slug курсу (наприклад, nocodedeveloper)").strip()

        elif choice == "4":
            # Пошук папок курсів
            base_dir = (Path(__file__).parent / base_download_dir).resolve()
            course_dirs = [d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith("GeniusSpace_")]
            if not course_dirs:
                console.print("[yellow]Не знайдено завантажених папок курсів у робочій директорії.[/yellow]\n")
                continue

            console.print("\n[bold]Оберіть папку для оптимізації відео:[/bold]")
            for idx, d in enumerate(course_dirs, start=1):
                mp4_count = len(list(d.rglob("*.mp4")))
                sz_gb = sum(f.stat().st_size for f in d.rglob("*.mp4")) / (1024**3)
                console.print(f"  [cyan]{idx}.[/cyan] {d.name} ({mp4_count} відео, {sz_gb:.2f} ГБ)")

            f_choice = Prompt.ask("Введіть номер папки (або 0 для скасування)", default="1")
            try:
                f_idx = int(f_choice)
                if 1 <= f_idx <= len(course_dirs):
                    opt_folder = course_dirs[f_idx - 1]
                    downloader = CourseDownloader(
                        api=api,
                        output_dir=base_download_dir,
                        optimize_videos=True,
                        optimize_crf=optimize_crf,
                        progress_callback=lambda msg: console.print(msg)
                    )
                    downloader.optimize_existing_folder(opt_folder)
            except ValueError:
                pass
            continue

        elif choice == "5":
            console.print(Panel(
                f"Базова папка: [bold]{base_download_dir}[/bold]\n"
                f"Папка курсу: [bold]{default_dir_name}[/bold]\n"
                f"Завантажувати відео: [bold]{download_videos}[/bold]\n"
                f"Завантажувати файли: [bold]{download_files}[/bold]\n"
                f"Якість відео: [bold]{video_quality}[/bold]\n"
                f"Авто-оптимізація відео: [bold]{optimize_videos}[/bold] (CRF: {optimize_crf})\n"
                f"FFmpeg: [bold]{ffmpeg_p}[/bold]",
                title="Поточні налаштування (.env)"
            ))
            continue

        elif choice == "6":
            console.print("[green]До побачення![/green]")
            break

        if target_slug:
            downloader = CourseDownloader(
                api=api,
                output_dir=base_download_dir,
                download_videos=download_videos,
                download_files=download_files,
                video_quality=video_quality,
                optimize_videos=optimize_videos,
                optimize_crf=optimize_crf,
                progress_callback=lambda msg: console.print(msg)
            )
            console.print(f"\n[bold green]Починаємо завантаження курсу '{target_slug}'...[/bold green]\n")
            try:
                downloader.download_course(target_slug, target_dir_name=target_dir)
            except Exception as e:
                console.print(f"[bold red]Сталася помилка під час завантаження:[/bold red] {e}")

            console.print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Завантаження перервано користувачем.[/yellow]")
