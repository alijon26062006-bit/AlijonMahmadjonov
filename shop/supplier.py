"""Пайвасти таъминкунанда (API).

Ҳоло ду реҷа:

*   ``manual`` — бе API. Фармоиш ба админ меравад, ӯ дастӣ иҷро мекунад.
    ID-и бозигар тафтиш намешавад — харидор худаш тасдиқ мекунад.
*   ``http``   — шаблон барои API-и воқеӣ. Вақте ҳуҷҷатҳо ва калид омаданд,
    танҳо ду метод дар ``HttpSupplier`` пур карда мешавад — боқӣ ҳама тайёр.

Ҳамаи хатоҳо дар дохил гирифта мешаванд: бот ҳеҷ гоҳ аз сабаби таъминкунанда
намеафтад.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlayerInfo:
    """Натиҷаи тафтиши ID-и бозигар."""

    player_id: str
    nickname: str | None = None
    ok: bool = True
    error: str | None = None


@dataclass(frozen=True)
class OrderResult:
    ok: bool
    external_id: str | None = None
    error: str | None = None


class Supplier(Protocol):
    name: str

    async def check_player(self, game: str, player_id: str) -> PlayerInfo: ...

    async def place_order(
        self, *, game: str, product_code: str, player_id: str, amount: int
    ) -> OrderResult: ...

    async def close(self) -> None: ...


class ManualSupplier:
    """Бе API: ҳама чиз дастӣ аз панели админ."""

    name = "manual"

    async def check_player(self, game: str, player_id: str) -> PlayerInfo:
        # Лақаб маълум нест — харидор ID-и худро худаш тасдиқ мекунад.
        return PlayerInfo(player_id=player_id, nickname=None, ok=True)

    async def place_order(
        self, *, game: str, product_code: str, player_id: str, amount: int
    ) -> OrderResult:
        return OrderResult(ok=True, external_id=None)

    async def close(self) -> None:
        return None


class HttpSupplier:
    """Шаблон барои API-и воқеӣ.

    Вақте ҳуҷҷатҳои таъминкунанда омаданд, се чизро иваз кардан кофист:
    ``_CHECK_PATH``, ``_ORDER_PATH`` ва тарзи хондани ҷавоб.
    """

    name = "http"

    _CHECK_PATH = "/check"
    _ORDER_PATH = "/order"

    def __init__(self, base_url: str, api_key: str, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._session = None

    async def _get_session(self):
        import aiohttp

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        return self._session

    async def check_player(self, game: str, player_id: str) -> PlayerInfo:
        if not self.base_url:
            return PlayerInfo(player_id=player_id, nickname=None, ok=True)
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.base_url}{self._CHECK_PATH}",
                params={"game": game, "player_id": player_id},
            ) as resp:
                data = await resp.json(content_type=None)
            if resp.status >= 400:
                return PlayerInfo(player_id, None, ok=False, error=f"HTTP {resp.status}")
            nickname = data.get("nickname") or data.get("username") or data.get("name")
            return PlayerInfo(player_id=player_id, nickname=nickname, ok=bool(nickname))
        except Exception as exc:  # хатои шабака набояд ботро афтонад
            log.warning("check_player нашуд: %s", exc)
            return PlayerInfo(player_id, None, ok=False, error=str(exc))

    async def place_order(
        self, *, game: str, product_code: str, player_id: str, amount: int
    ) -> OrderResult:
        if not self.base_url:
            return OrderResult(ok=True, external_id=None)
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}{self._ORDER_PATH}",
                json={
                    "game": game,
                    "product": product_code,
                    "player_id": player_id,
                    "amount": amount,
                },
            ) as resp:
                data = await resp.json(content_type=None)
            if resp.status >= 400:
                return OrderResult(ok=False, error=f"HTTP {resp.status}: {data}")
            return OrderResult(ok=True, external_id=str(data.get("order_id") or ""))
        except Exception as exc:
            log.warning("place_order нашуд: %s", exc)
            return OrderResult(ok=False, error=str(exc))

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()


def build_supplier(kind: str, url: str = "", key: str = "") -> Supplier:
    if kind == "http" and url:
        return HttpSupplier(url, key)
    return ManualSupplier()
