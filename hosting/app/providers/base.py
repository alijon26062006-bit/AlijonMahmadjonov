"""Общие интерфейсы провайдеров: серверы, DNS, регистратор доменов."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

# Статусы, которые видит клиент. Провайдерские статусы сводятся к ним.
STATUSES = ("creating", "running", "starting", "stopping", "off", "rebooting", "rebuilding", "deleting", "unknown")


class ProviderError(Exception):
    def __init__(self, message: str, code: str = "provider_error", status: int = 502):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


@dataclass
class CreatedServer:
    provider_id: str
    status: str
    ipv4: str = ""
    ipv6: str = ""
    root_password: str | None = None


@dataclass
class ServerState:
    status: str
    ipv4: str = ""
    ipv6: str = ""


@dataclass
class Metrics:
    """Временные ряды: список пар [unix_ts, значение]."""
    step: int
    series: dict[str, list[list[float]]] = field(default_factory=dict)


class VpsProvider(Protocol):
    name: str

    def ensure_ssh_key(self, name: str, public_key: str) -> str: ...

    def create_server(self, *, name: str, server_type: str, image: str, location: str,
                      user_data: str, labels: dict[str, str], ssh_keys: list[str] | None = None) -> CreatedServer: ...

    def get_server(self, provider_id: str) -> ServerState: ...

    def power(self, provider_id: str, action: str) -> None: ...

    def reset_password(self, provider_id: str) -> str: ...

    def rebuild(self, provider_id: str, image: str, user_data: str | None = None) -> str | None: ...

    def delete_server(self, provider_id: str) -> None: ...

    def metrics(self, provider_id: str, start: int, end: int, step: int) -> Metrics: ...


class DnsProvider(Protocol):
    name: str

    def ensure_zone(self, domain: str) -> None: ...

    def set_rrset(self, domain: str, name: str, rtype: str, ttl: int, values: list[str]) -> None: ...

    def delete_zone(self, domain: str) -> None: ...


@dataclass
class RegisteredDomain:
    order_id: str
    expires_at: int


class Registrar(Protocol):
    name: str

    def check_many(self, label: str, zones: list[str]) -> dict[str, bool]: ...

    def check(self, domain: str) -> bool: ...

    def ensure_contact(self, user: dict) -> str: ...

    def register(self, domain: str, years: int, contact_id: str, nameservers: list[str]) -> RegisteredDomain: ...

    def renew(self, domain: str, order_id: str, years: int, current_expiry: int) -> int: ...

    def set_nameservers(self, domain: str, order_id: str, nameservers: list[str]) -> None: ...

    def ping(self) -> str: ...
