from decimal import Decimal

from bot.services import CalcResult


def fmt_num(value) -> str:
    d = Decimal(str(value)).normalize()
    text = f"{d:f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def render_calc_result(r: CalcResult) -> str:
    lines = [
        "🧮 <b>Результат расчёта</b>",
        "",
        f"🚚 Тип доставки: <b>{r.delivery_type}</b>",
        f"🗂 Категория: <b>{r.category.name if r.category else '-'}</b>",
        f"📋 Тариф: <b>{r.tariff.name}</b>",
        f"💵 Стоимость за кг: <b>{fmt_num(r.price_per_kg)} {r.currency_code}</b>",
        f"⚖️ Вес: <b>{fmt_num(r.weight)} кг</b>",
    ]
    if r.volume > 0:
        lines.append(f"📐 Объём: <b>{fmt_num(r.volume)} м³</b> "
                     f"(объёмный вес: {fmt_num(r.volumetric_weight)} кг)")
    if r.chargeable_weight != r.weight:
        lines.append(f"🏋️ Оплачиваемый вес: <b>{fmt_num(r.chargeable_weight)} кг</b>")
    lines.append(f"💰 Базовая стоимость: <b>{fmt_num(r.base_cost)} {r.currency_code}</b>")
    if r.min_order_applied:
        lines.append("ℹ️ Применена минимальная стоимость заказа.")
    for name, amount in r.lines:
        sign = "−" if amount < 0 else "+"
        lines.append(f"{'🎁' if amount < 0 else '➕'} {name}: "
                     f"{sign}{fmt_num(abs(amount))} {r.currency_code}")
    lines.append("")
    lines.append(f"✅ <b>Итого: {fmt_num(r.total)} {r.currency_code}</b>")
    if r.total_tjs:
        lines.append(f"≈ {fmt_num(r.total_tjs)} TJS (по текущему курсу)")
    if r.delivery_time:
        lines.append(f"🕓 Срок доставки: <b>{r.delivery_time}</b>")
    return "\n".join(lines)


def parse_number(text: str) -> float | None:
    try:
        value = float(text.replace(",", ".").strip())
        return value if value >= 0 else None
    except (ValueError, AttributeError):
        return None
