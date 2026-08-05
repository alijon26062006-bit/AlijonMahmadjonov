import logging
import secrets

from django.conf import settings
from django.utils import timezone

from . import zadarma
from .models import VerificationCode

logger = logging.getLogger(__name__)


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def send(phone: str) -> dict:
    """Generates + stores a code and sends it via Zadarma SMS. Falls back to a
    visible "demo code" when Zadarma isn't configured or the send fails, so
    checkout always stays usable while credentials aren't set yet."""
    code = generate_code()
    expires_at = timezone.now() + timezone.timedelta(minutes=5)

    VerificationCode.objects.filter(phone=phone).delete()
    VerificationCode.objects.create(phone=phone, code=code, expires_at=expires_at, attempts=0)

    if not zadarma.is_configured():
        return {"ok": True, "demo": True, "demo_code": code}

    try:
        zadarma.send_sms(phone, f"Код подтверждения {settings.SITE_NAME}: {code}")
        return {"ok": True, "demo": False}
    except Exception:
        logger.exception("[zadarma] sms send failed")
        return {"ok": True, "demo": True, "demo_code": code, "warning": "sms_send_failed"}


def check(phone: str, code: str) -> bool:
    try:
        row = VerificationCode.objects.get(phone=phone)
    except VerificationCode.DoesNotExist:
        return False

    if row.expires_at < timezone.now():
        row.delete()
        return False

    if row.attempts >= 5:
        return False

    row.attempts += 1
    row.save(update_fields=["attempts"])

    if not secrets.compare_digest(row.code, code):
        return False

    row.delete()
    return True
