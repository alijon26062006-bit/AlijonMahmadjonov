from django.contrib import admin, messages
from django.utils.html import format_html

from . import orders as order_ops
from .models import Order

admin.site.site_header = "EasySIM — Админ-панель"
admin.site.site_title = "EasySIM"
admin.site.index_title = "Заказы"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "public_id", "status", "customer_email", "customer_phone",
        "country_display", "plan_title", "total_usd", "created_at",
    )
    list_filter = ("status", "esim_demo")
    search_fields = ("public_id", "customer_email", "customer_phone")
    ordering = ("-created_at",)

    readonly_fields = (
        "public_id", "created_at", "updated_at",
        "customer_email", "customer_phone", "phone_verified",
        "plan_id", "plan_title", "country_name", "country_flag", "plan_days", "plan_data",
        "price_usd", "quantity", "total_usd",
        "receipt_preview", "receipt_uploaded_at",
        "esim_iccid", "esim_qr_url", "esim_qr_data", "esim_demo",
    )
    fields = (
        "public_id", "status", "created_at", "updated_at",
        "customer_email", "customer_phone", "phone_verified",
        "country_flag", "country_name", "plan_title", "plan_data", "plan_days",
        "price_usd", "quantity", "total_usd",
        "receipt_preview", "receipt_uploaded_at",
        "esim_iccid", "esim_qr_url", "esim_qr_data", "esim_demo",
        "admin_note",
    )
    actions = ["confirm_and_issue_action", "reject_action"]

    @admin.display(description="Страна")
    def country_display(self, obj):
        return f"{obj.country_flag} {obj.country_name}"

    @admin.display(description="Чек об оплате")
    def receipt_preview(self, obj):
        if not obj.receipt:
            return "—"
        url = obj.receipt.url
        if url.lower().endswith(".pdf"):
            return format_html('<a href="{}" target="_blank" rel="noopener">Открыть PDF-чек →</a>', url)
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">'
            '<img src="{}" style="max-width:320px;max-height:320px;border-radius:8px;border:1px solid #ddd;">'
            "</a>",
            url, url,
        )

    @admin.action(description="Подтвердить и выдать eSIM")
    def confirm_and_issue_action(self, request, queryset):
        ok = fail = 0
        for order in queryset:
            if order.status not in (Order.Status.PENDING_REVIEW, Order.Status.FAILED):
                continue
            result = order_ops.confirm_and_issue(order)
            ok += 1 if result["ok"] else 0
            fail += 0 if result["ok"] else 1
        if ok:
            self.message_user(request, f"eSIM выдан для {ok} заказ(ов).", level=messages.SUCCESS)
        if fail:
            self.message_user(
                request, f"Не удалось выдать eSIM для {fail} заказ(ов) — см. поле «Заметка».",
                level=messages.ERROR,
            )

    @admin.action(description="Отклонить оплату")
    def reject_action(self, request, queryset):
        count = 0
        for order in queryset:
            if order.status != Order.Status.PENDING_REVIEW:
                continue
            order_ops.reject_order(order, note="Отклонено администратором")
            count += 1
        self.message_user(request, f"Отклонено заказов: {count}.", level=messages.SUCCESS)
