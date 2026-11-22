"""Клиент Hetzner Cloud API (https://api.hetzner.cloud/v1).

- Ошибки приходят как {"error": {"code", "message"}} — переводим на русский.
- Лимит запросов на проект в час (заголовки RateLimit-*); при превышении 429.
- Списки постранично: per_page до 50, meta.pagination.next_page.
- Токен в лог не пишем никогда.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

ERRORS_RU = {
    "forbidden": "Нет прав: токену Hetzner нужен доступ Read & Write.",
    "unauthorized": "Токен Hetzner не подошёл — проверьте его в настройках.",
    "not_found": "Не найдено у Hetzner (возможно, сервер уже удалён).",
    "invalid_input": "Hetzner не принял данные запроса.",
    "json_error": "Hetzner не понял запрос.",
    "locked": "Сервер сейчас занят другой операцией — повторите через минуту.",
    "conflict": "Ресурс изменился во время операции — повторите.",
    "rate_limit_exceeded": "Слишком много запросов к Hetzner — подождите немного.",
    "resource_limit_exceeded": "Достигнут лимит ресурсов в проекте Hetzner.",
    "resource_unavailable": "Этот тариф сейчас недоступен в выбранной локации.",
    "placement_error": "В этой локации сейчас нет свободных мощностей — выберите другую.",
    "uniqueness_error": "Сервер с таким именем уже есть.",
    "maintenance": "У Hetzner технические работы — попробуйте позже.",
    "unavailable": "Сервис Hetzner временно недоступен.",
    "timeout": "Hetzner не ответил вовремя.",
    "server_error": "Ошибка на стороне Hetzner.",
    "protected": "Ресурс защищён от удаления в Hetzner.",
    "service_error": "Ошибка сервиса Hetzner.",
}


class HetznerError(Exception):
    def __init__(self, code: str, message: str = "", status: int = 0):
        self.code, self.status, self.raw = code, status, message
        super().__init__(ERRORS_RU.get(code) or message or code)

    @property
    def text(self) -> str:
        return str(self)


class Hetzner:
    def __init__(self, token: str, base_url: str = "https://api.hetzner.cloud/v1",
                 transport: httpx.AsyncBaseTransport | None = None):
        self.token = token
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=30, transport=transport,
            headers={"Authorization": f"Bearer {token}", "User-Agent": "vps-panel/1.0"})
        self.ratelimit: dict[str, int] = {}
        self._cache: dict[str, tuple[float, Any]] = {}

    async def close(self) -> None:
        await self._client.aclose()

    async def request(self, method: str, path: str, *, params: dict | None = None,
                      json: dict | None = None) -> dict:
        if not self.token:
            raise HetznerError("unauthorized", "токен не задан", 401)
        try:
            r = await self._client.request(method, path, params=params, json=json)
        except httpx.TimeoutException:
            raise HetznerError("timeout", "timeout") from None
        except httpx.HTTPError as exc:
            raise HetznerError("unavailable", type(exc).__name__) from None
        for name in ("limit", "remaining", "reset"):
            value = r.headers.get(f"RateLimit-{name.capitalize()}")
            if value and value.isdigit():
                self.ratelimit[name] = int(value)
        if r.status_code == 204:
            return {}
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.status_code >= 400 or (isinstance(data, dict) and data.get("error")):
            err = (data or {}).get("error") or {}
            code = err.get("code") or ("rate_limit_exceeded" if r.status_code == 429 else
                                       "unauthorized" if r.status_code == 401 else
                                       "forbidden" if r.status_code == 403 else
                                       "not_found" if r.status_code == 404 else "server_error")
            log.warning("Hetzner %s %s → %s %s", method, path, r.status_code, code)
            raise HetznerError(code, err.get("message", ""), r.status_code)
        return data

    async def get(self, path: str, params: dict | None = None) -> dict:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, json: dict | None = None) -> dict:
        return await self.request("POST", path, json=json or {})

    async def delete(self, path: str) -> dict:
        return await self.request("DELETE", path)

    async def list(self, path: str, key: str, params: dict | None = None) -> list[dict]:
        """Все страницы списка: per_page=50, пока есть meta.pagination.next_page."""
        out, page = [], 1
        while page:
            data = await self.get(path, {**(params or {}), "page": page, "per_page": 50})
            out.extend(data.get(key) or [])
            page = (((data.get("meta") or {}).get("pagination") or {}).get("next_page"))
            if len(out) > 5000:
                break
        return out

    async def cached(self, key: str, ttl: float, fetch):
        hit = self._cache.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        value = await fetch()
        self._cache[key] = (time.monotonic() + ttl, value)
        return value

    def forget(self, prefix: str = "") -> None:
        for key in [k for k in self._cache if k.startswith(prefix)]:
            del self._cache[key]

    # ── права токена ──

    async def access(self) -> str:
        """'rw' | 'ro' | 'bad'. Read-only токен на POST получает 403 forbidden.

        Проверка без побочных эффектов: пустой ключ SSH Hetzner не примет
        (invalid_input), а read-only токен отбрасывается раньше — forbidden.
        """
        try:
            await self.get("/locations")
        except HetznerError as exc:
            if exc.code in ("unauthorized", "forbidden"):
                return "bad"
            raise
        try:
            await self.post("/ssh_keys", {"name": "", "public_key": ""})
        except HetznerError as exc:
            if exc.code == "forbidden":
                return "ro"
            if exc.code in ("invalid_input", "json_error", "uniqueness_error"):
                return "rw"
            raise
        return "rw"


_clients: dict[str, Hetzner] = {}


def client(token: str, base_url: str = "https://api.hetzner.cloud/v1") -> Hetzner:
    """Один клиент на токен — с общим кэшем и счётчиком лимитов."""
    key = token + "|" + base_url
    if key not in _clients:
        _clients.clear()
        _clients[key] = Hetzner(token, base_url)
    return _clients[key]
