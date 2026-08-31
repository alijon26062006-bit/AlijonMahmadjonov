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
# Разрешить вход по http. Только для разработки: по http пароль
# передаётся открытым текстом. На сервере включать нельзя.
ALLOW_INSECURE = _flag("AVERIX_ALLOW_INSECURE", False)
DEBUG = _flag("AVERIX_DEBUG", False)

# Адрес сайта нужен для canonical и og-тегов. На сервере задаётся
# в systemd, чтобы смена домена не требовала правки кода.
SITE_URL = os.environ.get("AVERIX_SITE_URL", "https://averix.dev").rstrip("/")

# Уведомления в Telegram. Токен живёт только здесь, на сервере:
# во фронтенд он не попадает никогда. Если переменных нет, формы
# работают как обычно — просто без сообщения владельцу.
TELEGRAM_TOKEN = os.environ.get("AVERIX_TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT = os.environ.get("AVERIX_TELEGRAM_CHAT", "").strip()

# Почта. Нужна только маркетплейсу: подтверждение адреса и восстановление
# пароля. Без этих переменных сайт работает как обычно, а восстановление
# пароля недоступно — притворяться, что письмо ушло, мы не будем.
SMTP_HOST = os.environ.get("AVERIX_SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("AVERIX_SMTP_PORT", "587") or 587)
SMTP_USER = os.environ.get("AVERIX_SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("AVERIX_SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("AVERIX_SMTP_FROM", "").strip()
SMTP_TLS = _flag("AVERIX_SMTP_TLS", True)

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
