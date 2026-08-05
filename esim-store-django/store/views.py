from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from . import cart, catalog, orders, verification
from .forms import ContactForm, ReceiptForm
from .models import Order, validate_receipt_file


def home(request):
    destinations = catalog.get_destinations()[:8]
    return render(request, "store/home.html", {"destinations": destinations})


def destinations_view(request):
    q = request.GET.get("q", "").strip()
    destinations = catalog.get_destinations()
    if q:
        needle = q.lower()
        destinations = [d for d in destinations if needle in d["name"].lower()]
    return render(request, "store/destinations.html", {"destinations": destinations, "q": q})


def destination_detail(request, slug):
    destination = catalog.get_destination(slug)
    if not destination:
        raise Http404("Страна не найдена")
    plans = catalog.get_plans_for_country(slug)
    return render(request, "store/destination.html", {"destination": destination, "plans": plans})


def cart_view(request):
    if request.method == "POST":
        action = request.POST.get("action", "")
        plan_id = request.POST.get("plan_id", "")

        if action == "add" and plan_id:
            if catalog.get_plan_by_id(plan_id):
                cart.add(request, plan_id, 1)
                messages.success(request, "Тариф добавлен в корзину.")
            else:
                messages.error(request, "Этот тариф больше недоступен.")
        elif action == "update" and plan_id:
            try:
                qty = max(0, int(request.POST.get("quantity", 1)))
            except ValueError:
                qty = 1
            cart.update_quantity(request, plan_id, qty)
        elif action == "remove" and plan_id:
            cart.remove(request, plan_id)
            messages.success(request, "Тариф удалён из корзины.")

        return redirect("cart")

    result = cart.items_with_totals(request)
    if result["dirty"]:
        messages.error(request, "Часть тарифов из корзины больше недоступна и была удалена.")
    return render(request, "store/cart.html", {"items": result["items"], "total": result["total"]})


EMPTY_CHECKOUT = {"email": "", "phone": "", "phone_verified": False, "code_sent": False, "demo_code": None}


def checkout_view(request):
    result = cart.items_with_totals(request)
    items, total = result["items"], result["total"]
    if not items:
        messages.error(request, "Сначала добавьте тариф в корзину.")
        return redirect("cart")

    co = request.session.get("checkout") or dict(EMPTY_CHECKOUT)

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "send_code":
            form = ContactForm(request.POST)
            if form.is_valid():
                phone = form.cleaned_data["phone"]
                send_result = verification.send(phone)
                co = {
                    "email": form.cleaned_data["email"],
                    "phone": phone,
                    "phone_verified": False,
                    "code_sent": True,
                    "demo_code": send_result.get("demo_code") if send_result.get("demo") else None,
                }
                messages.success(request, f"Код подтверждения отправлен на {phone}.")
            else:
                for errors in form.errors.values():
                    for e in errors:
                        messages.error(request, e)
            request.session["checkout"] = co
            return redirect("checkout")

        if action == "resend_code" and co.get("phone"):
            send_result = verification.send(co["phone"])
            co["demo_code"] = send_result.get("demo_code") if send_result.get("demo") else None
            messages.success(request, "Код отправлен повторно.")
            request.session["checkout"] = co
            return redirect("checkout")

        if action == "change_contact":
            request.session["checkout"] = dict(EMPTY_CHECKOUT)
            return redirect("checkout")

        if action == "verify_code" and co.get("phone"):
            code = request.POST.get("code", "").strip()
            if verification.check(co["phone"], code):
                co["phone_verified"] = True
                messages.success(request, "Номер телефона подтверждён.")
            else:
                messages.error(request, "Неверный или истёкший код.")
            request.session["checkout"] = co
            return redirect("checkout")

        if action == "submit_order" and co.get("phone_verified"):
            form = ReceiptForm(request.POST, request.FILES)
            if not form.is_valid():
                messages.error(request, "Загрузите скриншот или PDF чека.")
                return redirect("checkout")

            receipt_file = form.cleaned_data["receipt"]
            try:
                validate_receipt_file(receipt_file)
            except Exception as e:
                messages.error(request, str(e))
                return redirect("checkout")

            created_ids = []
            for item in items:
                order = orders.create_order(item["plan"], item["quantity"], co["email"], co["phone"], True)
                receipt_file.seek(0)
                order.receipt.save(receipt_file.name, receipt_file, save=False)
                order.status = Order.Status.PENDING_REVIEW
                order.receipt_uploaded_at = timezone.now()
                order.save()
                created_ids.append(order.public_id)

            cart.clear(request)
            request.session["checkout"] = dict(EMPTY_CHECKOUT)

            first_id = created_ids.pop(0)
            target = reverse("order_status", args=[first_id])
            if created_ids:
                target += "?more=" + ",".join(created_ids)
            return redirect(target)

    request.session["checkout"] = co
    return render(request, "store/checkout.html", {"items": items, "total": total, "co": co})


def order_status(request, public_id):
    more = [i for i in request.GET.get("more", "").split(",") if i]
    ids = [public_id, *more]
    found = list(Order.objects.filter(public_id__in=ids))
    if not found:
        raise Http404("Заказ не найден")
    order_by_id = {o.public_id: o for o in found}
    ordered = [order_by_id[i] for i in ids if i in order_by_id]
    return render(request, "store/order_status.html", {"orders": ordered})
