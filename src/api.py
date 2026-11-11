import re
import requests
from typing import Dict, Any, List, Optional

class APIError(Exception):
    """Базовий клас для помилок Genius API"""
    def __init__(self, message: str, status_code: Optional[int] = None, data: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.data = data

class UnauthorizedError(APIError):
    """Помилка 401 Unauthorized (недійсний або прострочений токен)"""
    pass

class NotFoundError(APIError):
    """Помилка 404 (курс або урок не знайдено)"""
    pass

class GeniusSpaceAPI:
    """Клієнт для роботи з REST API Genius.Space"""

    COURSE_API = "https://course.genius.space/external"
    USER_API = "https://user.genius.space/external"
    EDU_API = "https://edu.genius.space"

    def __init__(self, token: str, session_id: Optional[str] = None):
        self.token = token.strip()
        self.session_id = session_id.strip() if session_id else None
        self.session = requests.Session()
        self._update_headers()

    def _update_headers(self):
        clean_token = self.token
        if clean_token.lower().startswith("bearer "):
            clean_token = clean_token[7:].strip()

        headers = {
            "Authorization": f"Bearer {clean_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Locale": "uk",
            "Country-Id": "242",
            "Api-Version": "v1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
            "Origin": "https://edu.genius.space",
            "Referer": "https://edu.genius.space/"
        }
        if self.session_id:
            headers["Session-Id"] = self.session_id
        self.session.headers.update(headers)

    def set_token(self, token: str, session_id: Optional[str] = None):
        self.token = token.strip()
        if session_id:
            self.session_id = session_id.strip()
        self._update_headers()

    def _request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        try:
            resp = self.session.request(method, url, timeout=25, **kwargs)
        except requests.RequestException as e:
            raise APIError(f"Мережева помилка при підключенні до Genius.Space: {e}")

        # Якщо сервер оновив Session-Id у відповіді, зберігаємо його
        new_sid = resp.headers.get("Session-Id")
        if new_sid:
            self.session_id = new_sid
            self.session.headers["Session-Id"] = new_sid

        if resp.status_code == 401:
            raise UnauthorizedError(
                "Помилка авторизації (401 Unauthorized). "
                "Токен або Session-Id застаріли. Оновіть їх у файлі .env",
                status_code=401
            )
        elif resp.status_code == 404:
            raise NotFoundError(f"Об'єкт не знайдено (404 Not Found): {url}", status_code=404)
        elif resp.status_code >= 400:
            raise APIError(
                f"Помилка сервера Genius.Space (HTTP {resp.status_code}): {resp.text[:200]}",
                status_code=resp.status_code
            )

        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}

    def validate_connection(self) -> Dict[str, Any]:
        """Перевіряє доступність курсів за цим токеном"""
        url = f"{self.COURSE_API}/my/courses?include=course,rating"
        return self._request("GET", url)

    def get_my_courses(self) -> List[Dict[str, Any]]:
        """Отримує список доступних курсів"""
        url = (
            f"{self.COURSE_API}/my/courses"
            "?skip=0&limit=100&include=course,course.image,rating"
        )
        res = self._request("GET", url)
        items = res.get("data", [])
        result = []
        for item in items:
            course = item.get("course", {}).get("data") or item
            result.append({
                "id": course.get("id"),
                "title": course.get("name") or course.get("title"),
                "slug": course.get("slug"),
                "category": course.get("category"),
                "progress": item.get("progress"),
                "status": item.get("status")
            })
        return result

    def get_course_details(self, course_slug: str) -> Dict[str, Any]:
        """Отримує дерево курсу (модулі та уроки)"""
        url = (
            f"{self.COURSE_API}/courses/{course_slug}"
            "?use_as_id=slug&include=modules.materials"
        )
        res = self._request("GET", url)
        return res.get("data", {})

    def get_lesson_detail(self, course_slug: str, module_slug: str, lesson_slug: str) -> Dict[str, Any]:
        """
        Отримує повну інформацію про урок: відео, файли, опис
        """
        url = (
            f"{self.COURSE_API}/courses/{course_slug}/modules/{module_slug}/lessons/{lesson_slug}"
            "?use_as_id=slug&include=video,video.chapters,video.image,userLesson,speakers,files,course"
        )
        res = self._request("GET", url)
        return res.get("data", {})

    def resolve_video_stream(self, video_src: str) -> Optional[Dict[str, Any]]:
        """
        Якщо відео відтворюється через R2 (https://video.genius.space/watch/<id>),
        робить запит до внутрішнього API /api/video/play?lessonId=<id>
        і повертає підписане посилання на master.m3u8 з субтитрами.
        """
        watch_match = re.search(r'video\.genius\.space/watch/(\d+)', video_src)
        if watch_match:
            watch_id = watch_match.group(1)
            play_api_url = f"{self.EDU_API}/api/video/play?lessonId={watch_id}"
            try:
                play_res = self._request("GET", play_api_url)
                if play_res and "src" in play_res:
                    return {
                        "hls_url": play_res["src"],
                        "subtitles": play_res.get("textTracks", []),
                        "duration": play_res.get("durationSec")
                    }
            except Exception:
                pass
        return None
