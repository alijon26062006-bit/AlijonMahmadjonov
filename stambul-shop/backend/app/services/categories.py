"""Разделы: встроенные плюс заведённые владельцем.

Встроенные живут в коде — у них свои поля и размерные линейки. Свои живут
в базе и получают общий набор полей. Процессы у нас разные (сайт, бот,
воркер), поэтому список подтягивается там, где нужен, а не кэшируется
навсегда: запрос дешёвый, а рассинхронизация дорогая.
"""
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import schemas
from app.db.models import CustomCategory

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(title: str) -> str:
    text = unicodedata.normalize("NFKC", title).strip().lower()
    text = "".join(TRANSLIT.get(ch, ch) for ch in text)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return (text or "razdel")[:36]


async def sync(session: AsyncSession) -> None:
    """Подтягивает свои разделы в общий список."""
    rows = (await session.execute(
        select(CustomCategory.slug, CustomCategory.title,
               CustomCategory.sort_order)
        .order_by(CustomCategory.sort_order, CustomCategory.title))).all()
    schemas.register_custom([(r[0], r[1], r[2]) for r in rows])


async def create(session: AsyncSession, title: str) -> schemas.Category:
    """Заводит свой раздел. Повтор названия возвращает существующий."""
    title = " ".join(title.split())[:80]
    if len(title) < 2:
        raise ValueError("Название раздела слишком короткое")

    existing = await session.scalar(
        select(CustomCategory).where(CustomCategory.title.ilike(title)))
    if existing:
        await sync(session)
        return schemas.get_category(existing.slug)

    base = slugify(title)
    slug = base
    n = 2
    while schemas.get_category(slug) or await session.get(CustomCategory, slug):
        slug = f"{base}_{n}"
        n += 1

    session.add(CustomCategory(slug=slug, title=title))
    await session.commit()
    await sync(session)
    return schemas.get_category(slug)
