from django.conf import settings


def site_settings(request):
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "SUPPORT_PHONE": settings.SUPPORT_PHONE,
        "ZADARMA_WIDGET_KEY": settings.ZADARMA_WIDGET_KEY,
        "PAYMENT_INSTRUCTIONS": settings.PAYMENT_INSTRUCTIONS,
        "MAX_RECEIPT_SIZE_MB": settings.MAX_RECEIPT_SIZE_MB,
        "cart_count": sum(item.get("quantity", 0) for item in request.session.get("cart", {}).values()),
    }
