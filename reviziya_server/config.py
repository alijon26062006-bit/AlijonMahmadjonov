"""Настройки сервера ревизии. Читаются из окружения или из файла .env.reviziya."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env.reviziya"


@dataclass(frozen=True)
class Config:
    bot_token: str
    anthropic_api_key: str
    public_url: str          # https://домен — этот адрес открывает Telegram
    data_dir: Path
    web_dir: Path
    host: str = "127.0.0.1"
    port: int = 8787
    model: str = "claude-haiku-5-5"
    admin_ids: frozenset[int] = frozenset()

    @property
    def db_path(self) -> Path:
        return self.data_dir / "reviziya.db"


def _ids(raw: str) -> frozenset[int]:
    out = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part:
            out.add(int(part))
    return frozenset(out)


def load_config() -> Config:
    load_dotenv(ENV_FILE)
    missing = [k for k in ("REVIZIYA_BOT_TOKEN", "ANTHROPIC_API_KEY", "REVIZIYA_URL") if not os.getenv(k)]
    if missing:
        raise SystemExit(
            "Не хватает настроек: " + ", ".join(missing) + ". Запусти: bash setup_reviziya.sh"
        )
    return Config(
        bot_token=os.environ["REVIZIYA_BOT_TOKEN"].strip(),
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"].strip(),
        public_url=os.environ["REVIZIYA_URL"].strip().rstrip("/"),
        data_dir=Path(os.getenv("REVIZIYA_DATA_DIR", ROOT / "data")),
        web_dir=ROOT / "reviziya",
        host=os.getenv("REVIZIYA_HOST", "127.0.0.1"),
        port=int(os.getenv("REVIZIYA_PORT", "8787")),
        model=os.getenv("REVIZIYA_MODEL", "claude-haiku-5-5"),
        admin_ids=_ids(os.getenv("REVIZIYA_ADMIN_IDS", "")),
    )
