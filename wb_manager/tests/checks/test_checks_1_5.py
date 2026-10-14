"""Проверки 1–5 на фиктивных данных."""

from __future__ import annotations

from tests.checks.factory import (
    bundle,
    feedback,
    nm_ids,
    only,
    orders,
    orders_between,
    product,
    question,
    sales,
    stock,
)
from wbm.checks.c01_stock_out import StockOutCheck
from wbm.checks.c02_orders_drop import OrdersDropCheck
from wbm.checks.c03_unanswered import UnansweredCheck
from wbm.checks.c04_complaints import ComplaintsCheck
from wbm.checks.c05_returns import ReturnsCheck
from wbm.checks.thresholds import Thresholds
from wbm.domain.enums import CheckStatus, Severity

T = Thresholds()

# ── 1. Товар закончился или скоро закончится ──────────────────────────────────


def test_stock_out_levels() -> None:
    data = bundle(
        # 28 заказов за 14 дней = 2 в день
        orders=orders(1, 28, days_ago=13)
        + orders(2, 28, days_ago=13)
        + orders(3, 28, days_ago=13)
        + orders(4, 28, days_ago=13),
        stocks=[stock(1, 0), stock(2, 10), stock(3, 20), stock(4, 100)],
        products=[product(1, title="Платье красное")],
    )

    outcome = StockOutCheck().run(data, T)

    assert outcome.status is CheckStatus.PROBLEMS
    critical = only(outcome, Severity.CRITICAL)
    ended = next(f for f in critical if "Закончились" in f.title)
    assert nm_ids(ended) == [1]
    assert ended.products[0].name == "Платье красное"
    assert ended.products[0].metrics["заказов_в_день"] == 2.0
    assert ended.products[0].metrics["выручка_в_день_под_угрозой_руб"] == 2000.0
    soon = next(f for f in critical if "Закончатся" in f.title)
    assert nm_ids(soon) == [2]
    assert soon.products[0].metrics["дней_запаса"] == 5.0
    assert nm_ids(only(outcome, Severity.IMPORTANT)[0]) == [3]


def test_stock_out_ignores_cancelled_old_and_slow_orders() -> None:
    data = bundle(
        orders=orders(1, 10, days_ago=13, cancelled=10)  # все отменены
        + orders_between(2, 30, start_days_ago=40, end_days_ago=20)  # давно
        + orders(3, 1, days_ago=10),  # 1 заказ за 14 дней — медленно
        stocks=[stock(1, 1), stock(2, 1), stock(3, 1)],
    )

    assert StockOutCheck().run(data, T).status is CheckStatus.OK


def test_stock_out_sums_warehouses() -> None:
    data = bundle(
        orders=orders(1, 28, days_ago=13),
        stocks=[stock(1, 10, "Коледино"), stock(1, 10, "Казань")],
    )

    outcome = StockOutCheck().run(data, T)

    # 20 шт. на двух складах при 2 заказах в день — 10 дней запаса.
    assert only(outcome, Severity.IMPORTANT)[0].products[0].metrics["остаток_шт"] == 20


def test_stock_out_empty_data() -> None:
    assert StockOutCheck().run(bundle(orders=[], stocks=[]), T).status is CheckStatus.OK


# ── 2. Падение заказов ────────────────────────────────────────────────────────


def test_orders_drop_per_product_and_shop() -> None:
    data = bundle(
        orders=orders_between(1, 20, start_days_ago=60, end_days_ago=30)
        + orders(1, 8, days_ago=29)  # −60 %
        + orders_between(2, 20, start_days_ago=60, end_days_ago=30)
        + orders(2, 13, days_ago=29)  # −35 %
        + orders_between(3, 5, start_days_ago=60, end_days_ago=30),  # мало для выводов
        stocks=[stock(1, 0)],
    )

    outcome = OrdersDropCheck().run(data, T)

    critical = only(outcome, Severity.CRITICAL)
    shop = next(f for f in critical if "магазина" in f.title)
    assert shop.facts["падение_процентов"] == 53.3  # 45 → 21
    product_critical = next(f for f in critical if f is not shop)
    assert nm_ids(product_critical) == [1]
    assert product_critical.products[0].metrics["остаток_шт"] == 0
    assert nm_ids(only(outcome, Severity.IMPORTANT)[0]) == [2]


def test_orders_growth_is_fine() -> None:
    data = bundle(
        orders=orders_between(1, 20, start_days_ago=60, end_days_ago=30)
        + orders(1, 30, days_ago=29)
    )

    assert OrdersDropCheck().run(data, T).status is CheckStatus.OK


# ── 3. Отзывы и вопросы без ответа ────────────────────────────────────────────


def test_unanswered_feedbacks_and_questions() -> None:
    data = bundle(
        feedbacks=[
            feedback(1, 1, "Ужасно", days_ago=10),
            feedback(1, 3, "Так себе"),
            feedback(2, 2, "Плохо", answered=True),
            feedback(2, 5, "Отлично"),
        ],
        questions=[question(1), question(1), question(2, answered=True)],
    )

    outcome = UnansweredCheck().run(data, T)

    negative = only(outcome, Severity.CRITICAL)[0]
    assert negative.facts == {"отзывов": 2, "товаров": 1, "самому_старому_дней": 10}
    assert only(outcome, Severity.ADVICE)[0].facts["отзывов"] == 1
    questions = only(outcome, Severity.IMPORTANT)[0]
    assert questions.facts["вопросов"] == 2
    assert questions.products[0].metrics["вопросов_без_ответа"] == 2
    assert outcome.message is None


def test_unanswered_without_questions_data() -> None:
    from wbm.domain.data import DataResult

    data = bundle(feedbacks=[feedback(1, 5, answered=True)], questions=DataResult.error("HTTP 403"))

    outcome = UnansweredCheck().run(data, T)

    assert outcome.status is CheckStatus.OK
    assert outcome.message is not None
    assert "Вопросы" in outcome.message


# ── 4. Частые жалобы ──────────────────────────────────────────────────────────


def test_complaints_grouped_by_topic() -> None:
    data = bundle(
        feedbacks=[
            feedback(1, 2, "Маломерит на размер"),
            feedback(1, 3, "", cons="маломерка, берите больше"),
            feedback(1, 2, "Сильно маломерит"),
            feedback(1, 5, "Всё отлично"),
            feedback(1, 4, "Хорошее"),
            feedback(2, 1, "Брак, шов разошелся"),
            feedback(2, 5, "Супер"),
        ],
    )

    outcome = ComplaintsCheck().run(data, T)

    size = next(f for f in outcome.findings if "Размер" in f.title)
    assert size.severity is Severity.IMPORTANT  # 3 из 5 = 60 % ≥ 30 %
    assert size.products[0].metrics == {
        "отзывов_за_период": 5,
        "упоминаний": 3,
        "доля_процентов": 60.0,
    }
    assert all("Качество" not in f.title for f in outcome.findings)  # 1 упоминание < 3


def test_complaints_ignore_old_feedbacks_and_handle_yo() -> None:
    old = [feedback(1, 1, "Брак", days_ago=60) for _ in range(5)]
    fresh = [feedback(2, 1, "Пришёл с браком, всё порвалось") for _ in range(3)]

    outcome = ComplaintsCheck().run(bundle(feedbacks=old + fresh), T)

    assert [nm_ids(f) for f in outcome.findings] == [[2]]


# ── 5. Возвраты и отмены ──────────────────────────────────────────────────────


def test_cancels_and_returns_above_threshold_and_shop_average() -> None:
    data = bundle(
        orders=orders(1, 20, days_ago=10, cancelled=12)  # 60 % — критично
        + orders(2, 20, days_ago=10, cancelled=7)  # 35 % — важно
        + orders(3, 80, days_ago=10, cancelled=2)  # средняя по магазину ~17,5 %
        + orders(4, 5, days_ago=10, cancelled=5),  # мало заказов
        sales=sales(1, 20, returns=2) + sales(2, 20, returns=8) + sales(3, 40, returns=2),
    )

    outcome = ReturnsCheck().run(data, T)

    cancel_findings = [f for f in outcome.findings if "отмен" in f.title]
    assert {f.severity: nm_ids(f) for f in cancel_findings} == {
        Severity.CRITICAL: [1],
        Severity.IMPORTANT: [2],
    }
    returns = next(f for f in outcome.findings if "возвратов" in f.title)
    assert nm_ids(returns) == [2]
    assert returns.products[0].metrics["доля_процентов"] == 40.0


def test_returns_without_sales_data() -> None:
    outcome = ReturnsCheck().run(bundle(orders=orders(1, 20, days_ago=5)), T)

    assert outcome.status is CheckStatus.OK
    assert outcome.message is not None


def test_rate_must_also_exceed_shop_average() -> None:
    # У всех товаров много отмен (35 %) — это особенность магазина, а не одного товара.
    data = bundle(
        orders=orders(1, 20, days_ago=10, cancelled=7) + orders(2, 20, days_ago=10, cancelled=7)
    )

    assert ReturnsCheck().run(data, T).status is CheckStatus.OK
