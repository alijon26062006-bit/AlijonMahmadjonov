"""4. Частые жалобы в отзывах: размер, цвет, качество и др. — группировка по темам."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from wbm.checks.base import (
    AffectedProduct,
    Check,
    CheckOutcome,
    Finding,
    ProductNames,
    in_range,
    percent,
    period_bounds,
    register,
    top_products,
)
from wbm.checks.thresholds import Thresholds
from wbm.domain.data import DataBundle, Dataset, Feedback
from wbm.domain.enums import Severity


@dataclass(frozen=True, slots=True)
class Topic:
    key: str
    title: str
    patterns: tuple[str, ...]
    advice: str

    def matches(self, text: str) -> bool:
        return any(re.search(pattern, text) for pattern in self.patterns)


# Корни слов в нижнем регистре, «ё» заменена на «е». Словарь легко расширять.
TOPICS: tuple[Topic, ...] = (
    Topic(
        "size",
        "Размер",
        (
            r"маломер",
            r"большемер",
            r"\bразмер\w*\s+(не\s+)?(подош|соответств|мал|велик|не\s+тот)",
            r"\bмал(енький|а|о)?\b.*\bразмер",
            r"не\s+(подош[её]л|подошл)\w*\s+по\s+размеру",
            r"\bвелик(о|а|оват)",
            r"\bмаловат",
            r"сетк\w*\s+размер",
        ),
        "Уточните размерную сетку и замеры в карточке, добавьте подсказку «берите на размер больше/меньше».",
    ),
    Topic(
        "color",
        "Цвет",
        (
            r"\bцвет\w*\s+(не\s+)?(соответств|отлича|другой|не\s+тот|не\s+как)",
            r"\bоттен\w*",
            r"\bдругого\s+цвета",
            r"цвет\w*.{0,20}на\s+фото",
        ),
        "Переснимите фото при дневном свете, укажите точный оттенок в описании.",
    ),
    Topic(
        "quality",
        "Качество и брак",
        (
            r"\bбрак\w*",
            r"\bпорвал",
            r"\bразошел\w*\s+шов",
            r"\bнитк\w*\s+торч",
            r"\bкачеств\w*\s+(плох|ужас|низк|отврат|не\s+очень)",
            r"\bплох\w*\s+качеств",
            r"\bсломал",
            r"\bдырк",
            r"\bпятн",
            r"\bкатышк",
            r"\bразвалил",
        ),
        "Проверьте партию у поставщика и упаковку; ответьте покупателям и предложите замену.",
    ),
    Topic(
        "description",
        "Не соответствует описанию или фото",
        (
            r"не\s+соответству\w*\s+(описани|фото|картинк)",
            r"на\s+фото\s+(совсем\s+)?друг",
            r"\bобман",
            r"не\s+то[,.!\s]+что\s+заказыва",
        ),
        "Сверьте фото и описание с реальным товаром, уберите обещания, которых нет.",
    ),
    Topic(
        "smell",
        "Запах",
        (r"\bзапах\w*", r"\bвоня", r"\bпахн\w*\s+(химие|резин|ужас|неприят)"),
        "Проверьте материал у поставщика; добавьте в карточку совет проветрить или постирать.",
    ),
    Topic(
        "packaging",
        "Упаковка и комплектация",
        (
            r"\bупаков\w*\s+(порван|мят|повреж|плох|грязн)",
            r"\bпомят",
            r"\bгрязн\w*",
            r"\bне\s+хватал\w*",
            r"\bнекомплект",
            r"\bпришл\w*\s+не\s+(все|то)",
        ),
        "Проверьте упаковку и комплектацию при отгрузке.",
    ),
)


def normalize_text(text: str) -> str:
    return text.lower().replace("ё", "е")


@register
class ComplaintsCheck(Check):
    id = "complaints"
    title = "Частые жалобы в отзывах"
    requires = (Dataset.FEEDBACKS,)
    optional = (Dataset.PRODUCTS,)

    def run(self, data: DataBundle, thresholds: Thresholds) -> CheckOutcome:
        t = thresholds.complaints
        bounds = period_bounds(data)
        by_product: defaultdict[int, list[Feedback]] = defaultdict(list)
        for feedback in data.feedbacks.rows:
            if in_range(feedback.created_at, bounds):
                by_product[feedback.nm_id].append(feedback)

        names = ProductNames(data)
        hits: defaultdict[Topic, list[AffectedProduct]] = defaultdict(list)
        severities: dict[Topic, Severity] = {}
        for nm_id, feedbacks in by_product.items():
            texts = [normalize_text(f.full_text) for f in feedbacks]
            for topic in TOPICS:
                mentions = sum(1 for text in texts if topic.matches(text))
                share = mentions / len(feedbacks)
                if mentions < t.min_mentions or share < t.min_share:
                    continue
                metrics: dict[str, int | float | str] = {
                    "отзывов_за_период": len(feedbacks),
                    "упоминаний": mentions,
                    "доля_процентов": percent(share),
                }
                hits[topic].append(names.product(nm_id, feedbacks[0].vendor_code, metrics))
                if share >= t.critical_share:
                    severities[topic] = Severity.IMPORTANT

        findings = [
            Finding(
                severity=severities.get(topic, Severity.ADVICE),
                title=f"Жалобы на тему «{topic.title}»",
                facts={
                    "товаров": len(products),
                    "упоминаний_всего": sum(int(p.metrics["упоминаний"]) for p in products),
                    "дней_в_периоде": data.period_days,
                },
                reason=(
                    "Покупатели повторяют одну и ту же претензию в отзывах — "
                    "это снижает рейтинг и конверсию карточки."
                ),
                recommendation=topic.advice,
                products=top_products(
                    products, key=lambda p: float(p.metrics["доля_процентов"]), reverse=True
                ),
            )
            for topic, products in hits.items()
        ]
        return self.outcome(findings)
