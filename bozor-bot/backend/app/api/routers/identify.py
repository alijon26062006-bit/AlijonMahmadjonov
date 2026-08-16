"""Проверка номеров для веб-формы: VIN и IMEI.

Форма вызывает ручку сразу после ввода номера и подставляет то, что вернулось.
Ответ всегда 200: «не узнали» — это не ошибка, а обычный исход. Ошибкой
считается только неверный сам номер (не сошлась контрольная сумма).
"""
from fastapi import APIRouter

from app.api.deps import Cache, Db
from app.services import identifiers, tac_service, vin_decoder

router = APIRouter(prefix="/api/identify", tags=["identify"])


@router.get("/vin/{raw}")
async def identify_vin(raw: str, redis: Cache):
    ok, value, err, auto = identifiers.validate("vin_or_frame", raw[:32])
    if not ok:
        return {"ok": False, "error": err}

    out = {"ok": True, "value": value, "known": False,
           "brand_hint": auto.get("brand_hint"), "year": auto.get("year")}
    info = await vin_decoder.decode(value, redis)
    if info:
        out["known"] = True
        out["summary"] = vin_decoder.summary(info)
        out["fill"] = {k: info[k] for k in ("make", "model", "year") if info.get(k)}
        out["details"] = info
    return out


@router.get("/imei/{raw}")
async def identify_imei(raw: str, session: Db):
    ok, value, err, auto = identifiers.validate("imei", raw[:32])
    if not ok:
        return {"ok": False, "error": err}

    out = {"ok": True, "value": value, "tac": auto.get("tac"), "known": False}
    found = await tac_service.lookup(session, value)
    if found:
        out["known"] = True
        out["summary"] = f'{found["brand"]} {found["model"]}'
        out["fill"] = {"brand": found["brand"], "model": found["model"]}
    return out
