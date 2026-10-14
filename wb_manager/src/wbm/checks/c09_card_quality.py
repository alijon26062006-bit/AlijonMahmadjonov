"""9. Карточки с ошибками, пустыми характеристиками, коротким описанием, малым числом фото."""

from __future__ import annotations

from collections.abc import Callable

from wbm.checks.base import (
    AffectedProduct,
    Check,
    CheckOutcome,
    Finding,
    ProductNames,
    percent,
    plural,
    register,
    top_products,
)
from wbm.checks.thresholds import Thresholds
from wbm.domain.data import DataBundle, Dataset, Product
from wbm.domain.enums import Severity


def _is_empty(value: str | None) -> bool:
    return value is None or not value.strip()


@register
class CardQualityCheck(Check):
    id = "card_quality"
    title = "Ошибки и пробелы в карточках"
    requires = (Dataset.PRODUCTS,)
    optional = (Dataset.CARD_ERRORS,)

    def run(self, data: DataBundle, thresholds: Thresholds) -> CheckOutcome:
        t = thresholds.card_quality
        names = ProductNames(data)
        findings: list[Finding] = []

        if data.card_errors.usable and data.card_errors.rows:
            items = [
                AffectedProduct(
                    nm_id=e.nm_id,
                    vendor_code=e.vendor_code,
                    metrics={"ошибки": "; ".join(e.errors)[:500]},
                )
                for e in data.card_errors.rows
            ]
            findings.append(
                Finding(
                    severity=Severity.CRITICAL,
                    title=f"WB не принял карточки: {plural(len(items), 'карточка', 'карточки', 'карточек')}",
                    facts={"карточек": len(items)},
                    reason="WB вернул ошибки по этим карточкам — товар может не продаваться.",
                    recommendation="Исправьте ошибки в карточках по тексту WB.",
                    products=top_products(items, key=lambda p: p.vendor_code or ""),
                )
            )

        required_empty: list[AffectedProduct] = []
        many_empty: list[AffectedProduct] = []
        short_description: list[AffectedProduct] = []
        few_photos: list[AffectedProduct] = []
        for product in data.products.rows:
            ref = self._with(names, product)
            missing_required = [
                c.name for c in product.characteristics if c.required and _is_empty(c.value)
            ]
            if missing_required:
                required_empty.append(
                    ref({"пустые_обязательные": ", ".join(missing_required)[:300]})
                )
            if product.characteristics:
                empty = sum(1 for c in product.characteristics if _is_empty(c.value))
                share = empty / len(product.characteristics)
                if share >= t.empty_characteristics_share:
                    many_empty.append(
                        ref(
                            {
                                "заполнено": len(product.characteristics) - empty,
                                "всего_характеристик": len(product.characteristics),
                                "пустых_процентов": percent(share),
                            }
                        )
                    )
            length = len((product.description or "").strip())
            if length < t.min_description_length:
                short_description.append(ref({"символов_в_описании": length}))
            if product.photos < t.min_photos:
                few_photos.append(ref({"фото": product.photos}))

        groups: tuple[
            tuple[list[AffectedProduct], Severity, str, str, str, dict[str, int | float]], ...
        ] = (
            (
                required_empty,
                Severity.IMPORTANT,
                "Не заполнены обязательные характеристики",
                "Без обязательных характеристик карточка хуже находится в поиске и фильтрах.",
                "Заполните обязательные характеристики в карточке.",
                {},
            ),
            (
                many_empty,
                Severity.ADVICE,
                "Много пустых характеристик",
                "Покупатели ищут товар через фильтры: пустая характеристика — товар не попадает в выдачу.",
                "Заполните характеристики, особенно те, по которым фильтруют (размер, цвет, состав).",
                {"порог_пустых_процентов": percent(t.empty_characteristics_share)},
            ),
            (
                short_description,
                Severity.ADVICE,
                "Короткое описание",
                "Короткое описание хуже ранжируется и не отвечает на вопросы покупателя.",
                "Допишите описание: материал, размеры, уход, для кого и для чего товар.",
                {"порог_символов": t.min_description_length},
            ),
            (
                few_photos,
                Severity.ADVICE,
                "Мало фото",
                "Покупатель не может рассмотреть товар — конверсия ниже.",
                "Добавьте фото с разных сторон, детали, товар на человеке или в интерьере.",
                {"минимум_фото": t.min_photos},
            ),
        )
        for items, severity, title, reason, advice, extra in groups:
            if not items:
                continue
            findings.append(
                Finding(
                    severity=severity,
                    title=f"{title}: {plural(len(items), 'карточка', 'карточки', 'карточек')}",
                    facts={"карточек": len(items), **extra},
                    reason=reason,
                    recommendation=advice,
                    products=top_products(items, key=lambda p: p.vendor_code or ""),
                )
            )
        message = None
        if not data.card_errors.usable:
            message = "Список ошибок карточек от WB не загрузился — проверено только заполнение."
        return self.outcome(findings, message)

    @staticmethod
    def _with(
        names: ProductNames, product: Product
    ) -> Callable[[dict[str, int | float | str]], AffectedProduct]:
        def build(metrics: dict[str, int | float | str]) -> AffectedProduct:
            return names.product(product.nm_id, product.vendor_code, metrics)

        return build
