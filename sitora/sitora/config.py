"""Настройки из .env. Секреты (токен бота, ключи) — только из окружения, в код не попадают."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass
class Config:
    name: str = "Sitora"
    bot_token: str = ""
    admin_ids: list[int] = field(default_factory=list)
    base_url: str = "http://localhost:8020"
    db_path: str = str(ROOT / "data" / "sitora.db")
    fazer_key: str = ""
    fazer_url: str = "https://reseller.fazercards.com/api/v2"
    openai_key: str = ""
    receipt_model: str = "gpt-4o-mini"
    support: str = ""
    receipts_dir: str = str(ROOT / "data" / "receipts")

    @classmethod
    def load(cls) -> "Config":
        _load_env(ROOT / ".env")
        e = os.environ.get
        db = e("SITORA_DB", "data/sitora.db")
        db = db if os.path.isabs(db) else str(ROOT / db)
        return cls(
            name=e("SITORA_NAME", "Sitora") or "Sitora",
            bot_token=e("SITORA_BOT_TOKEN", ""),
            admin_ids=[int(x) for x in e("SITORA_ADMIN_IDS", "").replace(" ", "").split(",") if x.strip().lstrip("-").isdigit()],
            base_url=e("SITORA_BASE_URL", "http://localhost:8020").rstrip("/"),
            db_path=db,
            fazer_key=e("SITORA_FAZER_KEY", ""),
            fazer_url=e("SITORA_FAZER_URL", "https://reseller.fazercards.com/api/v2").rstrip("/"),
            openai_key=e("SITORA_OPENAI_KEY", ""),
            receipt_model=e("SITORA_RECEIPT_MODEL", "gpt-4o-mini"),
            support=e("SITORA_SUPPORT", ""),
            receipts_dir=str(Path(db).parent / "receipts"),
        )

    def is_admin(self, tg_id: int | None) -> bool:
        return tg_id is not None and int(tg_id) in self.admin_ids
