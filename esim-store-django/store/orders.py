import logging

from . import airalo
from .models import Order

logger = logging.getLogger(__name__)


def create_order(plan: dict, quantity: int, email: str, phone: str, phone_verified: bool) -> Order:
    total = round(plan["price_usd"] * quantity, 2)
    return Order.objects.create(
        status=Order.Status.PENDING_PAYMENT,
        customer_email=email,
        customer_phone=phone,
        phone_verified=phone_verified,
        plan_id=plan["id"],
        plan_title=plan["title"],
        country_name=plan["country_name"],
        country_flag=plan["country_flag"],
        plan_days=plan["days"],
        plan_data=plan["data_amount"],
        price_usd=plan["price_usd"],
        quantity=quantity,
        total_usd=total,
    )


def confirm_and_issue(order: Order) -> dict:
    """Confirms payment and issues the eSIM (real Airalo order when configured,
    a clearly-marked demo eSIM otherwise so the flow stays testable)."""
    order.status = Order.Status.ISSUING
    order.save(update_fields=["status", "updated_at"])

    try:
        if airalo.is_configured():
            esim = airalo.create_order(order.plan_id, order.quantity)
        else:
            esim = airalo.create_demo_order()

        order.status = Order.Status.ISSUED
        order.esim_iccid = esim["iccid"]
        order.esim_qr_url = esim["qr_code_url"]
        order.esim_qr_data = esim["qr_code_data"]
        order.esim_demo = esim["demo"]
        order.save()
        return {"ok": True}
    except Exception as e:
        logger.exception("[airalo] order issuance failed for %s", order.public_id)
        order.status = Order.Status.FAILED
        order.admin_note = f"Airalo error: {e}"
        order.save()
        return {"ok": False, "error": str(e)}


def reject_order(order: Order, note: str = "") -> None:
    order.status = Order.Status.REJECTED
    order.admin_note = note
    order.save()
