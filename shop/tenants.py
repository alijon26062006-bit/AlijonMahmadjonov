"""Конструктор: ҳамаи ботҳои шарикон дар як раванд.

Ҳар боти шарик базаи худро дорад (data/tenants/<bot_id>.sqlite3): харидорон,
ҳисобҳо, фармоишҳо, нархҳо ва танзимоти худаш. Ҳамаи ботҳо бо ҳамон
Dispatcher ва ҳамон коди дӯкон кор мекунанд; TenantMiddleware барои ҳар
навсозӣ базаи ҳамон ботро медиҳад.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.methods import GetUpdates

from . import requisites, wholesale
from .config import Config
from .db import Database

log = logging.getLogger(__name__)

CONSTRUCTOR_ON_KEY = "constructor_enabled"
MAX_BOTS_KEY = "constructor_max_bots"
DEFAULT_MAX_BOTS = 50
OPERATORS_KEY = "operators"
SUPPORT_KEY = "support_username"
REVIEWS_KEY = "reviews_url"

SYNC_EVERY = 60          # сония — ҳолати фармоишҳои яклухт
REPRICE_EVERY = 600      # сония — нархҳо аз нархи яклухт


@dataclass
class Platform:
    """Боти асосӣ: база, танзимот, таъминкунанда ва худи бот."""

    db: Database
    cfg: Config
    supplier: Any
    bot: Bot
    dp: Any = None


@dataclass
class TenantContext:
    id: int
    bot_id: int
    owner_id: int
    db: Database
    cfg: Config
    supplier: wholesale.WholesaleSupplier
    bot: Bot
    task: asyncio.Task | None = None
    username: str = ""


def constructor_open(db: Database) -> bool:
    return db.setting(CONSTRUCTOR_ON_KEY, "1") == "1"


def max_bots_total(db: Database) -> int:
    try:
        return max(0, int(db.setting(MAX_BOTS_KEY) or DEFAULT_MAX_BOTS))
    except ValueError:
        return DEFAULT_MAX_BOTS


def operators_of(db: Database) -> tuple[int, ...]:
    out = []
    for part in (db.setting(OPERATORS_KEY) or "").replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.append(int(part))
    return tuple(dict.fromkeys(out))


@dataclass
class TenantManager:
    platform: Platform
    contexts: dict[int, TenantContext] = field(default_factory=dict)     # bot_id → ctx
    _tasks: set = field(default_factory=set)

    # ── ёрирасонҳо ────────────────────────────────────────────────────
    def resolve(self, bot_id: int) -> TenantContext | None:
        return self.contexts.get(bot_id)

    def by_tenant(self, tenant_id: int) -> TenantContext | None:
        return next((c for c in self.contexts.values() if c.id == tenant_id), None)

    @property
    def data_dir(self) -> Path:
        return Path(self.platform.cfg.db_path).parent / "tenants"

    def db_path(self, bot_id: int) -> Path:
        return self.data_dir / f"{bot_id}.sqlite3"

    def build_cfg(self, row, tdb: Database) -> Config:
        """Танзимоти боти шарик: аз боти асосӣ, вале бе реквизит ва калидҳои соҳиб."""
        main = self.platform.cfg
        return replace(
            main,
            token=row["token"],
            admin_ids=tuple(dict.fromkeys((row["owner_id"], *operators_of(tdb)))),
            db_path=self.db_path(row["bot_id"]),
            support=(tdb.setting(SUPPORT_KEY) or "").lstrip("@"),
            reviews_url=tdb.setting(REVIEWS_KEY) or "",
            channel_url="",
            card_number="", card_holder="", alif_account="",
            supplier="tenant", supplier_url="", supplier_key="",
            donatix_key="", api_enabled=False, api_public_url="",
            tenant_id=row["id"], lang=row["lang"] or "tj",
        )

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    # ── оғоз ва қатъ ──────────────────────────────────────────────────
    async def start_all(self) -> int:
        if not constructor_open(self.platform.db):
            log.info("Конструктор хомӯш — ботҳои шарикон оғоз намешаванд.")
            return 0
        started = 0
        for row in self.platform.db.tenants():
            if row["status"] != "active":
                continue
            try:
                await self.start(row)
                started += 1
            except Exception:
                log.exception("Боти шарик #%s оғоз нашуд", row["id"])
        if started:
            log.info("Конструктор: %s боти шарик кор мекунад", started)
        return started

    async def start(self, row, *, poll: bool = True) -> TenantContext:
        from .fulfillment import resume_in_background
        from .middlewares import ButtonStyleFallback

        if row["bot_id"] in self.contexts:
            return self.contexts[row["bot_id"]]
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tdb = Database(self.db_path(row["bot_id"]))
        tdb.rotate_order_key_prefix()
        cfg = self.build_cfg(row, tdb)
        requisites.seed(tdb, cfg)
        supplier = wholesale.WholesaleSupplier(self.platform, row["id"], row["owner_id"], tdb)
        bot = Bot(token=row["token"], default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        bot.session.middleware(ButtonStyleFallback())
        ctx = TenantContext(
            id=row["id"], bot_id=row["bot_id"], owner_id=row["owner_id"], db=tdb, cfg=cfg,
            supplier=supplier, bot=bot, username=row["username"] or "",
        )
        wholesale.reprice_tenant(self.platform.db, tdb)
        self.contexts[row["bot_id"]] = ctx
        if poll:
            ctx.task = self._spawn(self._poll(ctx))
            self._spawn(self._set_commands(ctx))
            resume_in_background(bot, tdb, cfg, supplier)
        return ctx

    async def stop(self, tenant_id: int) -> None:
        ctx = self.by_tenant(tenant_id)
        if ctx is None:
            return
        self.contexts.pop(ctx.bot_id, None)
        if ctx.task is not None and ctx.task is not asyncio.current_task():
            ctx.task.cancel()
            await asyncio.gather(ctx.task, return_exceptions=True)
        try:
            await ctx.bot.session.close()
        except Exception:
            pass
        ctx.db.close()

    async def stop_all(self) -> None:
        for ctx in list(self.contexts.values()):
            await self.stop(ctx.id)
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def refresh(self, tenant_id: int) -> None:
        """Танзимот (операторон, забон, дастгирӣ) иваз шуд — бе азнавоғозкунӣ."""
        ctx = self.by_tenant(tenant_id)
        row = self.platform.db.tenant(tenant_id)
        if ctx is not None and row is not None:
            ctx.cfg = self.build_cfg(row, ctx.db)

    # ── Telegram ──────────────────────────────────────────────────────
    async def _set_commands(self, ctx: TenantContext) -> None:
        from aiogram.types import BotCommandScopeChat

        from .main import ADMIN_COMMANDS, COMMANDS

        try:
            await ctx.bot.set_my_commands(COMMANDS)
            for admin_id in ctx.cfg.admin_ids:
                await ctx.bot.set_my_commands(
                    [c for c in ADMIN_COMMANDS if c.command not in ("sku", "rang")],
                    scope=BotCommandScopeChat(chat_id=admin_id),
                )
        except Exception as exc:
            log.info("Фармонҳои боти шарик #%s: %s", ctx.id, exc)

    async def _poll(self, ctx: TenantContext) -> None:
        offset = None
        backoff = 1.0
        try:
            await ctx.bot.delete_webhook(drop_pending_updates=False)
        except TelegramUnauthorizedError:
            await self._token_revoked(ctx)
            return
        except Exception:
            pass
        while True:
            try:
                updates = await ctx.bot(GetUpdates(offset=offset, timeout=25), request_timeout=40)
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except TelegramUnauthorizedError:
                await self._token_revoked(ctx)
                return
            except Exception as exc:
                log.warning("Боти шарик #%s: навсозӣ гирифта нашуд: %s", ctx.id, exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            for update in updates:
                offset = update.update_id + 1
                self._spawn(self._feed(ctx, update))

    async def _feed(self, ctx: TenantContext, update) -> None:
        try:
            await self.platform.dp.feed_update(ctx.bot, update)
        except Exception:
            log.exception("Боти шарик #%s: хатои коркард", ctx.id)

    async def _token_revoked(self, ctx: TenantContext) -> None:
        """Шарик токенро бекор кард ё бот нест шуд — ботро хомӯш мекунем ва хабар медиҳем."""
        from .i18n import texts

        log.warning("Боти шарик #%s: токен кор намекунад — хомӯш шуд", ctx.id)
        self.platform.db.set_tenant(ctx.id, status="disabled", note="token_revoked")
        try:
            await self.platform.bot.send_message(
                ctx.owner_id, texts.tenant_token_revoked(ctx.username)
            )
        except Exception:
            pass
        self._spawn(self.stop(ctx.id))

    # ── нигоҳубин ─────────────────────────────────────────────────────
    async def maintenance_forever(self) -> None:
        ticks = 0
        while True:
            await asyncio.sleep(SYNC_EVERY)
            ticks += 1
            for ctx in list(self.contexts.values()):
                try:
                    await self.sync_orders(ctx)
                    if ticks * SYNC_EVERY % REPRICE_EVERY == 0:
                        wholesale.reprice_tenant(self.platform.db, ctx.db)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("Боти шарик #%s: нигоҳубин нашуд", ctx.id)

    def reprice_all(self) -> None:
        for ctx in list(self.contexts.values()):
            wholesale.reprice_tenant(self.platform.db, ctx.db)

    async def sync_orders(self, ctx: TenantContext) -> int:
        """Фармоишҳои кушодаи боти шарикро бо ҳолати фармоиши яклухт мувофиқ мекунад.

        Масалан, соҳиб фармоиши дастиро (Premium) иҷро кард — фармоиши харидор
        дар боти шарик низ баста мешавад ва чек меравад.
        """
        from .fulfillment import finalize, is_busy

        closed = 0
        for row in ctx.db.open_orders(200):
            ext = row["external_id"] or ""
            if not ext.startswith("W") or is_busy(ctx.db, row["id"]):
                continue
            result = await ctx.supplier.order_status(ext)
            if result.ok and result.status in ("completed", "failed"):
                await finalize(ctx.bot, ctx.db, ctx.cfg, row["id"], result.status, result.error)
                closed += 1
        return closed
