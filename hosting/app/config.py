"""Настройки из переменных окружения (и файла .env рядом с проектом)."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
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


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _templates(raw: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for part in raw.split(","):
        if "=" in part:
            name, vmid = part.split("=", 1)
            if vmid.strip().isdigit():
                out[name.strip()] = int(vmid.strip())
    return out


@dataclass
class Settings:
    brand_name: str = "AM Cloud"
    secret_key: str = ""
    database_path: str = "data/hosting.db"
    currency: str = "$"
    admin_email: str = ""
    cookie_secure: bool = False

    vps_provider: str = "demo"
    proxmox_url: str = ""
    proxmox_node: str = "pve"
    proxmox_token: str = ""
    proxmox_templates: dict[str, int] = field(default_factory=dict)
    proxmox_verify_tls: bool = True
    proxmox_ip_pool: str = ""
    proxmox_gateway: str = ""
    proxmox_bridge: str = "vmbr0"

    dns_provider: str = "demo"
    powerdns_url: str = ""
    powerdns_api_key: str = ""
    powerdns_server_id: str = "localhost"
    nameservers: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv(BASE_DIR / ".env")
        env = os.environ.get
        secret = env("SECRET_KEY", "")
        if not secret:
            # Без ключа сессии сбросятся при перезапуске — для разработки это нормально.
            secret = secrets.token_urlsafe(48)
        db_path = env("DATABASE_PATH", "data/hosting.db")
        if not os.path.isabs(db_path):
            db_path = str(BASE_DIR / db_path)
        return cls(
            brand_name=env("BRAND_NAME", "AM Cloud") or "AM Cloud",
            secret_key=secret,
            database_path=db_path,
            currency=env("CURRENCY", "$") or "$",
            admin_email=(env("ADMIN_EMAIL", "") or "").strip().lower(),
            cookie_secure=_bool("COOKIE_SECURE", False),
            vps_provider=(env("VPS_PROVIDER", "demo") or "demo").lower(),
            proxmox_url=(env("PROXMOX_URL", "") or "").rstrip("/"),
            proxmox_node=env("PROXMOX_NODE", "pve") or "pve",
            proxmox_token=env("PROXMOX_TOKEN", "") or "",
            proxmox_templates=_templates(env("PROXMOX_TEMPLATES", "") or ""),
            proxmox_verify_tls=_bool("PROXMOX_VERIFY_TLS", True),
            proxmox_ip_pool=env("PROXMOX_IP_POOL", "") or "",
            proxmox_gateway=env("PROXMOX_GATEWAY", "") or "",
            proxmox_bridge=env("PROXMOX_BRIDGE", "vmbr0") or "vmbr0",
            dns_provider=(env("DNS_PROVIDER", "demo") or "demo").lower(),
            powerdns_url=(env("POWERDNS_URL", "") or "").rstrip("/"),
            powerdns_api_key=env("POWERDNS_API_KEY", "") or "",
            powerdns_server_id=env("POWERDNS_SERVER_ID", "localhost") or "localhost",
            nameservers=[
                ns.strip().rstrip(".").lower()
                for ns in (env("NAMESERVERS", "ns1.amcloud.example,ns2.amcloud.example") or "").split(",")
                if ns.strip()
            ],
        )
