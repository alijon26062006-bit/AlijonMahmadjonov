"""Hetzner Cloud API: серверы, метрики и DNS-зоны одним токеном.

Документация: https://docs.hetzner.cloud
Авторизация: заголовок «Authorization: Bearer <HETZNER_TOKEN>».
Лимит Hetzner — 3600 запросов в час на проект, поэтому метрики и статусы кэшируются в services.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from .base import CreatedServer, Metrics, ProviderError, ServerState

# Статусы Hetzner → статусы панели
_STATUS = {
    "running": "running",
    "initializing": "creating",
    "starting": "starting",
    "stopping": "stopping",
    "off": "off",
    "deleting": "deleting",
    "migrating": "running",
    "rebuilding": "rebuilding",
    "unknown": "unknown",
}

# Действия панели → действия Hetzner
_POWER = {"start": "poweron", "stop": "shutdown", "force_stop": "poweroff", "reboot": "reboot", "reset": "reset"}

# Имена рядов Hetzner → имена рядов панели
_SERIES = {
    "cpu": "cpu",
    "disk.0.iops.read": "disk_iops_read",
    "disk.0.iops.write": "disk_iops_write",
    "disk.0.bandwidth.read": "disk_bps_read",
    "disk.0.bandwidth.write": "disk_bps_write",
    "network.0.bandwidth.in": "net_bps_in",
    "network.0.bandwidth.out": "net_bps_out",
    "network.0.pps.in": "net_pps_in",
    "network.0.pps.out": "net_pps_out",
}

_ERRORS_RU = {
    "unauthorized": "Hetzner отклонил токен: проверьте HETZNER_TOKEN",
    "forbidden": "У токена Hetzner нет прав на запись (нужен Read & Write)",
    "rate_limit_exceeded": "Превышен лимит запросов к Hetzner, попробуйте через минуту",
    "resource_limit_exceeded": "Достигнут лимит ресурсов в проекте Hetzner",
    "resource_unavailable": "Этот тариф сейчас недоступен в выбранной локации Hetzner",
    "placement_error": "Hetzner не смог разместить сервер в этой локации, выберите другую",
    "server_not_stopped_after_poweroff": "Сервер не выключился",
    "locked": "Сервер занят другой операцией, повторите через несколько секунд",
    "not_found": "Ресурс не найден у Hetzner",
    "uniqueness_error": "Такое имя уже занято в проекте Hetzner",
    "invalid_input": "Hetzner не принял параметры запроса",
    "conflict": "Ресурс изменился, повторите попытку",
    "protected": "Ресурс защищён от изменений в Hetzner (снимите защиту в консоли)",
    "maintenance": "У Hetzner идут технические работы, повторите позже",
    "unavailable": "Сервис Hetzner временно недоступен, повторите позже",
    "timeout": "Hetzner не успел ответить, повторите попытку",
    "server_error": "Ошибка на стороне Hetzner, повторите позже",
    "service_error": "Ошибка на стороне Hetzner, повторите позже",
    "bad_gateway": "Ошибка на стороне Hetzner, повторите позже",
    "incorrect_zone_mode": "Эта DNS-зона у Hetzner не в режиме primary",
}


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class HetznerClient:
    def __init__(self, token: str, base_url: str = "https://api.hetzner.cloud/v1",
                 transport: httpx.BaseTransport | None = None, timeout: float = 20.0):
        if not token:
            raise ProviderError("HETZNER_TOKEN не задан", code="config", status=500)
        self.http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}", "User-Agent": "hosting-panel/1.0"},
            timeout=timeout,
            transport=transport,
        )

    def request(self, method: str, path: str, **kw) -> dict:
        try:
            r = self.http.request(method, path, **kw)
        except httpx.HTTPError as e:
            raise ProviderError(f"Нет связи с Hetzner: {e.__class__.__name__}", code="network") from e
        if r.status_code == 204 or not r.content:
            if r.is_success:
                return {}
        try:
            data = r.json()
        except ValueError:
            data = {}
        if not r.is_success:
            err = data.get("error") or {}
            code = err.get("code") or f"http_{r.status_code}"
            message = _ERRORS_RU.get(code) or err.get("message") or f"Ошибка Hetzner {r.status_code}"
            status = 404 if r.status_code == 404 else 429 if r.status_code == 429 else 502
            raise ProviderError(message, code=code, status=status)
        return data


class HetznerVps:
    name = "hetzner"

    def __init__(self, client: HetznerClient):
        self.c = client

    def create_server(self, *, name, server_type, image, location, user_data, labels) -> CreatedServer:
        body = {
            "name": name,
            "server_type": server_type,
            "image": image,
            "location": location,
            "start_after_create": True,
            "user_data": user_data,
            "labels": labels,
            "public_net": {"enable_ipv4": True, "enable_ipv6": True},
        }
        data = self.c.request("POST", "/servers", json=body)
        srv = data.get("server") or {}
        net = srv.get("public_net") or {}
        return CreatedServer(
            provider_id=str(srv.get("id", "")),
            status=_STATUS.get(srv.get("status", ""), "creating"),
            ipv4=((net.get("ipv4") or {}).get("ip") or ""),
            ipv6=((net.get("ipv6") or {}).get("ip") or ""),
            root_password=data.get("root_password"),
        )

    def get_server(self, provider_id: str) -> ServerState:
        srv = self.c.request("GET", f"/servers/{provider_id}").get("server") or {}
        net = srv.get("public_net") or {}
        ipv6 = ((net.get("ipv6") or {}).get("ip") or "")
        # Hetzner отдаёт сеть /64 — показываем первый адрес из неё, как в консоли.
        if ipv6.endswith("/64"):
            ipv6 = ipv6[:-3] + "1"
        return ServerState(
            status=_STATUS.get(srv.get("status", ""), "unknown"),
            ipv4=((net.get("ipv4") or {}).get("ip") or ""),
            ipv6=ipv6,
        )

    def power(self, provider_id: str, action: str) -> None:
        if action not in _POWER:
            raise ProviderError("Неизвестное действие", code="invalid_input", status=400)
        self.c.request("POST", f"/servers/{provider_id}/actions/{_POWER[action]}")

    def reset_password(self, provider_id: str) -> str:
        # Работает через qemu-guest-agent, который есть в образах Hetzner. Сервер должен быть включён.
        data = self.c.request("POST", f"/servers/{provider_id}/actions/reset_password")
        pw = data.get("root_password")
        if not pw:
            raise ProviderError("Hetzner не вернул новый пароль", code="no_password")
        return pw

    def rebuild(self, provider_id: str, image: str, user_data: str | None = None) -> str | None:
        # По документации rebuild принимает user_data — так агент графиков ставится заново.
        body = {"image": image}
        if user_data:
            body["user_data"] = user_data
        data = self.c.request("POST", f"/servers/{provider_id}/actions/rebuild", json=body)
        return data.get("root_password")

    def delete_server(self, provider_id: str) -> None:
        try:
            self.c.request("DELETE", f"/servers/{provider_id}")
        except ProviderError as e:
            if e.code != "not_found":
                raise

    def metrics(self, provider_id: str, start: int, end: int, step: int) -> Metrics:
        data = self.c.request("GET", f"/servers/{provider_id}/metrics", params={
            "type": "cpu,disk,network", "start": _iso(start), "end": _iso(end), "step": step,
        })
        m = data.get("metrics") or {}
        out: dict[str, list[list[float]]] = {}
        for key, ts in (m.get("time_series") or {}).items():
            name = _SERIES.get(key)
            if not name:
                continue
            out[name] = [[float(t), float(v)] for t, v in (ts.get("values") or []) if v not in (None, "NaN")]
        return Metrics(step=int(m.get("step") or step), series=out)

    # Для админки: что реально доступно в проекте и почём.
    def server_types(self) -> list[dict]:
        return self.c.request("GET", "/server_types", params={"per_page": 50}).get("server_types", [])

    def pricing(self) -> dict:
        return self.c.request("GET", "/pricing").get("pricing", {})


class HetznerDns:
    """DNS-зоны Hetzner Cloud (/zones, /zones/{zone}/rrsets). Старый dns.hetzner.com закрыт в мае 2026."""

    name = "hetzner"

    def __init__(self, client: HetznerClient):
        self.c = client

    def ensure_zone(self, domain: str) -> None:
        try:
            self.c.request("GET", f"/zones/{domain}")
        except ProviderError as e:
            if e.code != "not_found":
                raise
            self.c.request("POST", "/zones", json={"name": domain, "mode": "primary", "ttl": 3600})

    @staticmethod
    def _value(rtype: str, value: str) -> str:
        if rtype == "TXT":
            # Строки длиннее 255 символов режутся на части в кавычках, как требует DNS.
            chunks = [value[i:i + 255] for i in range(0, len(value), 255)] or [""]
            return " ".join(f'"{c}"' for c in chunks)
        if rtype in ("CNAME", "NS", "MX", "SRV"):
            return value if value.endswith(".") else value + "."
        return value

    def set_rrset(self, domain: str, name: str, rtype: str, ttl: int, values: list[str]) -> None:
        path = f"/zones/{domain}/rrsets/{name}/{rtype}"
        if not values:
            try:
                self.c.request("DELETE", path)
            except ProviderError as e:
                if e.code != "not_found":
                    raise
            return
        records = [{"value": self._value(rtype, v)} for v in values]
        try:
            self.c.request("GET", path)
            exists = True
        except ProviderError as e:
            if e.code != "not_found":
                raise
            exists = False
        if exists:
            self.c.request("POST", f"{path}/actions/set_records", json={"records": records})
            self.c.request("POST", f"{path}/actions/change_ttl", json={"ttl": ttl})
        else:
            self.c.request("POST", f"/zones/{domain}/rrsets",
                           json={"name": name, "type": rtype, "ttl": ttl, "records": records})

    def delete_zone(self, domain: str) -> None:
        try:
            self.c.request("DELETE", f"/zones/{domain}")
        except ProviderError as e:
            if e.code != "not_found":
                raise
