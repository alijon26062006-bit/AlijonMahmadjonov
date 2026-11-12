"""Проверка имён серверов, доменов и DNS-записей."""
from __future__ import annotations

import ipaddress
import re

LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
TLD = r"(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})"
DOMAIN_RE = re.compile(rf"^(?:{LABEL}\.)+{TLD}$")
HOST_RE = re.compile(rf"^(?:{LABEL}\.)+{TLD}\.?$")
RECORD_NAME_RE = re.compile(r"^(?:\*\.)?[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?(?:\.[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?)*$")
SERVER_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

RECORD_TYPES = ("A", "AAAA", "CNAME", "MX", "TXT", "NS", "SRV", "CAA")
TTL_CHOICES = (60, 300, 1800, 3600, 21600, 86400)


class ValidationError(ValueError):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def normalize_domain(raw: str) -> str:
    d = raw.strip().lower().rstrip(".")
    d = re.sub(r"^https?://", "", d).split("/")[0]
    if d.startswith("www."):
        d = d[4:]
    try:
        d = d.encode("idna").decode("ascii")
    except UnicodeError as e:
        raise ValidationError("domain", "Некорректное имя домена") from e
    if len(d) > 253 or not DOMAIN_RE.match(d):
        raise ValidationError("domain", "Некорректное имя домена, пример: example.com")
    return d


def validate_server_name(name: str) -> str:
    n = name.strip().lower()
    if not SERVER_NAME_RE.match(n):
        raise ValidationError("name", "Имя сервера: латиница, цифры и дефис, до 63 символов, например web-01")
    return n


def _host(v: str) -> bool:
    return len(v) <= 253 and bool(HOST_RE.match(v.lower()))


def validate_record(rtype: str, name: str, value: str, ttl: int) -> tuple[str, str, str, int]:
    """Возвращает нормализованные (type, name, value, ttl) или бросает ValidationError."""
    t = rtype.strip().upper()
    if t not in RECORD_TYPES:
        raise ValidationError("type", f"Тип записи: {', '.join(RECORD_TYPES)}")
    n = (name.strip().lower() or "@").rstrip(".")
    if n != "@" and (len(n) > 253 or not RECORD_NAME_RE.match(n)):
        raise ValidationError("name", "Имя: @, www, mail или поддомен")
    v = value.strip()
    if ttl not in TTL_CHOICES:
        raise ValidationError("ttl", "Недопустимый TTL")

    if t == "A":
        try:
            if not isinstance(ipaddress.ip_address(v), ipaddress.IPv4Address):
                raise ValueError
        except ValueError:
            raise ValidationError("value", "Для A нужен IPv4, например 203.0.113.24") from None
    elif t == "AAAA":
        try:
            if not isinstance(ipaddress.ip_address(v), ipaddress.IPv6Address):
                raise ValueError
            v = str(ipaddress.ip_address(v))
        except ValueError:
            raise ValidationError("value", "Для AAAA нужен IPv6, например 2001:db8::1") from None
    elif t in ("CNAME", "NS"):
        v = v.lower().rstrip(".")
        if not _host(v):
            raise ValidationError("value", f"Для {t} нужно имя хоста, например example.com")
        if t == "CNAME" and n == "@":
            raise ValidationError("name", "CNAME нельзя ставить на корень домена (@)")
    elif t == "MX":
        parts = v.split()
        if len(parts) != 2 or not parts[0].isdigit() or int(parts[0]) > 65535 or not _host(parts[1].rstrip(".")):
            raise ValidationError("value", "Формат MX: приоритет и хост, например 10 mail.example.com")
        v = f"{int(parts[0])} {parts[1].lower().rstrip('.')}"
    elif t == "TXT":
        if v.startswith('"') and v.endswith('"') and len(v) >= 2:
            v = v[1:-1]
        if not v or len(v) > 2048:
            raise ValidationError("value", "TXT: от 1 до 2048 символов")
        if '"' in v or "\n" in v:
            raise ValidationError("value", "TXT не должен содержать кавычки и переносы строк")
    elif t == "SRV":
        parts = v.split()
        if len(parts) != 4 or not all(p.isdigit() for p in parts[:3]) or not _host(parts[3].rstrip(".")):
            raise ValidationError("value", "Формат SRV: приоритет вес порт хост, например 10 5 5060 sip.example.com")
        v = " ".join(parts[:3] + [parts[3].lower().rstrip(".")])
    elif t == "CAA":
        m = re.match(r'^(\d{1,3})\s+(issue|issuewild|iodef)\s+"?([^"\s]+)"?$', v)
        if not m or int(m.group(1)) > 255:
            raise ValidationError("value", 'Формат CAA: 0 issue "letsencrypt.org"')
        v = f'{m.group(1)} {m.group(2)} "{m.group(3)}"'
    return t, n, v, ttl
