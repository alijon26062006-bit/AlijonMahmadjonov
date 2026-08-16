"""Сделки: ответы покупателя и продавца на вопрос «вы договорились?»."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser, Db
from app.services import deal_service

router = APIRouter(prefix="/api/deals", tags=["deals"])


class Answer(BaseModel):
    agreed: bool


@router.post("/{deal_id}/buyer")
async def buyer_answer(deal_id: int, body: Answer, session: Db, user: CurrentUser):
    deal = await deal_service.buyer_answer(session, deal_id, user, body.agreed)
    if deal is None:
        raise HTTPException(404, "not_found")
    if body.agreed:
        # спрашиваем продавца в боте — ответ придёт кнопкой
        from app.workers.queue import enqueue_ask_seller
        await enqueue_ask_seller(deal.id)
    return {"status": deal.status}


@router.post("/{deal_id}/seller")
async def seller_answer(deal_id: int, body: Answer, session: Db, user: CurrentUser):
    result = await deal_service.seller_answer(session, deal_id, user, body.agreed)
    if result is None:
        raise HTTPException(404, "not_found")
    deal, listing = result
    return {"status": deal.status, "listing_status": listing.status}


@router.get("/mine")
async def my_pending(session: Db, user: CurrentUser):
    """Сделки, ждущие слова продавца, — для карточки в приложении."""
    deals = await deal_service.pending_for_seller(session, user)
    return {"items": [{"id": d.id, "listing_id": d.listing_id} for d in deals]}
