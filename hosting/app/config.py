"""Настройки из переменных окружения (и файла .env рядом с проектом)."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    """Минимальный загрузчик .env, чтобы не тянуть лишнюю зависимость."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def _bool(raw: str | None, default: bool) -> bool:
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    brand_name: str = "AM Cloud"
    secret_key: str = field(default_factory=lambda: secrets.token_urlsafe(48))
    database_path: str = str(BASE_DIR / "data" / "hosting.db")
    currency: str = "USD"
    admin_email: str = ""
    cookie_secure: bool = False
    # Публичный адрес панели: агент на серверах клиентов шлёт сюда память и процессы.
    public_url: str = "http://127.0.0.1:8000"
    # Пополнение баланса кнопкой без оплаты — только для показа и разработки.
    demo_payments: bool = True
    # Через сколько дней после окончания оплаты сервер выключается.
    grace_days: int = 3
    billing_interval_sec: int = 600

    # Серверы и DNS: "demo" — симуляция, "hetzner" — Hetzner Cloud API.
    vps_provider: str = "demo"
    dns_provider: str = "demo"
    hetzner_token: str = ""
    hetzner_api_url: str = "https://api.hetzner.cloud/v1"
    nameservers: list[str] = field(default_factory=lambda: [
        "hydrogen.ns.hetzner.com", "oxygen.ns.hetzner.com", "helium.ns.hetzner.de",
    ])

    # Регистратор доменов: пока только "demo" (подключается реселлерский договор).
    registrar: str = "demo"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BASE_DIR / ".env")
        env = os.environ.get
        db_path = env("DATABASE_PATH") or "data/hosting.db"
        if not os.path.isabs(db_path):
            db_path = str(BASE_DIR / db_path)
        s = cls(
            brand_name=env("BRAND_NAME") or "AM Cloud",
            database_path=db_path,
            currency=env("CURRENCY") or "USD",
            admin_email=(env("ADMIN_EMAIL") or "").strip().lower(),
            cookie_secure=_bool(env("COOKIE_SECURE"), False),
            public_url=(env("PUBLIC_URL") or "http://127.0.0.1:8000").rstrip("/"),
            demo_payments=_bool(env("DEMO_PAYMENTS"), True),
            grace_days=int(env("GRACE_DAYS") or 3),
            vps_provider=(env("VPS_PROVIDER") or "demo").lower(),
            dns_provider=(env("DNS_PROVIDER") or "demo").lower(),
            hetzner_token=env("HETZNER_TOKEN") or "",
            hetzner_api_url=(env("HETZNER_API_URL") or "https://api.hetzner.cloud/v1").rstrip("/"),
            registrar=(env("REGISTRAR") or "demo").lower(),
        )
        if env("SECRET_KEY"):
            s.secret_key = env("SECRET_KEY")  # type: ignore[assignment]
        if env("NAMESERVERS"):
            s.nameservers = [n.strip().rstrip(".").lower() for n in env("NAMESERVERS").split(",") if n.strip()]  # type: ignore[union-attr]
        return s

    def validate(self) -> list[str]:
        """Проблемы конфигурации, о которых стоит предупредить при запуске."""
        problems = []
        uses_hetzner = "hetzner" in (self.vps_provider, self.dns_provider)
        if uses_hetzner and not self.hetzner_token:
            problems.append("VPS_PROVIDER/DNS_PROVIDER=hetzner, но HETZNER_TOKEN пуст")
        if self.vps_provider not in ("demo", "hetzner"):
            problems.append(f"Неизвестный VPS_PROVIDER={self.vps_provider}")
        if self.dns_provider not in ("demo", "hetzner"):
            problems.append(f"Неизвестный DNS_PROVIDER={self.dns_provider}")
        return problems
