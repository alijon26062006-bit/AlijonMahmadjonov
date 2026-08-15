"""Загрузка фото с сайта → пересылка боту в чат-хранилище → тот же file_id.

Файловое хранилище на сервере не нужно: фото живут в Telegram,
как и присланные в бот напрямую.
"""
import asyncio

from aiogram.types import BufferedInputFile
from fastapi import APIRouter, HTTPException, UploadFile

from app.api.deps import CurrentUser
from app.config import get_settings

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

MAX_SIZE = 10 * 1024 * 1024
MAGIC = {b"\xff\xd8\xff": "jpeg", b"\x89PNG": "png", b"RIFF": "webp"}

_sem = asyncio.Semaphore(3)


@router.post("/photo")
async def upload_photo(file: UploadFile, user: CurrentUser):
    s = get_settings()
    if not s.storage_chat_id:
        # Пользователю — по-человечески, без имён переменных из конфигурации
        raise HTTPException(503, "Загрузка фото с сайта временно недоступна. "
                                 "Подайте объявление через бота — там фото "
                                 "принимаются как обычно.")

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(413, "Файл больше 10 МБ")
    if not any(data.startswith(m) for m in MAGIC):
        raise HTTPException(415, "Поддерживаются только JPEG, PNG и WebP")

    from app.bot.factory import create_bot
    async with _sem:
        bot = create_bot()
        try:
            msg = await bot.send_photo(
                chat_id=s.storage_chat_id,
                photo=BufferedInputFile(data, filename="upload.jpg"))
        except Exception:
            # чаще всего: бот не добавлен в чат-хранилище или неверный ID —
            # это забота администратора, пользователю показываем простой текст
            raise HTTPException(
                502, "Не удалось сохранить фото. Попробуйте ещё раз или "
                     "подайте объявление через бота."
            ) from None
        finally:
            await bot.session.close()

    best, thumb = msg.photo[-1], msg.photo[0]
    photo = {"file_id": best.file_id, "thumb_file_id": thumb.file_id,
             "file_unique_id": best.file_unique_id,
             "width": best.width, "height": best.height}
    from app.api.routers.listings import sign_photo
    photo["sig"] = sign_photo(photo)
    return photo
