"""Публичные настройки для клиента.

Позволяют интерфейсу знать заранее, что доступно, а не выяснять это
по ошибке после действия пользователя.
"""
from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
async def public_config():
    s = get_settings()
    return {
        "bot_username": s.bot_username,
        "bot_link": f"https://t.me/{s.bot_username}" if s.bot_username else None,
        # Загрузка фото с сайта возможна только при настроенном чате-хранилище
        "uploads_enabled": bool(s.storage_chat_id),
        "max_photos": s.max_photos,
        "currencies": ["TJS", "USD"],
    }
