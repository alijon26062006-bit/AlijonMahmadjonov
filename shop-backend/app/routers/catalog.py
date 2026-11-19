from decimal import ROUND_CEILING, Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..money import d, sell_price
from ..settings_store import get_markup
from ..supplier import SupplierError, cache, get_supplier

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def supplier_http_error(e: SupplierError) -> HTTPException:
    if e.status == 404:
        return HTTPException(404, "Не найдено")
    if e.status == 429:
        return HTTPException(429, "Слишком часто. Подождите немного.")
    return HTTPException(502, "Каталог временно недоступен, попробуйте через минуту")


def _ttl() -> int:
    return get_settings().catalog_cache_seconds


@router.get("/topups")
def topup_list():
    """Games/services for top-up. No supplier images (rights holders' artwork)."""
    try:
        items = cache.get("topups", _ttl(), lambda: get_supplier().topup_categories())
    except SupplierError as e:
        raise supplier_http_error(e)
    return {"items": [{"id": i["category_id"], "name": i["name"], "note": i.get("note") or ""} for i in items]}


def _validate_games() -> dict[str, dict]:
    games = cache.get("validate_games", _ttl(), lambda: get_supplier().validate_id_games())
    return {g["category_id"]: g for g in games}


@router.get("/topups/{category_id}")
def topup_detail(category_id: str, db: Session = Depends(get_db)):
    try:
        data = cache.get(f"offers:{category_id}", _ttl(), lambda: get_supplier().topup_offers(category_id))
        can_check = category_id in _validate_games()
    except SupplierError as e:
        raise supplier_http_error(e)
    markup = get_markup(db)
    offers = [{"id": str(o["offer_id"]), "name": o["name"], "price": f"{sell_price(o['price_usd'], markup):.2f}"}
              for o in data.get("offers", [])]
    fields = [{"key": f.get("key"), "label": f.get("label"), "type": f.get("type", "text"),
               "options": f.get("options") or []} for f in data.get("fields", [])]
    return {"id": data["category_id"], "name": data["name"], "note": data.get("note") or "",
            "fields": fields, "offers": offers, "can_check_id": can_check}


class ValidateIn(BaseModel):
    fields: dict[str, str] = Field(min_length=1)


@router.post("/topups/{category_id}/check-id")
def check_player_id(category_id: str, data: ValidateIn):
    try:
        if category_id not in _validate_games():
            return {"supported": False}
        r = get_supplier().validate_id(category_id, {k: v.strip() for k, v in data.fields.items()})
    except SupplierError as e:
        if e.status == 422:
            return {"supported": True, "valid": False,
                    "message": "Не удалось подтвердить ID. Проверьте его или напишите в поддержку."}
        raise supplier_http_error(e)
    return {"supported": True, "valid": bool(r.get("valid")), "player_name": r.get("player_name"),
            "region": r.get("region")}


@router.get("/telegram")
def telegram_quotes(db: Session = Depends(get_db)):
    try:
        stars = cache.get("tg_stars", 120, lambda: get_supplier().telegram_stars())
        prem = cache.get("tg_premium", 120, lambda: get_supplier().telegram_premium())
    except SupplierError as e:
        raise supplier_http_error(e)
    markup = get_markup(db)
    per_star = (d(stars["price_per_star"]) * (1 + markup / Decimal(100))).quantize(
        Decimal("0.0000001"), rounding=ROUND_CEILING)
    return {
        "stars": {"price_per_star": f"{per_star}", "min": stars["min_amount"], "max": stars["max_amount"]},
        "premium": [{"months": p["months"], "price": f"{sell_price(p['price_usd'], markup):.2f}"}
                    for p in prem.get("plans", [])],
    }
