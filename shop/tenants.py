"""Конструктор: ҳамаи ботҳои шарикон дар як раванд.

Ҳар боти шарик базаи худро дорад (data/tenants/<bot_id>.sqlite3): харидорон,
ҳисобҳо, фармоишҳо, нархҳо ва танзимоти худаш. Ҳамаи ботҳо бо ҳамон
Dispatcher ва ҳамон коди дӯкон кор мекунанд; TenantMiddleware барои ҳар
навсозӣ базаи ҳамон ботро медиҳад.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field, replace
from datetime import timedelta
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError
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
ORPHAN_AFTER = timedelta(minutes=3)     # фармоиши нав, ки ба иҷро нарафт
# Сабаби рад барои харидори боти шарик — бе ҷузъиёти дохилии платформа.
PUBLIC_FAIL = "Таъминкунанда фармоишро иҷро накард"
REPRICE_EVERY = 600      # сония — нархҳо аз нархи яклухт


class TenantBusy(Exception):
    """Дар боти шарик фармоиш ҳоло иҷро мешавад — нест кардан мумкин нест."""


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
    feeds: set = field(default_factory=set)     # навсозиҳое, ки ҳоло коркард мешаванд


def constructor_open(db: Database) -> bool:
    return db.setting(CONSTRUCTOR_ON_KEY, "1") == "1"


def max_bots_total(db: Database) -> int:
    try:
        return max(0, int(db.setting(MAX_BOTS_KEY) or DEFAULT_MAX_BOTS))
    except ValueError:
        return DEFAULT_MAX_BOTS


CONFLICT_ALERT_AFTER = 6          # ~1 дақиқа низоъи пайваста


def texts_conflict(username: str) -> str:
    return (
        f"⚠️ <b>Боти @{username} дар ду ҷо кор мекунад</b>\n\n"
        "Ҳамин токен дар барнома ё сервери дигар низ истифода мешавад — харидорон "
        "ҷавобро аз он мегиранд, на аз дӯкони шумо. Онро хомӯш кунед ё дар "
        "@BotFather токени нав гиред ва дар «🤖 Ботҳои ман» гузоред."
    )


@contextlib.contextmanager
def bot_context(lang: str, tenant_id: int):
    """Забон ва боти ҷорӣ барои кори паси парда (вазифаҳо контекстро мерос мегиранд)."""
    from .i18n import LANG, TENANT

    lang_token, tenant_token = LANG.set(lang or "tj"), TENANT.set(int(tenant_id or 0))
    try:
        yield
    finally:
        LANG.reset(lang_token)
        TENANT.reset(tenant_token)


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
    # Базаҳо пас аз қатъи бот кушода мемонанд: вазифаҳои иҷрои фармоиш ҳанӯз
    # метавонанд бо онҳо кор кунанд. Ҳангоми хомӯшии пурраи бот баста мешаванд.
    _dbs: dict[int, Database] = field(default_factory=dict)

    # ── ёрирасонҳо ────────────────────────────────────────────────────
    def resolve(self, bot_id: int) -> TenantContext | None:
        return self.contexts.get(bot_id)

    def is_main(self, bot_id: int) -> bool:
        return bot_id == self.platform.bot.id

    def open_db(self, bot_id: int) -> Database:
        tdb = self._dbs.get(bot_id)
        if tdb is None:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            tdb = self._dbs[bot_id] = Database(self.db_path(bot_id))
        return tdb

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
            owner_ids=(row["owner_id"],),
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

    async def start(self, row, *, poll: bool = True) -> TenantContext | None:
        from .fulfillment import resume_in_background
        from .middlewares import ButtonStyleFallback

        if row["bot_id"] in self.contexts:
            return self.contexts[row["bot_id"]]
        if not constructor_open(self.platform.db) or row["status"] != "active":
            return None
        tdb = self.open_db(row["bot_id"])
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
            with bot_context(cfg.lang, ctx.id):
                resume_in_background(bot, tdb, cfg, supplier)
        return ctx

    async def stop(self, tenant_id: int) -> None:
        """Ботро аз гирифтани навсозиҳо бозмедорад.

        Навсозиҳое, ки ҳоло коркард мешаванд (масалан, харидор «Тасдиқ»-ро
        пахш кард), то охир мерасанд — бекор кардани онҳо фармоишро нимкора мемонд.
        """
        ctx = self.by_tenant(tenant_id)
        if ctx is None:
            return
        self.contexts.pop(ctx.bot_id, None)
        if ctx.task is not None and ctx.task is not asyncio.current_task():
            ctx.task.cancel()
            await asyncio.gather(ctx.task, return_exceptions=True)
        self._spawn(self._close_when_idle(ctx))

    async def _close_when_idle(self, ctx: TenantContext) -> None:
        pending = [t for t in ctx.feeds if t is not asyncio.current_task()]
        if pending:
            await asyncio.wait(pending, timeout=120)
        try:
            await ctx.bot.session.close()
        except Exception:
            pass

    def tenant_db(self, bot_id: int) -> Database | None:
        """Базаи боти шарик (агар файл ҳаст), барои омор пеш аз нест кардан."""
        if bot_id in self._dbs or self.db_path(bot_id).exists():
            return self.open_db(bot_id)
        return None

    async def remove(self, row, backup_dir: Path) -> Path | None:
        """Боти шарикро пурра нест мекунад: бот, база ва сабт дар платформа.

        Пеш аз нест кардан нусхаи база дар ``backup_dir`` сохта мешавад
        (бармегардонад роҳи он ё None, агар база набуд). Агар фармоише ҳоло
        иҷро шавад — ``TenantBusy``: базаро зери вазифаи кушода пок намекунем.
        """
        from datetime import datetime

        from .fulfillment import is_busy

        tdb = self.tenant_db(row["bot_id"])
        if tdb is not None and any(is_busy(tdb, o["id"]) for o in tdb.open_orders(500)):
            raise TenantBusy(row["id"])

        ctx = self.by_tenant(row["id"])
        await self.stop(row["id"])
        if ctx is not None and ctx.feeds:
            await asyncio.wait(list(ctx.feeds), timeout=30)

        backup = None
        if tdb is not None:
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M")
            backup = backup_dir / f"bot-{row['username'] or row['bot_id']}-{stamp}.sqlite3"
            tdb.backup_to(backup)
            self._dbs.pop(row["bot_id"], None)
            tdb.close()
        path = self.db_path(row["bot_id"])
        for extra in ("", "-wal", "-shm"):
            Path(f"{path}{extra}").unlink(missing_ok=True)
        self.platform.db.delete_tenant(row["id"])
        log.warning("Боти шарик #%s (@%s) пурра нест карда шуд", row["id"], row["username"])
        return backup

    async def pause_all(self) -> None:
        """Конструктор хомӯш шуд: ҳамаи ботҳои шарикон қатъ мешаванд (маълумот мемонад)."""
        for ctx in list(self.contexts.values()):
            await self.stop(ctx.id)

    async def stop_all(self) -> None:
        """Хомӯшии пурраи раванд (пас аз қатъи вазифаҳои иҷрои фармоиш)."""
        for ctx in list(self.contexts.values()):
            self.contexts.pop(ctx.bot_id, None)
            try:
                await ctx.bot.session.close()
            except Exception:
                pass
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        for tdb in self._dbs.values():
            tdb.close()
        self._dbs.clear()

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
        conflicts = 0
        while True:
            try:
                updates = await ctx.bot(GetUpdates(offset=offset, timeout=25), request_timeout=40)
                backoff = 1.0
                conflicts = 0
            except asyncio.CancelledError:
                raise
            except TelegramUnauthorizedError:
                await self._token_revoked(ctx)
                return
            except TelegramConflictError:
                # Ҳамин токен дар ҷои дигар низ кор мекунад — харидорон ҷавоби
                # нусхаи дигарро мегиранд. Ба шарик як бор мегӯем.
                conflicts += 1
                if conflicts == CONFLICT_ALERT_AFTER:
                    await self._tell_owner(ctx, texts_conflict(ctx.username))
                await asyncio.sleep(min(backoff, 10))
                backoff = min(backoff * 2, 30)
                continue
            except Exception as exc:
                log.warning("Боти шарик #%s: навсозӣ гирифта нашуд: %s", ctx.id, exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            for update in updates:
                offset = update.update_id + 1
                task = self._spawn(self._feed(ctx, update))
                ctx.feeds.add(task)
                task.add_done_callback(ctx.feeds.discard)

    async def _feed(self, ctx: TenantContext, update) -> None:
        try:
            await self.platform.dp.feed_update(ctx.bot, update)
        except Exception:
            log.exception("Боти шарик #%s: хатои коркард", ctx.id)

    async def _tell_owner(self, ctx: TenantContext, text: str) -> None:
        try:
            await self.platform.bot.send_message(ctx.owner_id, text)
        except Exception:
            pass

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

        Фармоиши нимкора (бот дар миёнаи харид қатъ шуд) боз фиристода мешавад:
        калиди такрор кафолат медиҳад, ки пули яклухт ду бор гирифта намешавад.
        """
        from .fulfillment import _age, deliver_order, finalize, is_busy, pick_supplier

        closed = 0
        with bot_context(ctx.cfg.lang, ctx.id):
            for row in ctx.db.open_orders(200):
                if is_busy(ctx.db, row["id"]):
                    continue
                ext = row["external_id"] or ""
                if ext.startswith("W"):
                    result = await ctx.supplier.order_status(ext)
                    if result.ok and result.status in ("completed", "failed"):
                        await finalize(ctx.bot, ctx.db, ctx.cfg, row["id"], result.status,
                                       PUBLIC_FAIL if result.status == "failed" else None)
                        closed += 1
                    continue
                stuck = row["status"] == "new" and (
                    row["supplier_ref"] or _age(row) > ORPHAN_AFTER
                )
                if stuck and pick_supplier(ctx.cfg, ctx.supplier, row["kind"] or "game",
                                           row["sku"] or "") is not None:
                    await deliver_order(ctx.bot, ctx.db, ctx.cfg, ctx.supplier, row["id"])
        return closed
