"""Доставка звёзд и Premium через Fragment.

Провайдер выбирается переменной FRAGMENT_MODE в .env:

* ``mock`` — ничего не отправляет, только пишет в лог. Для разработки и тестов.
* ``api``  — реальные запросы к Fragment.

ВАЖНО: конкретные пути эндпоинтов Fragment вынесены в константы ниже. Перед
боевым запуском сверь их со своей документацией/личным кабинетом Fragment
и поправь при необходимости — трогать остальной код не придётся.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import aiohttp

from app.config import settings

log = logging.getLogger(__name__)

AUTH_PATH = "/v1/auth/authenticate/"
STARS_PATH = "/v1/order/stars/"
PREMIUM_PATH = "/v1/order/premium/"
WALLET_PATH = "/v1/misc/wallet/"
USER_PATH = "/v1/misc/user/{username}/"

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=60)


class DeliveryError(Exception):
    """Fragment явно отказал: не хватило баланса, нет получателя, плохой запрос.

    Точно известно, что выдачи НЕ было, поэтому деньги можно вернуть сразу.
    """


class DeliveryUncertain(Exception):
    """Ответа нет: таймаут, обрыв сети, 5xx.

    Неизвестно, прошла выдача или нет. Автовозврат тут опасен — можно вернуть
    деньги за реально отправленные звёзды, — поэтому такой заказ уходит
    админу на ручную проверку.
    """


@dataclass
class DeliveryResult:
    order_id: str | None
    raw: dict


@dataclass
class Recipient:
    """Получатель, каким его видит Fragment.

    name показывается покупателю на подтверждении: без него человек
    отправляет звёзды вслепую и опечатка в юзернейме стоит ему денег.
    """
    username: str
    name: str = ""

    @property
    def display(self) -> str:
        return self.name or f"@{self.username}"


class DeliveryProvider:
    async def deliver_stars(self, username: str, amount: int) -> DeliveryResult:
        raise NotImplementedError

    async def deliver_premium(self, username: str, months: int) -> DeliveryResult:
        raise NotImplementedError

    async def get_balance(self) -> str:
        raise NotImplementedError

    async def resolve_recipient(self, username: str) -> Recipient | None:
        """Найти получателя. None — Fragment такого не знает."""
        raise NotImplementedError

    async def healthcheck(self) -> dict:
        """Проверка связи для админ-панели: {ok, steps, error}."""
        raise NotImplementedError

    async def close(self) -> None:
        return None


class MockProvider(DeliveryProvider):
    """Заглушка: имитирует успешную выдачу, ничего не отправляя."""

    def __init__(self) -> None:
        self._counter = 0

    async def deliver_stars(self, username: str, amount: int) -> DeliveryResult:
        await asyncio.sleep(0.5)
        self._counter += 1
        log.warning("MOCK: выдано %s звёзд пользователю @%s", amount, username)
        return DeliveryResult(order_id=f"mock-{self._counter}", raw={"mock": True})

    async def deliver_premium(self, username: str, months: int) -> DeliveryResult:
        await asyncio.sleep(0.5)
        self._counter += 1
        log.warning("MOCK: выдан Premium на %s мес. пользователю @%s", months, username)
        return DeliveryResult(order_id=f"mock-{self._counter}", raw={"mock": True})

    async def get_balance(self) -> str:
        return "MOCK — реальный баланс недоступен"

    async def resolve_recipient(self, username: str) -> Recipient | None:
        # В mock-режиме «находим» кого угодно, кроме заведомо несуществующего
        # имени — так тестируется и ветка с ошибкой.
        if username.lower() in ("notfound", "unknown"):
            return None
        return Recipient(username=username, name=f"{username.capitalize()} (MOCK)")

    async def healthcheck(self) -> dict:
        return {
            "ok": True,
            "mode": "mock",
            "steps": [("Режим", "MOCK — реальной выдачи нет")],
            "error": "",
        }


class FragmentProvider(DeliveryProvider):
    """Клиент Fragment с JWT-авторизацией и авто-переполучением токена."""

    def __init__(self) -> None:
        missing = [
            name
            for name, value in (
                ("FRAGMENT_API_KEY", settings.fragment_api_key),
                ("FRAGMENT_PHONE_NUMBER", settings.fragment_phone_number),
                ("FRAGMENT_MNEMONICS", settings.fragment_mnemonics),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "FRAGMENT_MODE=api, но не заполнены: " + ", ".join(missing)
            )
        self._base = settings.fragment_base_url.rstrip("/")
        self._token: str | None = None
        self._lock = asyncio.Lock()
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=REQUEST_TIMEOUT)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _authenticate(self) -> str:
        session = await self._get_session()
        payload = {
            "api_key": settings.fragment_api_key,
            "phone_number": settings.fragment_phone_number,
            "mnemonics": settings.mnemonics_list,
        }
        try:
            async with session.post(self._base + AUTH_PATH, json=payload) as resp:
                data = await self._read_json(resp)
                if resp.status >= 400:
                    raise DeliveryError(
                        f"Авторизация Fragment не прошла ({resp.status}): {data}"
                    )
        except (TimeoutError, aiohttp.ClientError) as exc:
            # Авторизация идёт до выдачи, поэтому её провал безопасен:
            # заказ точно не отправлен и деньги можно вернуть.
            raise DeliveryError(f"Fragment недоступен: {exc}") from exc
        token = data.get("token") or data.get("access_token")
        if not token:
            raise DeliveryError(f"Fragment не вернул токен: {data}")
        log.info("Fragment: получен новый токен")
        return token

    async def _token_value(self, *, force: bool = False) -> str:
        async with self._lock:
            if force or not self._token:
                self._token = await self._authenticate()
            return self._token

    @staticmethod
    async def _read_json(resp: aiohttp.ClientResponse) -> dict:
        try:
            data = await resp.json(content_type=None)
        except Exception:  # noqa: BLE001 — Fragment иногда отдаёт HTML при ошибке
            data = {}
        if not isinstance(data, dict):
            data = {"response": data}
        if not data:
            text = (await resp.text())[:300]
            data = {"raw": text}
        return data

    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        session = await self._get_session()
        url = self._base + path
        for attempt in (1, 2):
            token = await self._token_value(force=attempt == 2)
            headers = {"Authorization": f"JWT {token}"}
            try:
                async with session.request(
                    method, url, json=payload, headers=headers
                ) as resp:
                    data = await self._read_json(resp)
                    if resp.status == 401 and attempt == 1:
                        log.info("Fragment: токен протух, повторяю авторизацию")
                        continue
                    if resp.status >= 500:
                        raise DeliveryUncertain(
                            f"Fragment вернул {resp.status}: {data.get('error') or data}"
                        )
                    if resp.status >= 400:
                        raise DeliveryError(
                            f"Fragment вернул {resp.status}: {data.get('error') or data}"
                        )
                    return data
            except (TimeoutError, aiohttp.ClientError) as exc:
                # Запрос мог дойти до Fragment и выполниться — считать его
                # неудачей и возвращать деньги нельзя.
                raise DeliveryUncertain(f"Нет ответа от Fragment: {exc}") from exc
        raise DeliveryError("Fragment: не удалось авторизоваться")

    async def deliver_stars(self, username: str, amount: int) -> DeliveryResult:
        data = await self._request(
            "POST", STARS_PATH,
            {"username": username, "quantity": amount, "show_sender": False},
        )
        return DeliveryResult(order_id=str(data.get("id") or data.get("order_id") or ""), raw=data)

    async def deliver_premium(self, username: str, months: int) -> DeliveryResult:
        data = await self._request(
            "POST", PREMIUM_PATH,
            {"username": username, "duration": months, "show_sender": False},
        )
        return DeliveryResult(order_id=str(data.get("id") or data.get("order_id") or ""), raw=data)

    async def get_balance(self) -> str:
        data = await self._request("GET", WALLET_PATH)
        balance = data.get("balance") or data.get("available") or data
        return str(balance)

    async def resolve_recipient(self, username: str) -> Recipient | None:
        try:
            data = await self._request("GET", USER_PATH.format(username=username))
        except DeliveryError as exc:
            log.info("Fragment: получатель @%s не найден (%s)", username, exc)
            return None
        except DeliveryUncertain as exc:
            # Проверка получателя ничего не меняет, поэтому недоступность
            # Fragment здесь безопасно трактовать как «не подтвердили».
            log.warning("Fragment недоступен при проверке @%s: %s", username, exc)
            return None

        # Формат ответа у разных версий API отличается — берём первое подходящее.
        name = ""
        for key in ("name", "display_name", "first_name", "title", "full_name"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                name = value.strip()
                break
        if not name and isinstance(data.get("recipient"), dict):
            name = str(data["recipient"].get("name") or "").strip()
        return Recipient(username=username, name=name)

    async def healthcheck(self) -> dict:
        """Пошагово проверяет, что выдача вообще возможна."""
        steps: list[tuple[str, str]] = []
        try:
            token = await self._token_value(force=True)
            steps.append(("Авторизация", f"✅ токен получен ({len(token)} симв.)"))
        except (DeliveryError, DeliveryUncertain) as exc:
            steps.append(("Авторизация", f"❌ {exc}"))
            return {"ok": False, "mode": "api", "steps": steps, "error": str(exc)}

        try:
            balance = await self.get_balance()
            steps.append(("Баланс кошелька", f"✅ {balance}"))
        except (DeliveryError, DeliveryUncertain) as exc:
            steps.append(("Баланс кошелька", f"⚠️ не прочитался: {exc}"))

        return {"ok": True, "mode": "api", "steps": steps, "error": ""}


def build_provider() -> DeliveryProvider:
    mode = settings.fragment_mode.strip().lower()
    if mode == "api":
        return FragmentProvider()
    if mode != "mock":
        log.warning("Неизвестный FRAGMENT_MODE=%r, использую mock", settings.fragment_mode)
    log.warning("Fragment работает в режиме MOCK — реальной выдачи не будет")
    return MockProvider()
