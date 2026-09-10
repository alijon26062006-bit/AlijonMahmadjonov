"""Настройки счётчика. Нужен только токен бота — больше ничего платного."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent.parent

FONT_CANDIDATES = (
    "assets/fonts/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/local/share/fonts/DejaVuSans.ttf",
    "/Library/Fonts/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "C:/Windows/Fonts/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
)
FONT_BOLD_CANDIDATES = (
    "assets/fonts/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/local/share/fonts/DejaVuSans-Bold.ttf",
    "/Library/Fonts/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)


def _first_existing(paths: tuple[str, ...]) -> str | None:
    for raw in paths:
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT / path
        if path.is_file():
            return str(path)
    return None


def _parse_ids(raw: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError as exc:
            raise ValueError(f"COUNTER_ALLOWED_USER_IDS: {part!r} — это не число") from exc
    return frozenset(ids)


def _load_dotenv(path: Path) -> None:
    """Простое чтение .env, без сторонних библиотек."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Config:
    telegram_token: str
    allowed_user_ids: frozenset[int]
    data_dir: Path
    model_path: Path
    tz_name: str = "Asia/Tashkent"
    unit_name: str = "шт"
    max_voice_seconds: int = 60
    max_amount: int = 1_000_000          # больше — переспросим, вдруг ослышался
    duplicate_window_seconds: int = 8    # защита от случайного повтора
    log_level: str = "INFO"
    font_path: str | None = None
    font_bold_path: str | None = None

    @property
    def tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.tz_name)
        except (ZoneInfoNotFoundError, ValueError):
            return ZoneInfo("UTC")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "counter.db"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    def ensure_dirs(self) -> None:
        for directory in (self.data_dir, self.reports_dir):
            directory.mkdir(parents=True, exist_ok=True)


def load_config(require_token: bool = True) -> Config:
    _load_dotenv(ROOT / ".env")

    token = os.getenv("COUNTER_BOT_TOKEN", "").strip() or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if require_token and not token:
        raise RuntimeError(
            "Не задан токен бота.\n"
            "Возьми его у @BotFather (команда /newbot) и положи в файл .env строкой:\n"
            "COUNTER_BOT_TOKEN=123456:AA..."
        )

    data_dir = Path(os.getenv("COUNTER_DATA_DIR", "data"))
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir

    model_path = Path(os.getenv("VOSK_MODEL_PATH", "models/vosk-ru"))
    if not model_path.is_absolute():
        model_path = ROOT / model_path

    def _int(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, "").strip() or default)
        except ValueError:
            return default

    return Config(
        telegram_token=token,
        allowed_user_ids=_parse_ids(os.getenv("COUNTER_ALLOWED_USER_IDS", "")),
        data_dir=data_dir,
        model_path=model_path,
        tz_name=os.getenv("TZ", "Asia/Tashkent").strip() or "Asia/Tashkent",
        unit_name=os.getenv("COUNTER_UNIT", "шт").strip() or "шт",
        max_voice_seconds=_int("COUNTER_MAX_VOICE_SECONDS", 60),
        max_amount=_int("COUNTER_MAX_AMOUNT", 1_000_000),
        duplicate_window_seconds=_int("COUNTER_DUPLICATE_WINDOW", 8),
        log_level=(os.getenv("LOG_LEVEL", "INFO").strip() or "INFO").upper(),
        font_path=os.getenv("FONT_PATH") or _first_existing(FONT_CANDIDATES),
        font_bold_path=os.getenv("FONT_BOLD_PATH") or _first_existing(FONT_BOLD_CANDIDATES),
    )
