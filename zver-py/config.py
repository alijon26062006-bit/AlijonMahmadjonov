"""Настройки. Читаются из .env рядом с проектом.

.env создаёт установщик из вашего config.php — вручную ключи вводить не нужно.
Файл .env в git не попадает (см. .gitignore) и имеет права 600.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_env(path: Path) -> None:
    """Простой парсер .env: KEY=value, кавычки снимаются, # — комментарий."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        # переменные окружения имеют приоритет над файлом
        os.environ.setdefault(key, val)


_load_env(BASE_DIR / ".env")


def _req(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        raise SystemExit(
            f"В .env не задан {key}.\n"
            f"Проверьте файл {BASE_DIR / '.env'} — его создаёт install-py.sh "
            f"из вашего config.php."
        )
    return val


def _ids(key: str) -> list[int]:
    out: list[int] = []
    for part in os.environ.get(key, "").replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.append(int(part))
    return out


BOT_TOKEN: str = _req("BOT_TOKEN")
ADMINS: list[int] = _ids("ADMINS")

DB_HOST: str = os.environ.get("DB_HOST", "localhost")
DB_PORT: int = int(os.environ.get("DB_PORT", "3306") or 3306)
DB_NAME: str = _req("DB_NAME")
DB_USER: str = _req("DB_USER")
DB_PASS: str = os.environ.get("DB_PASS", "")

# Валюта и связь — при первом запуске подхватываются из таблицы z_settings,
# значения ниже используются только если в базе пусто.
CURRENCY: str = os.environ.get("CURRENCY", "TJS")
SUPPORT: str = os.environ.get("SUPPORT", "")

# Ключи внешних сервисов. В ядре не используются — понадобятся, когда
# будем подключать FazerCards и проверку ников. Читаются заранее, чтобы
# установщик переносил их из config.php один раз и навсегда.
FZ_KEY: str = os.environ.get("FZ_KEY", "")
FZ_HOOK: str = os.environ.get("FZ_HOOK", "")
FZ_BASE: str = os.environ.get("FZ_BASE", "https://api.fzr.cards/api/v2")
GS_KEY: str = os.environ.get("GS_KEY", "")
FT_ID: str = os.environ.get("FT_ID", "")
FT_KEY: str = os.environ.get("FT_KEY", "")

DEBUG: bool = os.environ.get("DEBUG", "0").strip().lower() in ("1", "true", "yes")

if not ADMINS:
    raise SystemExit("В .env не задан ADMINS — некому подтверждать заказы.")
