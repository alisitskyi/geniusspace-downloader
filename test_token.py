import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from src.utils import setup_console_encoding, get_ffmpeg_path
from src.api import GeniusSpaceAPI, UnauthorizedError, APIError

setup_console_encoding()

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console(legacy_windows=False)

def test():
    load_dotenv(override=True)
    token = os.getenv("GENIUS_AUTH_TOKEN", "").strip()
    session_id = os.getenv("GENIUS_SESSION_ID", "").strip() or None

    console.print(Panel.fit("[bold blue]Перевірка з'єднання та токена Genius.Space[/bold blue]"))

    ffmpeg_p = get_ffmpeg_path()
    console.print(f"[bold green][OK][/bold green] FFmpeg знайдено за адресою: [cyan]{ffmpeg_p}[/cyan]")

    if not token:
        console.print("[bold red][!] Токен GENIUS_AUTH_TOKEN не знайдено в файлі .env[/bold red]")
        return

    console.print(f"Токен: [cyan]{token[:8]}...{token[-6:]}[/cyan], Session-Id: [cyan]{session_id or 'немає'}[/cyan]")
    console.print("Перевірка підключення до API курсів...")

    api = GeniusSpaceAPI(token, session_id)

    try:
        courses = api.get_my_courses()
        console.print(f"[bold green][OK] Авторизація успішна! З'єднання з Genius.Space встановлено.[/bold green]")

        if courses:
            table = Table(title="Ваші доступні курси", show_header=True, header_style="bold magenta")
            table.add_column("№", style="dim", width=4)
            table.add_column("Назва курсу", style="bold")
            table.add_column("Slug (для завантаження)", style="cyan")
            table.add_column("Прогрес", justify="right")

            for idx, c in enumerate(courses, start=1):
                title = c.get("title") or "Без назви"
                slug = c.get("slug") or "немає"
                prog = f"{c.get('progress') or 0}%"
                table.add_row(str(idx), title, slug, prog)

            console.print(table)
        else:
            console.print("[yellow]Курсів у списку my/courses не знайдено, але доступ до курсу nocodedeveloper є![/yellow]")

        console.print(f"\n[green]Усе готово до роботи! Для завантаження запустіть:[/green] [bold]run.bat[/bold]\n")

    except UnauthorizedError:
        console.print("[bold red][!] Помилка: Токен або Session-Id недійсні або прострочені.[/bold red]")
    except Exception as e:
        console.print(f"[red]Помилка перевірки: {e}[/red]")

if __name__ == "__main__":
    test()
