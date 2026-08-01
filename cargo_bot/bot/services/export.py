"""Экспорт данных в Excel (openpyxl)."""
import os
import tempfile
from datetime import datetime

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Order, User


def _save(wb: Workbook, prefix: str) -> str:
    path = os.path.join(
        tempfile.gettempdir(),
        f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
    )
    wb.save(path)
    return path


async def export_orders(session: AsyncSession) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Заявки"
    ws.append(["№", "Номер", "Имя", "Телефон", "Ссылка", "Описание",
               "Вес, кг", "Объём, м³", "Комментарий", "Статус", "Создана"])
    rows = (await session.scalars(select(Order).order_by(Order.id))).all()
    for o in rows:
        ws.append([o.id, o.number, o.name, o.phone, o.product_url, o.description,
                   float(o.weight) if o.weight is not None else None,
                   float(o.volume) if o.volume is not None else None,
                   o.comment, o.status,
                   o.created_at.strftime("%d.%m.%Y %H:%M") if o.created_at else ""])
    return _save(wb, "orders")


async def export_users(session: AsyncSession) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Пользователи"
    ws.append(["№", "Telegram ID", "Username", "Имя", "Телефон", "Язык", "Регистрация"])
    rows = (await session.scalars(select(User).order_by(User.id))).all()
    for u in rows:
        ws.append([u.id, u.tg_id, u.username, u.full_name, u.phone, u.language,
                   u.created_at.strftime("%d.%m.%Y %H:%M") if u.created_at else ""])
    return _save(wb, "users")
