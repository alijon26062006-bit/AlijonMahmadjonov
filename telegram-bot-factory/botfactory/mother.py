"""Главный бот — фабрика. Здесь человек создаёт и правит своих ботов."""

from __future__ import annotations

import html
import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from . import texts
from .config import Settings
from .crypto import TokenCipher
from .generator import AIHub, NoKey
from .providers import PROVIDERS, ProviderError, guess_provider
from .spec import lint, summary
from .storage import STATUS_RUNNING, BotRecord, Storage, token_fingerprint
from .supervisor import StartError, Supervisor

log = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{20,}$")
MIN_PROMPT_LENGTH = 15


class New(StatesGroup):
    token = State()
    prompt = State()


class Edit(StatesGroup):
    instruction = State()


class Keys(StatesGroup):
    value = State()


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=texts.BTN_NEW)],
            [KeyboardButton(text=texts.BTN_MY_BOTS), KeyboardButton(text=texts.BTN_KEYS)],
            [KeyboardButton(text=texts.BTN_HELP)],
        ],
        resize_keyboard=True,
    )


def bot_keyboard(record: BotRecord, running: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if running:
        rows.append(
            [InlineKeyboardButton(text=texts.BTN_STOP, callback_data=f"stop:{record.id}")]
        )
    else:
        rows.append([InlineKeyboardButton(text=texts.BTN_RUN, callback_data=f"run:{record.id}")])
    rows.append(
        [
            InlineKeyboardButton(text=texts.BTN_EDIT, callback_data=f"edit:{record.id}"),
            InlineKeyboardButton(text=texts.BTN_UNDO, callback_data=f"undo:{record.id}"),
        ]
    )
    if record.link:
        rows.append([InlineKeyboardButton(text=texts.BTN_OPEN, url=record.link)])
    rows.append(
        [
            InlineKeyboardButton(text=texts.BTN_DELETE, callback_data=f"del:{record.id}"),
            InlineKeyboardButton(text=texts.BTN_BACK, callback_data="bots"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


class Factory:
    """Обработчики фабрики. Всё состояние живёт в базе и в FSM."""

    def __init__(
        self,
        *,
        settings: Settings,
        storage: Storage,
        cipher: TokenCipher,
        hub: AIHub,
        supervisor: Supervisor,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.cipher = cipher
        self.hub = hub
        self.supervisor = supervisor

    # --- вспомогательное -------------------------------------------------

    def card_text(self, record: BotRecord, used: int) -> str:
        status = texts.STATUS_LABELS.get(record.status, record.status)
        text = texts.BOT_CARD.format(
            name=html.escape(record.spec.name),
            handle=html.escape(record.handle),
            status=status,
        )
        if record.spec.ai.enabled and self.settings.ai_monthly_limit > 0:
            text += texts.BOT_CARD_AI.format(used=used, limit=self.settings.ai_monthly_limit)
        if record.last_error:
            text += texts.BOT_CARD_ERROR.format(error=html.escape(record.last_error))
        return f"{text}\n\n{summary(record.spec)}"

    def preview_text(self, record: BotRecord) -> str:
        text = texts.PREVIEW_HEADER.format(summary=summary(record.spec))
        problems = lint(record.spec)
        if problems:
            items = "\n".join(f"• {html.escape(item)}" for item in problems)
            text += texts.PREVIEW_WARNINGS.format(items=items)
        return text

    async def show_card(self, message: Message, record: BotRecord) -> None:
        used = await self.storage.ai_used(record.id)
        await message.answer(
            self.card_text(record, used),
            reply_markup=bot_keyboard(record, self.supervisor.is_running(record.id)),
            disable_web_page_preview=True,
        )

    async def can_draw(self, user_id: int) -> bool:
        """Есть ли у человека ключ поставщика, который рисует."""
        return any(
            PROVIDERS[code].draws
            for code in await self.storage.key_providers(user_id)
            if code in PROVIDERS
        )

    async def owned(self, callback: CallbackQuery) -> BotRecord | None:
        """Достать бота из callback_data и убедиться, что он принадлежит нажавшему."""
        try:
            bot_id = int((callback.data or "").split(":", 1)[1])
        except (IndexError, ValueError):
            return None
        record = await self.storage.get_bot(bot_id)
        if record is None or callback.from_user is None or record.owner_id != callback.from_user.id:
            await callback.answer("Бот не найден", show_alert=True)
            return None
        return record


def build_router(factory: Factory) -> Router:  # noqa: C901 — это карта интерфейса
    router = Router(name="factory")
    settings = factory.settings
    storage = factory.storage
    supervisor = factory.supervisor

    # --- базовые команды -------------------------------------------------

    @router.message(CommandStart())
    async def on_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        if message.from_user is not None:
            await storage.remember_user(
                message.from_user.id, message.from_user.username, message.from_user.first_name
            )
        await message.answer(
            texts.START.format(brand=html.escape(settings.brand_name)),
            reply_markup=main_keyboard(),
        )

    @router.message(Command("help"))
    @router.message(F.text == texts.BTN_HELP)
    async def on_help(message: Message) -> None:
        await message.answer(texts.HELP)

    @router.message(Command("cancel"))
    async def on_cancel(message: Message, state: FSMContext) -> None:
        if await state.get_state() is None:
            await message.answer(texts.NOTHING_TO_CANCEL)
            return
        await state.clear()
        await message.answer(texts.CANCELLED, reply_markup=main_keyboard())

    @router.message(Command("stats"))
    async def on_stats(message: Message) -> None:
        if message.from_user is None or message.from_user.id not in settings.admin_ids:
            await message.answer(texts.UNKNOWN)
            return
        numbers = await storage.stats()
        await message.answer(
            texts.STATS.format(
                users=numbers.get("users", 0),
                bots=numbers.get("bots", 0),
                running=numbers.get("running", 0),
                stopped=numbers.get("stopped", 0),
                error=numbers.get("error", 0),
                ai_calls=numbers.get("ai_calls", 0),
            )
        )

    # --- ключи ИИ ---------------------------------------------------------

    def keys_keyboard(saved: list[str]) -> InlineKeyboardMarkup:
        rows: list[list[InlineKeyboardButton]] = [
            [InlineKeyboardButton(text=texts.BTN_ADD_KEY, callback_data="addkey")]
        ]
        for code in saved:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=texts.BTN_DEL_KEY.format(title=PROVIDERS[code].title),
                        callback_data=f"delkey:{code}",
                    )
                ]
            )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    async def show_keys(message: Message, user_id: int) -> None:
        saved = await storage.key_providers(user_id)
        if saved:
            items = "\n".join(f"• {PROVIDERS[code].title}" for code in saved if code in PROVIDERS)
            text = texts.MY_KEYS.format(items=items)
        else:
            text = texts.NO_KEYS
        await message.answer(text, reply_markup=keys_keyboard(saved))

    async def ask_key(message: Message, state: FSMContext, after: str = "") -> None:
        await state.set_state(Keys.value)
        await state.update_data(after=after)
        await message.answer(texts.ASK_KEY)

    @router.message(Command("keys"))
    @router.message(F.text == texts.BTN_KEYS)
    async def on_keys(message: Message, state: FSMContext) -> None:
        await state.clear()
        if message.from_user is None:
            return
        await show_keys(message, message.from_user.id)

    @router.callback_query(F.data == "addkey")
    async def on_add_key(callback: CallbackQuery, state: FSMContext) -> None:
        await callback.answer()
        if callback.message is None:
            return
        await ask_key(callback.message, state)

    @router.callback_query(F.data.startswith("delkey:"))
    async def on_del_key(callback: CallbackQuery) -> None:
        await callback.answer()
        if callback.message is None or callback.from_user is None:
            return
        code = (callback.data or "").split(":", 1)[1]
        await storage.delete_key(callback.from_user.id, code)
        await callback.message.answer(texts.KEY_DELETED)
        await show_keys(callback.message, callback.from_user.id)

    @router.message(Keys.value)
    async def on_key_value(message: Message, state: FSMContext) -> None:
        if message.from_user is None:
            return
        key = "".join(ch for ch in (message.text or "") if ch.isprintable()).strip()
        code = guess_provider(key)
        if code is None:
            await message.answer(texts.KEY_UNKNOWN)
            return

        try:
            await message.delete()
        except Exception:  # noqa: BLE001 — не критично
            log.debug("Не удалось удалить сообщение с ключом", exc_info=True)

        note = await message.answer(texts.KEY_CHECKING)
        probe = factory.hub.build_probe(code, key)
        try:
            await probe.check()
        except ProviderError as exc:
            await note.edit_text(texts.KEY_BAD.format(error=html.escape(str(exc))))
            return
        finally:
            await probe.close()

        await storage.save_key(message.from_user.id, code, factory.cipher.encrypt(key))
        data = await state.get_data()
        await state.clear()
        await note.edit_text(texts.KEY_SAVED.format(title=PROVIDERS[code].title))

        if data.get("after") == "new":
            await begin_new(message, state)
        else:
            await show_keys(message, message.from_user.id)

    # --- создание бота ---------------------------------------------------

    async def begin_new(message: Message, state: FSMContext) -> None:
        if message.from_user is None:
            return
        count = await storage.count_bots(message.from_user.id)
        if count >= settings.max_bots_per_user:
            await message.answer(texts.LIMIT_REACHED.format(count=count))
            return
        if not await factory.hub.has_key(message.from_user.id):
            await ask_key(message, state, after="new")
            return
        await state.set_state(New.token)
        await message.answer(texts.ASK_TOKEN)

    @router.message(Command("new"))
    @router.message(F.text == texts.BTN_NEW)
    async def on_new(message: Message, state: FSMContext) -> None:
        await begin_new(message, state)

    @router.message(New.token)
    async def on_token(message: Message, state: FSMContext) -> None:
        if message.from_user is None:
            return
        token = (message.text or "").strip()

        if not TOKEN_RE.match(token):
            await message.answer(texts.BAD_TOKEN_FORMAT)
            return

        try:
            await message.delete()
        except Exception:  # noqa: BLE001 — не критично, если удалить не вышло
            log.debug("Не удалось удалить сообщение с токеном", exc_info=True)

        if await storage.token_taken(token):
            await message.answer(texts.TOKEN_TAKEN)
            await state.clear()
            return

        probe = Bot(token=token)
        try:
            info = await probe.get_me()
        except Exception:  # noqa: BLE001 — любая причина = ключ не подошёл
            await message.answer(texts.TOKEN_REJECTED)
            return
        finally:
            await probe.session.close()

        await state.update_data(
            token=token, tg_bot_id=info.id, username=info.username, title=info.first_name
        )
        await state.set_state(New.prompt)
        await message.answer(texts.TOKEN_SAVED.format(handle=html.escape(f"@{info.username}")))
        await message.answer(texts.ASK_PROMPT)

    @router.message(New.prompt)
    async def on_prompt(message: Message, state: FSMContext) -> None:
        if message.from_user is None:
            return
        prompt = (message.text or "").strip()
        if len(prompt) < MIN_PROMPT_LENGTH:
            await message.answer(texts.PROMPT_TOO_SHORT)
            return

        data = await state.get_data()
        token = data.get("token")
        if not token:
            await state.clear()
            await message.answer(texts.CANCELLED)
            return

        note = await message.answer(texts.BUILDING)
        try:
            spec = await factory.hub.create_spec(message.from_user.id, prompt)
        except ProviderError as exc:
            await note.edit_text(texts.GENERATION_FAILED.format(error=html.escape(str(exc)[:300])))
            return

        record = await storage.create_bot(
            owner_id=message.from_user.id,
            token_enc=factory.cipher.encrypt(token),
            token_hash=token_fingerprint(token),
            tg_bot_id=data.get("tg_bot_id"),
            username=data.get("username"),
            prompt=prompt,
            spec=spec,
        )
        await state.clear()
        await note.delete()
        await message.answer(factory.preview_text(record), disable_web_page_preview=True)
        if spec.ai.image_generation and not await factory.can_draw(message.from_user.id):
            await message.answer(texts.KEY_NEEDED_TO_DRAW)
        await factory.show_card(message, record)

    # --- список ботов ------------------------------------------------------

    @router.message(Command("mybots"))
    @router.message(F.text == texts.BTN_MY_BOTS)
    async def on_my_bots(message: Message, state: FSMContext) -> None:
        await state.clear()
        if message.from_user is None:
            return
        records = await storage.list_bots(message.from_user.id)
        if not records:
            await message.answer(texts.NO_BOTS)
            return
        rows = [
            [
                InlineKeyboardButton(
                    text=f"{'▶' if supervisor.is_running(r.id) else '■'} {r.spec.name}"[:64],
                    callback_data=f"bot:{r.id}",
                )
            ]
            for r in records
        ]
        await message.answer(texts.MY_BOTS, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

    @router.callback_query(F.data == "bots")
    async def on_back_to_list(callback: CallbackQuery) -> None:
        await callback.answer()
        if callback.message is None or callback.from_user is None:
            return
        records = await storage.list_bots(callback.from_user.id)
        if not records:
            await callback.message.answer(texts.NO_BOTS)
            return
        rows = [
            [
                InlineKeyboardButton(
                    text=f"{'▶' if supervisor.is_running(r.id) else '■'} {r.spec.name}"[:64],
                    callback_data=f"bot:{r.id}",
                )
            ]
            for r in records
        ]
        await callback.message.answer(
            texts.MY_BOTS, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
        )

    @router.callback_query(F.data.startswith("bot:"))
    async def on_open_bot(callback: CallbackQuery) -> None:
        await callback.answer()
        record = await factory.owned(callback)
        if record is None or callback.message is None:
            return
        await factory.show_card(callback.message, record)

    # --- запуск и остановка --------------------------------------------------

    @router.callback_query(F.data.startswith("run:"))
    async def on_run(callback: CallbackQuery) -> None:
        record = await factory.owned(callback)
        if record is None or callback.message is None:
            return
        await callback.answer()
        try:
            await supervisor.start(record)
        except StartError as exc:
            await callback.message.answer(texts.START_FAILED.format(error=html.escape(str(exc))))
            return
        fresh = await storage.get_bot(record.id)
        if fresh is not None:
            await callback.message.answer(
                texts.STARTED.format(link=fresh.link or fresh.handle),
                disable_web_page_preview=True,
            )
            await factory.show_card(callback.message, fresh)

    @router.callback_query(F.data.startswith("stop:"))
    async def on_stop(callback: CallbackQuery) -> None:
        record = await factory.owned(callback)
        if record is None or callback.message is None:
            return
        await callback.answer()
        await supervisor.stop(record.id)
        fresh = await storage.get_bot(record.id)
        await callback.message.answer(texts.STOPPED)
        if fresh is not None:
            await factory.show_card(callback.message, fresh)

    # --- правка словами --------------------------------------------------------

    @router.callback_query(F.data.startswith("edit:"))
    async def on_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
        record = await factory.owned(callback)
        if record is None or callback.message is None:
            return
        await callback.answer()
        await state.set_state(Edit.instruction)
        await state.update_data(bot_id=record.id)
        await callback.message.answer(
            texts.ASK_EDIT.format(name=html.escape(record.spec.name))
        )

    @router.message(Edit.instruction)
    async def on_edit_apply(message: Message, state: FSMContext) -> None:
        instruction = (message.text or "").strip()
        if len(instruction) < 3:
            await message.answer(texts.PROMPT_TOO_SHORT)
            return

        data = await state.get_data()
        record = await storage.get_bot(int(data.get("bot_id", 0)))
        if record is None or message.from_user is None or record.owner_id != message.from_user.id:
            await state.clear()
            await message.answer(texts.CANCELLED)
            return

        note = await message.answer(texts.UPDATING)
        try:
            spec = await factory.hub.edit_spec(record.owner_id, record.spec, instruction)
        except ProviderError as exc:
            await note.edit_text(texts.GENERATION_FAILED.format(error=html.escape(str(exc)[:300])))
            return

        await storage.update_spec(record.id, spec, instruction[:200])
        await supervisor.apply_spec(record.id, spec)
        await state.clear()
        await note.delete()

        fresh = await storage.get_bot(record.id)
        if fresh is not None:
            await message.answer(texts.EDITED)
            await factory.show_card(message, fresh)

    @router.callback_query(F.data.startswith("undo:"))
    async def on_undo(callback: CallbackQuery) -> None:
        record = await factory.owned(callback)
        if record is None or callback.message is None:
            return
        await callback.answer()
        previous = await storage.previous_version(record.id)
        if previous is None:
            await callback.message.answer(texts.NOTHING_TO_UNDO)
            return
        await storage.drop_last_version(record.id)
        await storage.update_spec(record.id, previous, "откат")
        await supervisor.apply_spec(record.id, previous)
        fresh = await storage.get_bot(record.id)
        await callback.message.answer(texts.UNDONE)
        if fresh is not None:
            await factory.show_card(callback.message, fresh)

    # --- удаление ----------------------------------------------------------------

    @router.callback_query(F.data.startswith("del:"))
    async def on_delete_ask(callback: CallbackQuery) -> None:
        record = await factory.owned(callback)
        if record is None or callback.message is None:
            return
        await callback.answer()
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=texts.BTN_DELETE_YES, callback_data=f"delyes:{record.id}"
                    ),
                    InlineKeyboardButton(text=texts.BTN_BACK, callback_data=f"bot:{record.id}"),
                ]
            ]
        )
        await callback.message.answer(
            texts.CONFIRM_DELETE.format(name=html.escape(record.spec.name)),
            reply_markup=keyboard,
        )

    @router.callback_query(F.data.startswith("delyes:"))
    async def on_delete(callback: CallbackQuery) -> None:
        record = await factory.owned(callback)
        if record is None or callback.message is None:
            return
        await callback.answer()
        await supervisor.stop(record.id, mark="")
        await storage.delete_bot(record.id)
        await callback.message.answer(texts.DELETED)

    # --- всё остальное ---------------------------------------------------------------

    @router.message()
    async def on_anything_else(message: Message) -> None:
        await message.answer(texts.UNKNOWN, reply_markup=main_keyboard())

    return router


__all__ = ["Factory", "build_router", "STATUS_RUNNING"]
