"""Демо-провайдеры: всё работает без ключей, данные правдоподобные, но выдуманные."""
from __future__ import annotations

import hashlib
import math
import random
import secrets
import socket
import threading
import time

from .base import CreatedServer, Metrics, ProviderError, ServerState

YEAR = 365 * 24 * 3600


def _seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


class DemoVps:
    name = "demo"
    BOOT_SECONDS = 20

    def __init__(self):
        self._lock = threading.Lock()
        self._servers: dict[str, dict] = {}
        self._next = 1000

    def _get(self, pid: str) -> dict:
        s = self._servers.get(pid)
        if s is None:
            # После перезапуска панели демо-состояние теряется — восстанавливаем «работающий» сервер.
            s = {"status": "running", "since": 0, "ipv4": self._ip(pid), "ipv6": f"2001:db8:{int(pid) % 9999:x}::1",
                 "target": "running"}
            self._servers[pid] = s
        if s["status"] != s["target"] and time.time() - s["since"] >= s.get("delay", 3):
            s["status"] = s["target"]
        return s

    @staticmethod
    def _ip(pid: str) -> str:
        n = _seed("ip", pid)
        return f"203.0.113.{n % 250 + 2}"

    def create_server(self, *, name, server_type, image, location, user_data, labels) -> CreatedServer:
        with self._lock:
            self._next += 1
            pid = str(self._next)
            self._servers[pid] = {"status": "creating", "target": "running", "since": time.time(),
                                  "delay": self.BOOT_SECONDS, "ipv4": self._ip(pid),
                                  "ipv6": f"2001:db8:{int(pid) % 9999:x}::1"}
        return CreatedServer(pid, "creating", self._servers[pid]["ipv4"], self._servers[pid]["ipv6"],
                             root_password=secrets.token_urlsafe(14))

    def get_server(self, provider_id: str) -> ServerState:
        with self._lock:
            s = self._get(provider_id)
            return ServerState(s["status"], s["ipv4"], s["ipv6"])

    def power(self, provider_id: str, action: str) -> None:
        with self._lock:
            s = self._get(provider_id)
            if s["status"] in ("creating", "rebuilding"):
                raise ProviderError("Сервер занят другой операцией, повторите через несколько секунд", code="locked", status=409)
            plan = {"start": ("starting", "running", 4), "stop": ("stopping", "off", 3), "force_stop": ("off", "off", 0),
                    "reboot": ("rebooting", "running", 6), "reset": ("rebooting", "running", 4)}
            if action not in plan:
                raise ProviderError("Неизвестное действие", code="invalid_input", status=400)
            now_status, target, delay = plan[action]
            s.update(status=now_status, target=target, since=time.time(), delay=delay)

    def reset_password(self, provider_id: str) -> str:
        with self._lock:
            if self._get(provider_id)["status"] != "running":
                raise ProviderError("Сервер должен быть включён", code="server_not_running", status=409)
        return secrets.token_urlsafe(14)

    def rebuild(self, provider_id: str, image: str) -> str | None:
        with self._lock:
            s = self._get(provider_id)
            s.update(status="rebuilding", target="running", since=time.time(), delay=15)
        return secrets.token_urlsafe(14)

    def delete_server(self, provider_id: str) -> None:
        with self._lock:
            self._servers.pop(provider_id, None)

    def metrics(self, provider_id: str, start: int, end: int, step: int) -> Metrics:
        with self._lock:
            running = self._get(provider_id)["status"] == "running"
        base = _seed("cpu", provider_id) % 40 + 10
        out: dict[str, list[list[float]]] = {k: [] for k in ("cpu", "disk_iops_read", "disk_iops_write",
                                                               "disk_bps_read", "disk_bps_write", "net_bps_in", "net_bps_out")}
        t = start - start % step
        while t <= end:
            r = random.Random(_seed(provider_id, t))
            day = math.sin((t % 86400) / 86400 * 2 * math.pi - 1.4)  # суточный ритм
            on = running or t < end - 120
            cpu = max(1.0, base + day * 12 + r.gauss(0, 5) + (30 if r.random() > 0.97 else 0)) if on else 0.0
            net = max(0.0, (2.5e5 + day * 1.5e5 + r.gauss(0, 6e4))) if on else 0.0
            out["cpu"].append([t, round(min(cpu, 100.0), 2)])
            out["net_bps_in"].append([t, round(net, 1)])
            out["net_bps_out"].append([t, round(net * (2.2 + r.random()), 1)])
            iops = max(0.0, 40 + day * 20 + r.gauss(0, 12)) if on else 0.0
            out["disk_iops_read"].append([t, round(iops * 0.4, 1)])
            out["disk_iops_write"].append([t, round(iops * 0.6, 1)])
            out["disk_bps_read"].append([t, round(iops * 0.4 * 16384, 1)])
            out["disk_bps_write"].append([t, round(iops * 0.6 * 32768, 1)])
            t += step
        return Metrics(step=step, series=out)


class DemoDns:
    name = "demo"

    def __init__(self):
        self.zones: dict[str, dict[tuple[str, str], dict]] = {}

    def ensure_zone(self, domain: str) -> None:
        self.zones.setdefault(domain, {})

    def set_rrset(self, domain: str, name: str, rtype: str, ttl: int, values: list[str]) -> None:
        zone = self.zones.setdefault(domain, {})
        if values:
            zone[(name, rtype)] = {"ttl": ttl, "values": list(values)}
        else:
            zone.pop((name, rtype), None)

    def delete_zone(self, domain: str) -> None:
        self.zones.pop(domain, None)


class DemoRegistrar:
    """Проверка занятости через DNS: если у домена есть NS-сервер или адрес — считаем занятым."""

    name = "demo"

    def __init__(self, resolve: bool = True):
        self.resolve = resolve

    def check(self, domain: str) -> bool:
        if self.resolve:
            try:
                socket.setdefaulttimeout(2)
                socket.getaddrinfo(domain, None)
                return False
            except (socket.gaierror, UnicodeError, OSError):
                pass
        # Без ответа DNS решаем детерминированно, чтобы результат не «прыгал».
        return _seed("free", domain) % 4 != 0

    def register(self, domain: str, years: int) -> int:
        return int(time.time()) + years * YEAR

    def renew(self, domain: str, years: int, current_expiry: int) -> int:
        return max(current_expiry, int(time.time())) + years * YEAR
