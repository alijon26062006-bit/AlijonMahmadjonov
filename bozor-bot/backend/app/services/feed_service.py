"""Главная лента: перемешанная витрина по категориям с обучением интересам.

Устроена так, чтобы работать сразу и не требовать переделки потом:

* на пустой площадке решают свежесть и качество — интересы просто не влияют;
* как только у человека появляется история, она начинает учитываться сама,
  никаких переключателей;
* порядок случайный, но устойчивый в течение дня — прокрутка не перетасовывает
  ленту, а завтра она обновится;
* разнообразие обеспечивается принудительно: подряд не больше двух объявлений
  одной категории, часть ленты — намеренно за пределами интересов.

Веса вынесены в настройки: подбираются наблюдением, без правки кода.
"""
import hashlib
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.models import ST_APPROVED, Listing, ListingEvent, User
from app.schemas_engine.registry import get_schema

# Сколько объявлений тянем из базы перед ранжированием
CANDIDATE_LIMIT = 300
# Через столько часов вес свежести падает вдвое
FRESHNESS_HALF_LIFE_H = 72
# Не больше стольких подряд из одной категории
MAX_SAME_CATEGORY_IN_ROW = 2
# Доля ленты, отданная под «исследование» — вне интересов человека
EXPLORATION_SHARE = 0.2


def _stable_jitter(seed: str, listing_id: int) -> float:
    """Случайное, но повторяемое число 0..1 для пары «сеанс + объявление».

    Благодаря повторяемости лента не перетасовывается при прокрутке.
    """
    h = hashlib.md5(f"{seed}:{listing_id}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def session_seed(user_id: int | None) -> str:
    """Своё зерно на каждого человека и каждый день."""
    day = datetime.utcnow().strftime("%Y-%m-%d")
    return f"{user_id or 'guest'}:{day}"


def _freshness(listing: Listing, now: datetime) -> float:
    published = listing.published_at or listing.created_at
    if not published:
        return 0.0
    age_h = max((now - published.replace(tzinfo=None)).total_seconds() / 3600, 0)
    return 0.5 ** (age_h / FRESHNESS_HALF_LIFE_H)


def _quality(listing: Listing) -> float:
    """Насколько объявление вообще пригодно к показу."""
    photos = len(listing.photos)
    photo_score = min(photos / 4, 1.0)          # четыре фото и больше — максимум

    schema = get_schema(listing.category_slug)
    if schema:
        total = max(len([f for f in schema.fields if f.stored == "attrs"]), 1)
        filled = len([k for k, v in (listing.attrs or {}).items()
                      if v not in (None, "", [], False) and not k.startswith("_")])
        fields_score = min(filled / total, 1.0)
    else:
        fields_score = 0.5

    desc_score = min(len(listing.description or "") / 200, 1.0)

    # Отклик: сглажено, иначе новые объявления с нулём просмотров штрафуются
    engagement = (listing.contacts_count + listing.favorites_count + 1) / \
                 (listing.views_count + 10)
    engagement_score = min(engagement * 3, 1.0)

    return (photo_score * 0.4 + fields_score * 0.25
            + desc_score * 0.15 + engagement_score * 0.2)


async def user_affinity(session: AsyncSession, user_id: int | None) -> dict:
    """Что человек смотрел раньше: категории и города с весами 0..1.

    Пустой словарь означает «истории нет» — тогда интересы не влияют вовсе.
    """
    if not user_id:
        return {}
    since = datetime.utcnow() - timedelta(days=30)
    rows = (await session.execute(
        select(Listing.category_slug, Listing.city_id, ListingEvent.kind,
               func.count().label("n"))
        .join(Listing, Listing.id == ListingEvent.listing_id)
        .where(ListingEvent.user_id == user_id, ListingEvent.created_at > since)
        .group_by(Listing.category_slug, Listing.city_id, ListingEvent.kind))).all()
    if not rows:
        return {}

    # Обращение к продавцу — куда более сильный сигнал, чем просмотр
    weight = {"view": 1, "favorite": 4, "contact_click": 8, "share": 3}
    cats: dict[str, float] = {}
    cities: dict[int, float] = {}
    for slug, city_id, kind, n in rows:
        w = weight.get(kind, 1) * n
        cats[slug] = cats.get(slug, 0) + w
        if city_id:
            cities[city_id] = cities.get(city_id, 0) + w

    def normalize(d: dict) -> dict:
        top = max(d.values()) if d else 0
        return {k: v / top for k, v in d.items()} if top else {}

    return {"categories": normalize(cats), "cities": normalize(cities)}


def _affinity_score(listing: Listing, affinity: dict) -> float:
    """0.5 — нейтрально: когда истории нет, слагаемое никого не двигает."""
    if not affinity:
        return 0.5
    cat = affinity.get("categories", {}).get(listing.category_slug, 0.0)
    city = affinity.get("cities", {}).get(listing.city_id, 0.0) if listing.city_id else 0.0
    return cat * 0.7 + city * 0.3


def score_listing(listing: Listing, affinity: dict, seed: str,
                  now: datetime, seen: set[int]) -> float:
    s = get_settings()
    value = (
        s.feed_w_freshness * _freshness(listing, now)
        + s.feed_w_quality * _quality(listing)
        + s.feed_w_affinity * _affinity_score(listing, affinity)
        + s.feed_w_jitter * _stable_jitter(seed, listing.id)
    )
    if listing.id in seen:
        value *= 0.45      # уже видел — опускаем, но не прячем совсем
    return value


def diversify(ranked: list[Listing], affinity: dict) -> list[Listing]:
    """Перестановка ради разнообразия.

    Без неё человек, посмотревший пару квартир, утонет в квартирах и не узнает,
    что на площадке есть авто и запчасти.
    """
    known = set(affinity.get("categories", {})) if affinity else set()
    familiar = [x for x in ranked if x.category_slug in known] if known else []
    fresh_eyes = [x for x in ranked if x.category_slug not in known] if known else list(ranked)

    out: list[Listing] = []
    tail: list[str] = []
    pools = [familiar, fresh_eyes] if known else [fresh_eyes]
    explore_every = max(int(1 / EXPLORATION_SHARE), 2) if known else 0

    while any(pools):
        # каждое N-е место отдаём тому, чего человек ещё не смотрел
        prefer_new = explore_every and len(out) % explore_every == explore_every - 1
        order = [1, 0] if prefer_new else [0, 1]
        picked = None
        for idx in order:
            if idx >= len(pools) or not pools[idx]:
                continue
            for i, cand in enumerate(pools[idx]):
                same_in_row = tail[-MAX_SAME_CATEGORY_IN_ROW:].count(cand.category_slug)
                if same_in_row < MAX_SAME_CATEGORY_IN_ROW:
                    picked = pools[idx].pop(i)
                    break
            if picked:
                break
        if picked is None:      # разнообразие исчерпано — берём что есть
            for pool in pools:
                if pool:
                    picked = pool.pop(0)
                    break
        if picked is None:
            break
        out.append(picked)
        tail.append(picked.category_slug)
    return out


async def build_feed(session: AsyncSession, user: User | None,
                     offset: int, limit: int, seen: set[int] | None = None) -> list[Listing]:
    """Готовая лента для главной страницы."""
    now = datetime.utcnow()
    candidates = (await session.scalars(
        select(Listing)
        .where(Listing.status == ST_APPROVED)
        .options(selectinload(Listing.photos))
        .order_by(Listing.published_at.desc().nullslast())
        .limit(CANDIDATE_LIMIT))).all()
    if not candidates:
        return []

    affinity = await user_affinity(session, user.id if user else None)
    seed = session_seed(user.id if user else None)
    seen = seen or set()

    ranked = sorted(candidates,
                    key=lambda l: score_listing(l, affinity, seed, now, seen),
                    reverse=True)
    return diversify(ranked, affinity)[offset:offset + limit]


async def log_event(session: AsyncSession, listing_id: int,
                    user_id: int | None, kind: str) -> None:
    """Событие для будущего обучения. Сбор начинается с первого дня —
    задним числом эти данные получить неоткуда."""
    session.add(ListingEvent(listing_id=listing_id, user_id=user_id, kind=kind[:16]))
    await session.commit()
