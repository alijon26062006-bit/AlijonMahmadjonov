"""Сборка поста и публикация в канал.

Ограничения Telegram, учтённые здесь:
- caption ≤ 1024 символов и только на первом элементе медиагруппы;
- sendMediaGroup не принимает кнопки — кнопка отдельным сообщением;
- в канале разрешены только url-кнопки: t.me/<bot>/<app>?startapp=...
"""
import html

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.media_group import MediaGroupBuilder

from app.config import get_settings
from app.db.models import Listing, ListingPhoto
from app.schemas_engine.fields import CategorySchema
from app.schemas_engine.registry import option_label

CAPTION_LIMIT = 1024

CURRENCY_SIGN = {"TJS": "смн", "USD": "$"}


def esc(v) -> str:
    return html.escape(str(v))


def price_line(listing: Listing, schema: CategorySchema) -> str:
    sign = CURRENCY_SIGN.get(listing.currency, listing.currency)
    amount = f"{listing.price:,.0f}".replace(",", " ")
    unit = ""
    price_spec = schema.field("price")
    if price_spec and price_spec.unit:
        unit = f" {price_spec.unit}"
    elif schema.slug == "rent_flat":
        unit = " в месяц" if listing.attrs.get("rent_period") == "month" else " в сутки"
    negotiable = " · торг уместен" if listing.is_negotiable else ""
    return f"💰 <b>{amount} {sign}</b>{unit}{negotiable}"


def specs_line(listing: Listing, schema: CategorySchema) -> str:
    parts = []
    for spec in schema.fields:
        if not spec.post_format:
            continue
        val = listing.attrs.get(spec.key)
        if val in (None, "", False):
            continue
        label = option_label(spec, val)
        parts.append(esc(spec.post_format.replace("{v}", label)))
    return " · ".join(parts)


def build_caption(listing: Listing, schema: CategorySchema,
                  city: str | None, district: str | None) -> str:
    head = [f"<b>{schema.emoji} {esc(listing.title)}</b>", price_line(listing, schema)]
    place = ", ".join(x for x in (city, district) if x)
    if listing.address:
        place = f"{place}, {esc(listing.address)}" if place else esc(listing.address)
    if place:
        head.append(f"📍 {place}")
    if (specs := specs_line(listing, schema)):
        head.append(f"⚙️ {specs}")

    tags = " ".join(f"#{t}" for t in schema.hashtags + ([city.replace(" ", "_")] if city else []))
    header = "\n".join(head)
    reserve = len(header) + len(tags) + 6
    desc = esc(listing.description)
    room = CAPTION_LIMIT - reserve
    if len(desc) > room:
        desc = desc[: max(room - 1, 0)].rstrip() + "…"
    return f"{header}\n\n{desc}\n\n{tags}"[:CAPTION_LIMIT]


def miniapp_button(listing: Listing) -> InlineKeyboardMarkup:
    s = get_settings()
    url = f"{s.miniapp_link}?startapp=l_{listing.public_id.hex}"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🛍 Открыть в приложении", url=url)]])


async def publish_to_channel(bot: Bot, listing: Listing, schema: CategorySchema,
                             photos: list[ListingPhoto],
                             city: str | None, district: str | None) -> int | None:
    """Отправляет медиагруппу + кнопку. Возвращает message_id первого сообщения."""
    s = get_settings()
    caption = build_caption(listing, schema, city, district)

    builder = MediaGroupBuilder()
    for i, p in enumerate(photos[:10]):
        builder.add_photo(media=p.file_id,
                          caption=caption if i == 0 else None,
                          parse_mode="HTML" if i == 0 else None)
    messages = await bot.send_media_group(chat_id=s.channel_id, media=builder.build())
    await bot.send_message(chat_id=s.channel_id,
                           text=f"👆 {esc(listing.title)}",
                           reply_markup=miniapp_button(listing))
    return messages[0].message_id if messages else None


def channel_post_url(listing: Listing) -> str | None:
    s = get_settings()
    if s.channel_username and listing.channel_message_id:
        return f"https://t.me/{s.channel_username}/{listing.channel_message_id}"
    return None
