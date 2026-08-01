"""Универсальный CRUD-движок админ-панели.

Работает по реестру сущностей (registry.py): списки с пагинацией,
карточка записи, пошаговое добавление, редактирование любого поля,
вкл/выкл, удаление с подтверждением. Каждое изменение пишется в журнал
(таблица logs) со старыми и новыми значениями.

Формат callback-данных:
  e:<key>:list:<page>            список
  e:<key>:view:<id>              карточка
  e:<key>:add                    начать добавление
  e:<key>:av:<value>             значение поля при добавлении (choice/fk/bool)
  e:<key>:ef:<id>:<fi>           редактировать поле fi
  e:<key>:sv:<id>:<fi>:<value>   сохранить значение (choice/fk/bool)
  e:<key>:tg:<id>                вкл/выкл
  e:<key>:delc:<id> / del:<id>   удаление
"""
import math

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters import IsAdmin
from bot.keyboards import main_menu, paginate_kb
from bot.repositories import Repository
from bot.services import log_action, snapshot
from bot.states import CrudStates
from bot.texts import t

from .registry import ENTITIES, Entity, Field

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

B = InlineKeyboardButton
SKIP = "_"


def _trunc(text: str, n: int = 42) -> str:
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


async def _options(session: AsyncSession, f: Field) -> list[tuple[str, str]]:
    if f.ftype == "bool":
        return [("1", "Да"), ("0", "Нет")]
    if f.ftype == "choice":
        return list(f.choices)
    if f.ftype == "currency":
        from bot.models import Currency
        rows = await Repository(session, Currency).list(is_active=True)
        return [(c.code, f"{c.code} ({c.name})") for c in rows]
    if f.ftype == "fk":
        e = ENTITIES[f.fk]
        rows = await Repository(session, e.model).list(limit=50, order_by=e.order_by)
        return [(str(r.id), _trunc(e.row(r), 30)) for r in rows]
    return []


def _parse_cb_value(f: Field, raw: str):
    if raw == SKIP:
        return None
    if f.ftype in ("fk",):
        return int(raw)
    if f.ftype == "bool":
        return raw == "1"
    return raw


def _parse_text_value(f: Field, text: str):
    text = (text or "").strip()
    if text in {"-", "—"}:
        if f.required:
            raise ValueError("Это поле обязательно.")
        return None
    if f.ftype == "int":
        try:
            return int(text)
        except ValueError:
            raise ValueError("Введите целое число.") from None
    if f.ftype == "dec":
        try:
            return float(text.replace(",", "."))
        except ValueError:
            raise ValueError("Введите число, например: 5.5") from None
    return text


async def _display(session: AsyncSession, f: Field, value) -> str:
    if value is None:
        return "—"
    if f.ftype == "bool":
        return "Да" if value else "Нет"
    if f.ftype == "choice":
        return dict(f.choices).get(str(value), str(value))
    if f.ftype == "fk":
        e = ENTITIES[f.fk]
        obj = await Repository(session, e.model).get(int(value))
        return _trunc(e.row(obj), 40) if obj else f"#{value}?"
    return str(value)


async def _render_list(session: AsyncSession, e: Entity, page: int):
    repo = Repository(session, e.model)
    total = await repo.count()
    pages = max(1, math.ceil(total / e.per_page))
    page = min(max(1, page), pages)
    items = await repo.list(offset=(page - 1) * e.per_page, limit=e.per_page,
                            order_by=e.order_by)
    rows = []
    for obj in items:
        mark = ""
        if e.has_active and not getattr(obj, "is_active", True):
            mark = "🚫 "
        rows.append([B(text=mark + _trunc(e.row(obj)),
                       callback_data=f"e:{e.key}:view:{obj.id}")])
    if e.can_add:
        rows.append([B(text="➕ Добавить", callback_data=f"e:{e.key}:add")])
    kb = paginate_kb(f"e:{e.key}:list", page, pages, extra_rows=rows)
    return f"{e.title}\nВсего записей: {total}", kb


async def _render_view(session: AsyncSession, e: Entity, obj):
    lines = [f"<b>{e.title_one}</b> #{obj.id}", ""]
    kb_rows = []
    for i, f in enumerate(e.fields):
        value = await _display(session, f, getattr(obj, f.name, None))
        lines.append(f"<b>{f.label}:</b> {value}")
        kb_rows.append([B(text=f"✏️ {f.label}", callback_data=f"e:{e.key}:ef:{obj.id}:{i}")])
    if e.has_active:
        status = "✅ Активен" if getattr(obj, "is_active", True) else "🚫 Отключён"
        lines.append(f"\n<b>Статус:</b> {status}")
        kb_rows.append([B(text="🔁 Вкл/Выкл", callback_data=f"e:{e.key}:tg:{obj.id}")])
    if e.can_delete:
        kb_rows.append([B(text="🗑 Удалить", callback_data=f"e:{e.key}:delc:{obj.id}")])
    kb_rows.append([B(text="◀️ К списку", callback_data=f"e:{e.key}:list:1")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=kb_rows)


async def _ask_field(message: Message, state: FSMContext, session: AsyncSession,
                     e: Entity, idx: int):
    f = e.fields[idx]
    prompt = f"({idx + 1}/{len(e.fields)}) <b>{f.label}</b>"
    if f.hint:
        prompt += f"\nℹ️ {f.hint}"
    if f.ftype in ("choice", "fk", "currency", "bool"):
        opts = await _options(session, f)
        rows = [[B(text=label, callback_data=f"e:{e.key}:av:{val}")] for val, label in opts]
        if not f.required:
            rows.append([B(text="⏭ Пропустить", callback_data=f"e:{e.key}:av:{SKIP}")])
        await message.answer(prompt, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    else:
        if not f.required:
            prompt += "\n(Отправьте «-», чтобы пропустить)"
        await message.answer(prompt)


async def _finalize_add(message: Message, state: FSMContext, session: AsyncSession,
                        e: Entity, vals: dict, actor_id: int):
    await state.clear()
    if e.key == "rate":
        vals["updated_by"] = actor_id
    obj = await Repository(session, e.model).add(**vals)
    await log_action(session, actor_id, "create", e.model.__tablename__, obj.id,
                     new=snapshot(obj))
    text, kb = await _render_view(session, e, obj)
    await message.answer(f"✅ Запись создана.\n\n{text}", reply_markup=kb)


async def _save_field(session: AsyncSession, e: Entity, obj, f: Field, value,
                      actor_id: int):
    old = snapshot(obj)
    values = {f.name: value}
    if e.key == "rate":
        values["updated_by"] = actor_id
    await Repository(session, e.model).update(obj, **values)
    await log_action(session, actor_id, "update", e.model.__tablename__, obj.id,
                     old={f.name: old.get(f.name)}, new={f.name: str(value)})


@router.callback_query(F.data.startswith("e:"))
async def crud_callback(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    parts = cb.data.split(":")
    e = ENTITIES.get(parts[1])
    if not e:
        await cb.answer("Неизвестная сущность", show_alert=True)
        return
    action = parts[2]
    repo = Repository(session, e.model)

    if action == "list":
        await state.clear()
        text, kb = await _render_list(session, e, int(parts[3]))
        await cb.message.edit_text(text, reply_markup=kb)

    elif action == "view":
        obj = await repo.get(int(parts[3]))
        if not obj:
            await cb.answer("Запись не найдена", show_alert=True)
            return
        text, kb = await _render_view(session, e, obj)
        await cb.message.edit_text(text, reply_markup=kb)

    elif action == "add":
        await state.set_state(CrudStates.add_value)
        await state.set_data({"ent": e.key, "vals": {}, "idx": 0})
        await cb.message.answer(f"➕ Новая запись: {e.title_one}")
        await _ask_field(cb.message, state, session, e, 0)

    elif action == "av":
        data = await state.get_data()
        if await state.get_state() != CrudStates.add_value.state or data.get("ent") != e.key:
            await cb.answer("Сессия добавления не активна", show_alert=True)
            return
        idx = data["idx"]
        f = e.fields[idx]
        vals = data["vals"]
        vals[f.name] = _parse_cb_value(f, parts[3])
        idx += 1
        if idx < len(e.fields):
            await state.update_data(vals=vals, idx=idx)
            await _ask_field(cb.message, state, session, e, idx)
        else:
            await _finalize_add(cb.message, state, session, e, vals, cb.from_user.id)

    elif action == "ef":
        obj_id, fi = int(parts[3]), int(parts[4])
        f = e.fields[fi]
        if f.ftype in ("choice", "fk", "currency", "bool"):
            opts = await _options(session, f)
            rows = [[B(text=label, callback_data=f"e:{e.key}:sv:{obj_id}:{fi}:{val}")]
                    for val, label in opts]
            if not f.required:
                rows.append([B(text="🚫 Очистить (NULL)",
                               callback_data=f"e:{e.key}:sv:{obj_id}:{fi}:{SKIP}")])
            rows.append([B(text="◀️ Назад", callback_data=f"e:{e.key}:view:{obj_id}")])
            await cb.message.edit_text(
                f"<b>{f.label}</b> — выберите значение:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            )
        else:
            await state.set_state(CrudStates.edit_value)
            await state.set_data({"ent": e.key, "id": obj_id, "fi": fi})
            hint = f"\nℹ️ {f.hint}" if f.hint else ""
            null_hint = "" if f.required else "\n(Отправьте «-», чтобы очистить)"
            await cb.message.answer(
                f"Введите новое значение поля <b>{f.label}</b>:{hint}{null_hint}"
            )

    elif action == "sv":
        obj_id, fi = int(parts[3]), int(parts[4])
        f = e.fields[fi]
        obj = await repo.get(obj_id)
        if not obj:
            await cb.answer("Запись не найдена", show_alert=True)
            return
        value = _parse_cb_value(f, parts[5])
        if value is None and f.required:
            await cb.answer("Поле обязательно", show_alert=True)
            return
        await _save_field(session, e, obj, f, value, cb.from_user.id)
        text, kb = await _render_view(session, e, obj)
        await cb.message.edit_text(f"✅ Сохранено.\n\n{text}", reply_markup=kb)

    elif action == "tg":
        obj = await repo.get(int(parts[3]))
        if not obj:
            await cb.answer("Запись не найдена", show_alert=True)
            return
        old = snapshot(obj)
        await repo.update(obj, is_active=not obj.is_active)
        await log_action(session, cb.from_user.id, "toggle", e.model.__tablename__,
                         obj.id, old={"is_active": old.get("is_active")},
                         new={"is_active": str(obj.is_active)})
        text, kb = await _render_view(session, e, obj)
        await cb.message.edit_text(text, reply_markup=kb)

    elif action == "delc":
        obj_id = int(parts[3])
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [B(text="🗑 Да, удалить", callback_data=f"e:{e.key}:del:{obj_id}"),
             B(text="◀️ Отмена", callback_data=f"e:{e.key}:view:{obj_id}")],
        ])
        await cb.message.edit_text("Удалить запись безвозвратно?", reply_markup=kb)

    elif action == "del":
        obj = await repo.get(int(parts[3]))
        if obj:
            old = snapshot(obj)
            await repo.delete(obj.id)
            await log_action(session, cb.from_user.id, "delete",
                             e.model.__tablename__, int(parts[3]), old=old)
        text, kb = await _render_list(session, e, 1)
        await cb.message.edit_text(f"🗑 Удалено.\n\n{text}", reply_markup=kb)

    await cb.answer()


@router.message(CrudStates.add_value)
async def crud_add_text(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == t("btn_cancel"):
        await state.clear()
        await message.answer(t("cancelled"), reply_markup=main_menu())
        return
    data = await state.get_data()
    e = ENTITIES[data["ent"]]
    idx = data["idx"]
    f = e.fields[idx]
    if f.ftype in ("choice", "fk", "currency", "bool"):
        await message.answer("Выберите значение кнопкой выше 👆")
        return
    try:
        value = _parse_text_value(f, message.text)
    except ValueError as err:
        await message.answer(f"⚠️ {err}")
        return
    vals = data["vals"]
    vals[f.name] = value
    idx += 1
    if idx < len(e.fields):
        await state.update_data(vals=vals, idx=idx)
        await _ask_field(message, state, session, e, idx)
    else:
        await _finalize_add(message, state, session, e, vals, message.from_user.id)


@router.message(CrudStates.edit_value)
async def crud_edit_text(message: Message, state: FSMContext, session: AsyncSession):
    if message.text == t("btn_cancel"):
        await state.clear()
        await message.answer(t("cancelled"), reply_markup=main_menu())
        return
    data = await state.get_data()
    e = ENTITIES[data["ent"]]
    f = e.fields[data["fi"]]
    try:
        value = _parse_text_value(f, message.text)
    except ValueError as err:
        await message.answer(f"⚠️ {err}")
        return
    repo = Repository(session, e.model)
    obj = await repo.get(data["id"])
    if not obj:
        await state.clear()
        await message.answer("Запись не найдена.")
        return
    await _save_field(session, e, obj, f, value, message.from_user.id)
    await state.clear()
    text, kb = await _render_view(session, e, obj)
    await message.answer(f"✅ Сохранено.\n\n{text}", reply_markup=kb)
