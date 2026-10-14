"""Логика бота без Telegram: регистрация, токен, себестоимость, анализы.

Обработчики Telegram (handlers.py) только передают сюда данные и показывают ответ —
поэтому всё важное проверяется обычными тестами.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wbm.bot.texts import OPTIONAL_CATEGORIES, REQUIRED_CATEGORIES
from wbm.config import WBSettings
from wbm.costs import CostFile, CostFileError, parse_cost_file
from wbm.db import repositories as repo
from wbm.db.models import AnalysisRun, RunSource, RunStatus, Shop, User
from wbm.report.pdf import build_pdf
from wbm.security.crypto import TokenCipher
from wbm.wb_client import (
    Category,
    WBClient,
    WBConfigError,
    WBError,
    WBTokenFormatError,
    normalize_token,
)
from wbm.wb_client.api.general import GeneralAPI
from wbm.wb_client.ratelimit import RateLimiterRegistry
from wbm.wb_client.token_check import CategoryStatus, check_token

logger = logging.getLogger(__name__)

MAX_SHOPS_PER_USER = 5
TOKEN_CHECK_MAX_WAIT = 20.0

# Похоже на токен WB: JWT из трёх частей base64url (первая начинается с eyJ).
_TOKEN_LIKE = re.compile(r"(?:bearer\s+)?eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]*", re.IGNORECASE)


def looks_like_token(text: str) -> bool:
    return bool(_TOKEN_LIKE.search(text))


@dataclass(slots=True)
class ConnectResult:
    ok: bool
    message: str = ""
    shop_name: str = ""
    available: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    updated: bool = False
    shop_id: int | None = None


@dataclass(slots=True)
class CostsResult:
    ok: bool
    message: str = ""
    saved: int = 0
    errors: list[str] = field(default_factory=list)


class BotServices:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        cipher: TokenCipher,
        wb_settings: WBSettings,
        *,
        limiters: RateLimiterRegistry | None = None,
    ) -> None:
        self._sessions = sessionmaker
        self._cipher = cipher
        self._wb_settings = wb_settings
        self._limiters = limiters

    # ── пользователи ──────────────────────────────────────────────────────────

    async def register(self, telegram_user_id: int, chat_id: int, name: str | None) -> User:
        async with self._sessions.begin() as session:
            return await repo.get_or_create_telegram_user(
                session, telegram_user_id=telegram_user_id, chat_id=chat_id, name=name
            )

    async def save_phone(self, user_id: int, phone: str) -> None:
        async with self._sessions.begin() as session:
            await repo.set_phone(session, user_id, phone)

    # ── токен и магазин ───────────────────────────────────────────────────────

    async def connect_token(self, user: User, text: str) -> ConnectResult:
        """Проверяет токен в WB и сохраняет магазин. Сам токен нигде не логируется."""
        match = _TOKEN_LIKE.search(text)
        try:
            token = normalize_token(match.group() if match else text)
        except WBTokenFormatError as exc:
            return ConnectResult(False, f"Это не похоже на токен WB: {exc}.")

        try:
            client = WBClient(
                token,
                self._wb_settings,
                limiters=self._limiters,
                max_wait=TOKEN_CHECK_MAX_WAIT,
                log_name=f"пользователь {user.id}",
            )
        except WBConfigError as exc:
            return ConnectResult(False, str(exc))

        async with client:
            info = client.token_info
            check = await check_token(
                client, (Category.COMMON, *REQUIRED_CATEGORIES, *OPTIONAL_CATEGORIES)
            )
            if not check.valid:
                return ConnectResult(
                    False,
                    "WB не принял токен: он неверный, удалён или просрочен. "
                    "Создайте новый токен и пришлите его.",
                )
            if all(
                c.status is CategoryStatus.ERROR
                for c in check.categories
                if c.category is not Category.COMMON
            ):
                return ConnectResult(
                    False, "Не удалось проверить токен — WB сейчас не отвечает. Попробуйте позже."
                )
            shop_name, seller_id = await self._seller(client)

        available = sorted(c.value for c in check.available if c is not Category.COMMON)
        seller_id = seller_id or info.seller_id
        shop_name = shop_name or f"Магазин {info.fingerprint[:6]}"
        encrypted = self._cipher.encrypt(token)
        kind = int(info.kind) if info.kind is not None else None
        name = shop_name[:255]
        async with self._sessions.begin() as session:
            existing = (
                await repo.find_shop_by_seller(session, user.id, seller_id) if seller_id else None
            )
            if existing is not None:
                shop = await repo.update_shop_token(
                    session,
                    existing,
                    name=name,
                    token_encrypted=encrypted,
                    token_fingerprint=info.fingerprint,
                    token_kind=kind,
                    token_expires_at=info.expires_at,
                    token_categories=available,
                    sandbox=self._wb_settings.sandbox,
                )
                updated = True
            else:
                if await repo.count_shops(session, user.id) >= MAX_SHOPS_PER_USER:
                    return ConnectResult(
                        False, f"Можно подключить не больше {MAX_SHOPS_PER_USER} магазинов."
                    )
                shop = await repo.create_shop(
                    session,
                    user_id=user.id,
                    name=name,
                    seller_id=seller_id,
                    token_encrypted=encrypted,
                    token_fingerprint=info.fingerprint,
                    token_kind=kind,
                    token_expires_at=info.expires_at,
                    token_categories=available,
                    sandbox=self._wb_settings.sandbox,
                )
                updated = False
            shop_id = shop.id
        logger.info(
            "Пользователь %d подключил магазин %d (токен %s, разделов: %d)",
            user.id,
            shop_id,
            info.fingerprint,
            len(available),
        )
        return ConnectResult(
            True,
            shop_name=shop_name,
            available=available,
            warnings=list(check.warnings),
            updated=updated,
            shop_id=shop_id,
        )

    @staticmethod
    async def _seller(client: WBClient) -> tuple[str | None, str | None]:
        try:
            seller = await GeneralAPI(client).seller_info()
        except WBError as exc:
            logger.info("%s: название продавца не получено: %s", client.log_name, exc)
            return None, None
        return (seller.trade_mark or seller.name), seller.sid

    async def shops(self, user_id: int) -> list[Shop]:
        async with self._sessions() as session:
            return await repo.list_shops(session, user_id)

    async def delete_shop(self, user_id: int, shop_id: int) -> bool:
        async with self._sessions.begin() as session:
            return await repo.delete_shop(session, user_id, shop_id)

    # ── себестоимость ─────────────────────────────────────────────────────────

    async def save_costs(
        self, user_id: int, shop_id: int, filename: str, content: bytes
    ) -> CostsResult:
        try:
            parsed: CostFile = parse_cost_file(filename, content)
        except CostFileError as exc:
            return CostsResult(False, str(exc))
        async with self._sessions.begin() as session:
            if await repo.get_shop(session, user_id, shop_id) is None:
                return CostsResult(False, "Магазин не найден.")
            saved = await repo.replace_cost_prices(session, shop_id, parsed.prices)
        return CostsResult(True, saved=saved, errors=parsed.errors)

    # ── анализы ───────────────────────────────────────────────────────────────

    async def start_analysis(
        self, user_id: int, shop_id: int, chat_id: int
    ) -> tuple[AnalysisRun | None, bool]:
        """(анализ, создан ли новый). None — магазин не найден."""
        async with self._sessions.begin() as session:
            run = await repo.enqueue_run(
                session,
                user_id=user_id,
                shop_id=shop_id,
                source=RunSource.TELEGRAM,
                notify_chat_id=chat_id,
            )
            if run is None:
                return None, False
            is_new = run.status == RunStatus.QUEUED and run.notify_message_id is None
            return run, is_new

    async def remember_progress_message(self, run_id: int, message_id: int) -> None:
        async with self._sessions.begin() as session:
            await repo.set_notify_message(session, run_id, message_id)

    async def history(self, user_id: int, shop_id: int) -> list[AnalysisRun]:
        async with self._sessions() as session:
            return await repo.list_runs(session, user_id, shop_id, limit=10)

    async def report_pdf(self, user_id: int, run_id: int) -> tuple[bytes, str] | None:
        async with self._sessions() as session:
            run = await repo.get_run(session, user_id, run_id)
            if run is None or run.status != RunStatus.DONE:
                return None
            shop = await repo.get_shop(session, user_id, run.shop_id)
            shop_name = shop.name if shop else "Магазин"
            pdf = build_pdf(run, shop_name)
        moment = (run.finished_at or datetime.now(UTC)).strftime("%Y-%m-%d")
        return pdf, f"wb-analysis-{run_id}-{moment}.pdf"
