"""Настройки дуэли. Читаются из окружения или из .env рядом с проектом."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def _parse_ids(raw: str) -> frozenset[int]:
    ids = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part:
            try:
                ids.add(int(part))
            except ValueError as exc:
                raise ValueError(f"DUEL_ADMIN_IDS: {part!r} — это не число") from exc
    return frozenset(ids)


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "да", "on"}


@dataclass(frozen=True)
class DuelConfig:
    """Всё, что нужно серверу дуэли, чтобы подняться."""

    bot_token: str
    public_url: str
    data_dir: Path
    host: str = "127.0.0.1"
    port: int = 8081
    dev_mode: bool = False
    tick_hz: int = 20
    admin_ids: frozenset[int] = frozenset()
    log_level: str = "INFO"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "duel.sqlite3"

    @property
    def webapp_url(self) -> str:
        """Адрес Mini App — его Telegram открывает по кнопке."""
        return self.public_url.rstrip("/") + "/"

    @property
    def tick_interval(self) -> float:
        return 1.0 / max(1, self.tick_hz)

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


def load_config(env_file: str | Path | None = None) -> DuelConfig:
    """Собирает настройки. Бросает RuntimeError, если чего-то не хватает."""

    load_dotenv(env_file or ROOT / ".env")

    token = os.getenv("DUEL_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Не задан DUEL_BOT_TOKEN. Заведи отдельного бота у @BotFather "
            "(/newbot) и впиши его токен в .env"
        )

    public_url = os.getenv("DUEL_PUBLIC_URL", "").strip()
    dev_mode = _parse_bool(os.getenv("DUEL_DEV_MODE", ""))
    if not public_url:
        if not dev_mode:
            raise RuntimeError(
                "Не задан DUEL_PUBLIC_URL — адрес, по которому Telegram откроет "
                "Mini App. Нужен https (например https://duel.example.com)"
            )
        public_url = "http://127.0.0.1:8081"
    if not dev_mode and not public_url.startswith("https://"):
        raise RuntimeError(
            f"DUEL_PUBLIC_URL={public_url!r}: Telegram открывает Mini App только по https"
        )

    port_raw = os.getenv("DUEL_PORT", "8081").strip()
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ValueError(f"DUEL_PORT: {port_raw!r} — это не число") from exc

    tick_raw = os.getenv("DUEL_TICK_HZ", "20").strip()
    try:
        tick_hz = max(5, min(50, int(tick_raw)))
    except ValueError as exc:
        raise ValueError(f"DUEL_TICK_HZ: {tick_raw!r} — это не число") from exc

    data_dir = Path(os.getenv("DUEL_DATA_DIR", os.getenv("DATA_DIR", "data"))).expanduser()
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir

    return DuelConfig(
        bot_token=token,
        public_url=public_url,
        data_dir=data_dir,
        host=os.getenv("DUEL_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=port,
        dev_mode=dev_mode,
        tick_hz=tick_hz,
        admin_ids=_parse_ids(os.getenv("DUEL_ADMIN_IDS", "")),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )
