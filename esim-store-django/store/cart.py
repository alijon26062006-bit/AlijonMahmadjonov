from . import catalog


def get_cart(request) -> dict:
    return request.session.get("cart", {})


def add(request, plan_id: str, quantity: int = 1) -> None:
    cart = request.session.get("cart", {})
    if plan_id in cart:
        cart[plan_id]["quantity"] = cart[plan_id].get("quantity", 1) + quantity
    else:
        cart[plan_id] = {"quantity": quantity}
    request.session["cart"] = cart
    request.session.modified = True


def remove(request, plan_id: str) -> None:
    cart = request.session.get("cart", {})
    cart.pop(plan_id, None)
    request.session["cart"] = cart
    request.session.modified = True


def update_quantity(request, plan_id: str, quantity: int) -> None:
    cart = request.session.get("cart", {})
    if quantity <= 0:
        cart.pop(plan_id, None)
    else:
        cart.setdefault(plan_id, {})["quantity"] = quantity
    request.session["cart"] = cart
    request.session.modified = True


def clear(request) -> None:
    request.session["cart"] = {}
    request.session.modified = True


def count(request) -> int:
    return sum(int(item.get("quantity", 0)) for item in get_cart(request).values())


def items_with_totals(request) -> dict:
    items = []
    total = 0.0
    dirty = False
    cart = get_cart(request)

    for plan_id, entry in list(cart.items()):
        plan = catalog.get_plan_by_id(plan_id)
        if not plan:
            cart.pop(plan_id, None)
            dirty = True
            continue
        qty = int(entry.get("quantity", 1))
        subtotal = round(plan["price_usd"] * qty, 2)
        items.append({"plan": plan, "quantity": qty, "subtotal": subtotal})
        total += subtotal

    if dirty:
        request.session["cart"] = cart
        request.session.modified = True

    return {"items": items, "total": round(total, 2), "dirty": dirty}
