"""Подготовка фотографий товара: очередь, провайдеры, сохранение.

Обработанная версия кладётся в то же хранилище Telegram и записывается
рядом с оригиналом. Оригинал не переписывается никогда — ни при удачной
обработке, ни при повторной.
"""
import asyncio

import httpx
from aiogram.types import BufferedInputFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import ProductPhoto
from app.services import ai_check, settings_store
from app.services.telegram_files import get_photo_bytes

REMOVEBG_URL = "https://api.remove.bg/v1.0/removebg"


class StudioError(Exception):
    """Ошибка обработки, которую показываем владельцу словами."""


# ─────────────────────────── Провайдеры маски ───────────────────────────

async def _cutout_remote(data: bytes, api_key: str) -> bytes:
    """Отделение фона сторонним сервисом. Возвращает PNG с прозрачностью.

    Провайдер только вырезает товар — фон, масштаб и тень мы всё равно
    делаем сами, иначе стиль каталога перестанет быть нашим.
    """
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                REMOVEBG_URL,
                headers={"X-Api-Key": api_key},
                data={"size": "auto", "format": "png"},
                files={"image_file": ("photo.jpg", data, "image/jpeg")})
    except httpx.HTTPError as error:
        raise StudioError(f"Сервис обработки не ответил: {error}") from None
    if response.status_code == 402:
        raise StudioError("На счету сервиса обработки закончились кредиты")
    if response.status_code in (401, 403):
        raise StudioError("Ключ сервиса обработки не принят")
    if response.status_code != 200:
        raise StudioError(f"Сервис обработки вернул ошибку {response.status_code}")
    return response.content


def _compose_local(data: bytes, background: str | None):
    from app.imaging.pipeline import ImagingError, compose
    try:
        return compose(data, background=background)
    except ImagingError as error:
        raise StudioError(str(error)) from None


def _compose_from_cutout(cutout_png: bytes, background: str | None):
    """Тот же сбор кадра, но маска уже готова — пришла от сервиса."""
    from app.imaging.pipeline import ImagingError, compose
    try:
        return compose(b"", background=background, cutout_png=cutout_png)
    except ImagingError as error:
        raise StudioError(str(error)) from None


# ─────────────────────────── Обработка одной фотографии ───────────────────

async def process(session: AsyncSession, photo_id: int,
                  background: str | None = None, *,
                  mode: str = "standard", note: str = "",
                  category_slug: str = "") -> ProductPhoto:
    """Готовит карточную версию фотографии и сохраняет её рядом с оригиналом.

    Два режима, и разница между ними принципиальная.

    `standard` — фон, свет и кадр. Пиксели товара переносятся как есть,
    поэтому изменить его физически невозможно и сверять нечего.

    `reshape` — съёмочная ретушь: вешалка из-под воротника, завернувшийся
    рукав, перекос, объём плеч. Здесь картинку перерисовывает модель, и
    результат обязательно сверяется с оригиналом. Не сошлось — карточка
    не встаёт на витрину сама, а ждёт человека.
    """
    photo = await session.get(ProductPhoto, photo_id)
    if photo is None:
        raise StudioError("Фотография не найдена")

    s = get_settings()
    if not s.storage_chat_id:
        raise StudioError("Не настроен приватный чат-хранилище")

    photo.processing = "working"
    photo.processing_error = None
    await session.commit()

    try:
        from app.api.deps import get_redis
        data = await get_photo_bytes(get_redis(), photo.file_id,
                                     photo.file_unique_id)
        if not data:
            raise StudioError("Не удалось получить исходную фотографию")

        if mode == "reshape":
            result, verdict = await _reshape(session, data, background,
                                             note, category_slug)
        else:
            result, verdict = await _standard(session, data, background), None

        stored = await _store(result.data)
        photo.proc_file_id = stored["file_id"]
        photo.proc_thumb_file_id = stored["thumb_file_id"]
        photo.proc_thumb_w = stored["thumb_w"]
        photo.proc_file_unique_id = stored["file_unique_id"]
        photo.background = result.background
        photo.style_version = result.style_version
        photo.mode = mode

        if mode == "reshape":
            from app.imaging.fashion import PROMPT_VERSION
            photo.prompt_version = PROMPT_VERSION
            photo.check_status = ai_check.status_of(verdict)
            photo.check_note = _verdict_text(verdict)
            ok = photo.check_status == "ok"
            photo.processing = "ready" if ok else "review"
            # спорную ретушь на витрину сами не ставим
            photo.use_processed = ok
        else:
            photo.prompt_version = None
            photo.check_status = "ok"
            photo.check_note = "пиксели товара не менялись"
            photo.processing = "ready"
            photo.use_processed = True

        await session.commit()
        return photo
    except StudioError as error:
        photo.processing = "failed"
        photo.processing_error = str(error)[:300]
        await session.commit()
        raise
    except Exception as error:                       # непредвиденное
        photo.processing = "failed"
        photo.processing_error = f"{type(error).__name__}: {error}"[:300]
        await session.commit()
        raise StudioError("Обработка не удалась, попробуйте ещё раз") from None


async def _standard(session: AsyncSession, data: bytes,
                    background: str | None):
    """Фон, свет, кадр. Товар переносится пиксель в пиксель."""
    provider = await settings_store.get(session, "ai_provider", "local")
    api_key = await settings_store.get(session, "ai_api_key")
    if provider == "removebg" and api_key:
        cutout = await _cutout_remote(data, api_key)
        return await asyncio.to_thread(_compose_from_cutout, cutout, background)
    # локально: модель строит маску прямо на сервере, ключ не нужен
    return await asyncio.to_thread(_compose_local, data, background)


async def _reshape(session: AsyncSession, data: bytes, background: str | None,
                   note: str, category_slug: str):
    """Съёмочная ретушь с обязательной сверкой результата."""
    from app.imaging import fashion
    from app.imaging.pipeline import ImagingError, fit_canvas

    key, model = await settings_store.openai(session)
    if not key:
        raise StudioError("Для исправления формы нужен ключ OpenAI "
                          "в настройках")

    try:
        raw = await fashion.retouch(
            data, api_key=key, kind=fashion.kind_for(category_slug),
            reshape=True, background=background or "very_light", note=note)
    except fashion.FashionError as error:
        raise StudioError(str(error)) from None

    try:
        result = await asyncio.to_thread(fit_canvas, raw, background)
    except ImagingError as error:
        raise StudioError(str(error)) from None

    try:
        verdict = await ai_check.compare(data, raw, api_key=key, model=model)
    except ai_check.CheckError:
        # Сверка не прошла по техническим причинам — это не повод считать
        # результат хорошим. Отправляем на проверку человеку.
        verdict = {"same_product": False, "severity": "minor",
                   "differences": [], "note": "сверка не выполнилась"}
    return result, verdict


def _verdict_text(verdict: dict | None) -> str:
    if not verdict:
        return ""
    if verdict["severity"] == "none":
        return "сверка с оригиналом: расхождений нет"
    parts = verdict["differences"] or ([verdict["note"]] if verdict["note"]
                                       else ["есть сомнения"])
    head = "товар изменился" if verdict["severity"] == "major" else "возможны отличия"
    return f"{head}: " + "; ".join(parts)[:400]


async def _store(data: bytes) -> dict:
    """Кладёт готовую картинку в чат-хранилище и возвращает её приметы."""
    from app.bot.factory import create_bot

    bot = create_bot()
    try:
        message = await bot.send_photo(
            chat_id=get_settings().storage_chat_id,
            photo=BufferedInputFile(data, filename="catalog.jpg"))
    except Exception:
        raise StudioError("Не удалось сохранить обработанную фотографию") from None
    finally:
        await bot.session.close()

    best = message.photo[-1]
    thumb = next((x for x in message.photo if (x.width or 0) >= 400), best)
    return {"file_id": best.file_id, "thumb_file_id": thumb.file_id,
            "thumb_w": thumb.width, "file_unique_id": best.file_unique_id}


async def pending_for_product(session: AsyncSession, product_id: int) -> list[int]:
    rows = (await session.scalars(
        select(ProductPhoto.id)
        .where(ProductPhoto.product_id == product_id)
        .order_by(ProductPhoto.position))).all()
    return list(rows)
