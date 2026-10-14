"""3. Негативные отзывы без ответа, отзывы и вопросы без ответа."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta

from wbm.checks.base import (
    Check,
    CheckOutcome,
    Finding,
    ProductNames,
    register,
    top_products,
)
from wbm.checks.thresholds import Thresholds
from wbm.domain.data import DataBundle, Dataset, Feedback
from wbm.domain.enums import Severity


@register
class UnansweredCheck(Check):
    id = "unanswered"
    title = "Отзывы и вопросы без ответа"
    requires = (Dataset.FEEDBACKS,)
    optional = (Dataset.QUESTIONS, Dataset.PRODUCTS)

    def run(self, data: DataBundle, thresholds: Thresholds) -> CheckOutcome:
        t = thresholds.unanswered
        fresh_after = data.now - timedelta(hours=t.min_age_hours)
        waiting = [f for f in data.feedbacks.rows if not f.answered and f.created_at <= fresh_after]
        negative = [f for f in waiting if f.rating <= t.negative_max_rating]
        other = [f for f in waiting if f.rating > t.negative_max_rating]
        names = ProductNames(data)

        findings: list[Finding] = []
        if negative:
            findings.append(
                self._feedback_finding(
                    negative,
                    names,
                    data,
                    severity=Severity.CRITICAL,
                    title=f"Негативные отзывы без ответа: {len(negative)}",
                    reason=(
                        f"Отзывы с оценкой {t.negative_max_rating} и ниже видят все покупатели. "
                        "Без ответа продавца они отпугивают сильнее."
                    ),
                    recommendation=(
                        "Ответьте на каждый: поблагодарите, признайте проблему, объясните, "
                        "что уже исправили. Начните с самых старых."
                    ),
                )
            )
        if other:
            findings.append(
                self._feedback_finding(
                    other,
                    names,
                    data,
                    severity=Severity.ADVICE,
                    title=f"Отзывы без ответа: {len(other)}",
                    reason="Ответы на положительные отзывы показывают, что продавец на связи.",
                    recommendation="Ответьте коротко и по-человечески — это поддерживает лояльность.",
                )
            )

        message = None
        if data.questions.usable:
            questions = [
                q for q in data.questions.rows if not q.answered and q.created_at <= fresh_after
            ]
            if questions:
                per_product = Counter(q.nm_id for q in questions)
                vendor = {q.nm_id: q.vendor_code for q in questions}
                oldest = min(q.created_at for q in questions)
                findings.append(
                    Finding(
                        severity=Severity.IMPORTANT,
                        title=f"Вопросы покупателей без ответа: {len(questions)}",
                        facts={
                            "вопросов": len(questions),
                            "самому_старому_дней": (data.now - oldest).days,
                        },
                        reason="Вопрос задают до покупки: без ответа покупатель уходит к конкуренту.",
                        recommendation="Ответьте на вопросы — начните с самых старых.",
                        products=top_products(
                            (
                                names.product(nm, vendor[nm], {"вопросов_без_ответа": count})
                                for nm, count in per_product.items()
                            ),
                            key=lambda p: float(p.metrics["вопросов_без_ответа"]),
                            reverse=True,
                        ),
                    )
                )
        else:
            message = "Вопросы покупателей не загрузились — проверены только отзывы."
        return self.outcome(findings, message)

    @staticmethod
    def _feedback_finding(
        feedbacks: list[Feedback],
        names: ProductNames,
        data: DataBundle,
        *,
        severity: Severity,
        title: str,
        reason: str,
        recommendation: str,
    ) -> Finding:
        per_product = Counter(f.nm_id for f in feedbacks)
        vendor = {f.nm_id: f.vendor_code for f in feedbacks}
        oldest = min(f.created_at for f in feedbacks)
        return Finding(
            severity=severity,
            title=title,
            facts={
                "отзывов": len(feedbacks),
                "товаров": len(per_product),
                "самому_старому_дней": (data.now - oldest).days,
            },
            reason=reason,
            recommendation=recommendation,
            products=top_products(
                (
                    names.product(nm, vendor[nm], {"отзывов_без_ответа": count})
                    for nm, count in per_product.items()
                ),
                key=lambda p: float(p.metrics["отзывов_без_ответа"]),
                reverse=True,
            ),
        )
