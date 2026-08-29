"""
Настройки. Всё берётся из окружения — в коде нет ни одного секрета.

Данные (база, загрузки) намеренно лежат ВНЕ папки репозитория:
update.sh на сервере делает git reset --hard, и всё лишнее внутри
клона было бы стёрто при первом же обновлении сайта.
"""
import os
from pathlib import Path


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("AVERIX_DATA_DIR", "/var/www/averix-data"))
DB_PATH = DATA_DIR / "averix.db"
UPLOAD_DIR = DATA_DIR / "uploads"

# В разработке сайт открывается по http, и cookie с флагом Secure не долетит.
# На сервере флаг обязателен — иначе сессию можно перехватить.
SECURE_COOKIES = _flag("AVERIX_SECURE_COOKIES", True)
DEBUG = _flag("AVERIX_DEBUG", False)

SESSION_COOKIE = "averix_session"
SESSION_HOURS = 12

# Защита от перебора пароля
LOGIN_WINDOW_MINUTES = 15
LOGIN_SLOWDOWN_AFTER = 3      # после стольких неудач — задержка
LOGIN_BLOCK_AFTER = 5         # после стольких — отказ до конца окна

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
