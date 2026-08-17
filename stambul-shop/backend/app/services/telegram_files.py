"""Отдача фотографий из Telegram: file_id → байты, с кэшем.

Слои:
1) диск — байты фото неизменны, после первого запроса Telegram не трогаем;
2) Redis — file_path живёт ~1 час, кэшируем на 50 минут;
3) браузер — Cache-Control: immutable + ETag (в роутере).
Стампид гасится блокировкой по file_id.
"""
import asyncio
from pathlib import Path

import httpx
from redis.asyncio import Redis

from app.config import get_settings

_locks: dict[str, asyncio.Lock] = {}
_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=20)
    return _client


def cache_path(file_unique_id: str) -> Path:
    s = get_settings()
    fu = file_unique_id
    return Path(s.media_cache_dir) / fu[:2] / fu[2:4] / f"{fu}.jpg"


async def get_photo_bytes(redis: Redis, file_id: str, file_unique_id: str) -> bytes | None:
    """Возвращает байты фото; None — если Telegram отдал ошибку."""
    path = cache_path(file_unique_id)
    if path.exists():
        return path.read_bytes()

    lock = _locks.setdefault(file_id, asyncio.Lock())
    async with lock:
        if path.exists():                       # пока ждали — кто-то скачал
            return path.read_bytes()

        s = get_settings()
        api = f"https://api.telegram.org/bot{s.bot_token}"

        # Redis здесь — только ускорение. Если он недоступен, фотографии
        # должны продолжать отдаваться, просто с лишним вызовом getFile.
        async def cache_get(key: str) -> str | None:
            try:
                v = await redis.get(key)
            except Exception:
                return None
            return v.decode() if isinstance(v, bytes) else v

        async def cache_set(key: str, value: str, ex: int) -> None:
            try:
                await redis.set(key, value, ex=ex)
            except Exception:
                pass

        async def cache_del(key: str) -> None:
            try:
                await redis.delete(key)
            except Exception:
                pass

        file_path = await cache_get(f"tgfile:{file_id}")
        if not file_path:
            r = await _http().get(f"{api}/getFile", params={"file_id": file_id})
            data = r.json()
            if not data.get("ok"):
                return None
            if (data["result"].get("file_size") or 0) > 20 * 1024 * 1024:
                return None                      # лимит скачивания Bot API
            file_path = data["result"]["file_path"]
            await cache_set(f"tgfile:{file_id}", file_path, 3000)

        r = await _http().get(
            f"https://api.telegram.org/file/bot{s.bot_token}/{file_path}")
        if r.status_code != 200:
            await cache_del(f"tgfile:{file_id}")
            return None

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(r.content)
        tmp.rename(path)
        return r.content
