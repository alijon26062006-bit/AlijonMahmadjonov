"""Главная лента: перемешанная витрина по категориям."""
from fastapi import APIRouter

from app.api.deps import Cache, Db, OptionalUser
from app.services import feed_service

router = APIRouter(prefix="/api/feed", tags=["feed"])

SEEN_TTL = 3 * 24 * 3600      # что человек уже видел — помним три дня


@router.get("")
async def feed(session: Db, redis: Cache, user: OptionalUser,
               offset: int = 0, limit: int = 20):
    from app.api.routers.listings import _card, _names

    key = f"seen:{user.id}" if user else None
    seen: set[int] = set()
    if key:
        try:
            raw = await redis.smembers(key)
            seen = {int(x) for x in raw}
        except Exception:
            pass          # кэш недоступен — просто не учитываем «уже видел»

    items = await feed_service.build_feed(
        session, user, offset=max(offset, 0), limit=min(max(limit, 1), 50), seen=seen)

    if key and items:
        try:
            await redis.sadd(key, *[l.id for l in items])
            await redis.expire(key, SEEN_TTL)
        except Exception:
            pass

    cities, districts = await _names(session, items)
    from app.schemas_engine.registry import get_schema

    out = []
    for l in items:
        card = _card(l, cities, districts)
        schema = get_schema(l.category_slug)
        # Метка категории показывается прямо на карточке
        card["category_title"] = schema.title if schema else l.category_slug
        card["direction"] = schema.parent if schema else None
        out.append(card)

    return {"items": out, "has_more": len(items) == limit}
