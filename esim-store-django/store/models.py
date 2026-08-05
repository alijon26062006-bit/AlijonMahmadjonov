import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


def generate_public_id() -> str:
    return secrets.token_hex(5).upper()


def receipt_upload_path(instance: "Order", filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"receipts/{instance.public_id}.{ext}"


def validate_receipt_file(file) -> None:
    max_bytes = settings.MAX_RECEIPT_SIZE_MB * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(f"Файл слишком большой (макс. {settings.MAX_RECEIPT_SIZE_MB} МБ).")

    file.seek(0)
    header = file.read(32)
    file.seek(0)

    is_jpeg = header.startswith(b"\xff\xd8\xff")
    is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = header[0:4] == b"RIFF" and header[8:12] == b"WEBP"
    is_pdf = header.startswith(b"%PDF")

    if not (is_jpeg or is_png or is_webp or is_pdf):
        raise ValidationError("Допустимы только изображения (JPG/PNG/WEBP) или PDF.")


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Ожидает оплаты"
        PENDING_REVIEW = "pending_review", "Чек на проверке"
        ISSUING = "issuing", "Выдаём eSIM…"
        ISSUED = "issued", "eSIM выдан"
        REJECTED = "rejected", "Оплата отклонена"
        FAILED = "failed", "Ошибка выдачи"

    public_id = models.CharField(max_length=20, unique=True, default=generate_public_id, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING_PAYMENT)

    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=32)
    phone_verified = models.BooleanField(default=False)

    plan_id = models.CharField(max_length=64)
    plan_title = models.CharField(max_length=190)
    country_name = models.CharField(max_length=120)
    country_flag = models.CharField(max_length=16)
    plan_days = models.PositiveIntegerField()
    plan_data = models.CharField(max_length=32)
    price_usd = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    total_usd = models.DecimalField(max_digits=10, decimal_places=2)

    receipt = models.FileField(
        upload_to=receipt_upload_path, blank=True, null=True, validators=[validate_receipt_file]
    )
    receipt_uploaded_at = models.DateTimeField(blank=True, null=True)

    esim_iccid = models.CharField(max_length=64, blank=True, null=True)
    esim_qr_url = models.URLField(max_length=500, blank=True, null=True)
    esim_qr_data = models.CharField(max_length=255, blank=True, null=True)
    esim_demo = models.BooleanField(default=False)

    admin_note = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Заказ #{self.public_id}"

    def get_absolute_url(self) -> str:
        return reverse("order_status", args=[self.public_id])

    @property
    def status_badge_class(self) -> str:
        return {
            self.Status.PENDING_PAYMENT: "badge-pending",
            self.Status.PENDING_REVIEW: "badge-pending",
            self.Status.ISSUING: "badge-info",
            self.Status.ISSUED: "badge-success",
            self.Status.REJECTED: "badge-danger",
            self.Status.FAILED: "badge-danger",
        }.get(self.status, "badge-pending")


class VerificationCode(models.Model):
    phone = models.CharField(max_length=32, unique=True)
    code = models.CharField(max_length=10)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return self.phone
