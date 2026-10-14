"""Тексты бота (HTML-разметка Telegram). Всё, что пришло от пользователя или из WB, экранируем."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from wbm.db.models import AnalysisRun, CheckResult, Finding
from wbm.domain.enums import SEVERITY_TITLES, CheckStatus, Severity
from wbm.wb_client import CATEGORIES, Category

TOP_PROBLEMS = 5
_ICONS = {Severity.CRITICAL: "🔴", Severity.IMPORTANT: "🟠", Severity.ADVICE: "🔵"}

REQUIRED_CATEGORIES: tuple[Category, ...] = (
    Category.CONTENT,
    Category.ANALYTICS,
    Category.PRICES,
    Category.STATISTICS,
    Category.PROMOTION,
    Category.FEEDBACKS,
    Category.FINANCE,
)
OPTIONAL_CATEGORIES: tuple[Category, ...] = (Category.MARKETPLACE,)

WELCOME = (
    "👋 Здравствуйте! Я AI-менеджер для продавцов Wildberries.\n\n"
    "Я проверяю магазин и показываю, что не так: какие товары скоро закончатся, "
    "где падают заказы, какие отзывы ждут ответа, что продаётся в минус и куда "
    "уходят деньги на рекламу и удержания.\n\n"
    "<b>Я ничего не меняю в магазине — только читаю данные.</b>\n\n"
    "Чтобы начать, поделитесь номером телефона — кнопка внизу."
)

ASK_PHONE = "Нажмите кнопку «📱 Поделиться номером» внизу экрана."

ALIEN_CONTACT = "Пришлите, пожалуйста, свой номер — кнопкой «📱 Поделиться номером»."

PHONE_SAVED = "✅ Номер сохранён."


def token_instructions() -> str:
    sections = ", ".join(CATEGORIES[c].title for c in REQUIRED_CATEGORIES)
    return (
        "<b>Подключите магазин — нужен токен WB.</b>\n\n"
        "1. Личный кабинет WB → «Интеграции по API» → «+ Создать токен».\n"
        "2. Вкладка «Ручная интеграция», тип — <b>Персональный</b>.\n"
        f"3. Разделы: {escape(sections)}.\n"
        "   Если торгуете со своего склада — добавьте «Маркетплейс».\n"
        "4. Уровень доступа — <b>Только чтение</b>.\n"
        "5. «Создать» → «Копировать и закрыть».\n\n"
        "Пришлите токен сюда одним сообщением. 🔒 Я сразу удалю сообщение, а токен "
        "сохраню только в зашифрованном виде."
    )


HELP = (
    "<b>Команды</b>\n"
    "/analyze — проанализировать магазин\n"
    "/history — прошлые анализы и отчёты PDF\n"
    "/shops — магазины: выбрать или удалить\n"
    "/token — как подключить магазин\n"
    "/costs — как загрузить себестоимость\n\n"
    "Новый токен — просто пришлите его сообщением."
)

COSTS_HELP = (
    "<b>Себестоимость</b> нужна, чтобы найти товары, которые продаются в минус.\n\n"
    "Пришлите файл Excel (.xlsx) или CSV из двух колонок:\n"
    "<code>артикул; себестоимость</code>\n"
    "Например: <code>PLATYE-01; 850</code>\n\n"
    "Артикул — ваш артикул продавца, как в карточке WB. Новый файл заменяет старый."
)

DELETED_NOTICE = "🔒 Сообщение с токеном удалено. Проверяю токен в WB…"

GROUP_WARNING = (
    "⚠️ Не присылайте токен в группы — его видят все участники. "
    "Удалите этот токен в кабинете WB и создайте новый. Пишите мне в личные сообщения."
)

NO_SHOP = "Сначала подключите магазин — пришлите токен WB. Как его создать: /token"

NEED_PHONE_FIRST = (
    "Сначала поделитесь номером телефона — кнопка «📱 Поделиться номером». "
    "Токен я не сохранил — пришлите его ещё раз после этого."
)


def category_report(available: Sequence[str], warnings: Sequence[str]) -> str:
    have = set(available)
    lines = []
    for category in (*REQUIRED_CATEGORIES, *OPTIONAL_CATEGORIES):
        title = escape(CATEGORIES[category].title)
        if category.value in have:
            lines.append(f"✅ {title}")
        elif category in REQUIRED_CATEGORIES:
            lines.append(f"❌ {title} — нет доступа, часть проверок будет без данных")
        else:
            lines.append(f"▫️ {title} — не подключено (нужно только для своего склада)")
    text = "\n".join(lines)
    if warnings:
        text += "\n\n" + "\n".join(f"⚠️ {escape(w)}" for w in warnings)
    return text


def shop_connected(
    shop_name: str, available: Sequence[str], warnings: Sequence[str], *, updated: bool
) -> str:
    action = "Токен обновлён" if updated else "Магазин подключён"
    return (
        f"✅ <b>{action}: {escape(shop_name)}</b>\n\n"
        f"{category_report(available, warnings)}\n\n"
        "Дальше: пришлите файл себестоимости (/costs) или сразу запускайте /analyze."
    )


def progress_text(shop_name: str, percent: int, stage: str) -> str:
    filled = max(0, min(10, percent // 10))
    bar = "▓" * filled + "░" * (10 - filled)
    return f"⏳ Анализ «{escape(shop_name)}»\n{bar} {percent}%\n{escape(stage)}"


def _sorted_findings(checks: Sequence[CheckResult]) -> list[Finding]:
    order = {Severity.CRITICAL: 0, Severity.IMPORTANT: 1, Severity.ADVICE: 2}
    items = [(c.position, f) for c in checks for f in c.findings]
    items.sort(key=lambda p: (order.get(Severity(p[1].severity), 3), p[0], p[1].position))
    return [f for _, f in items]


def _shorten(text: str, limit: int = 350) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def run_summary(run: AnalysisRun, shop_name: str) -> str:
    """Итог анализа для Telegram: счётчики, топ-5 проблем, что не проверено."""
    findings = _sorted_findings(run.checks)
    counts = {s: sum(1 for f in findings if f.severity == s) for s in Severity}
    lines = [f"📊 <b>Анализ «{escape(shop_name)}» готов</b>"]
    summary_text = (run.summary or {}).get("summary_text")
    if isinstance(summary_text, str) and summary_text:
        lines += ["", escape(_shorten(summary_text, 600))]
    if findings:
        lines += [
            "",
            f"🔴 Критично: {counts[Severity.CRITICAL]}   "
            f"🟠 Важно: {counts[Severity.IMPORTANT]}   🔵 Советы: {counts[Severity.ADVICE]}",
            "",
            f"<b>Главное ({min(TOP_PROBLEMS, len(findings))} из {len(findings)}):</b>",
        ]
        for number, finding in enumerate(findings[:TOP_PROBLEMS], start=1):
            severity = Severity(finding.severity)
            text = finding.text or f"{finding.reason} {finding.recommendation}"
            lines += [
                "",
                f"{number}. {_ICONS[severity]} <b>{escape(finding.title)}</b>",
                escape(_shorten(text)),
            ]
    else:
        lines += ["", "✅ Проблем по проверкам с данными не найдено."]

    skipped = [
        c
        for c in run.checks
        if c.status in (CheckStatus.NO_DATA, CheckStatus.NEEDS_COST, CheckStatus.ERROR)
    ]
    if skipped:
        lines += ["", f"▫️ Не проверено: {len(skipped)} из {len(run.checks)} — подробности в PDF."]
        if any(c.status == CheckStatus.NEEDS_COST for c in run.checks):
            lines.append("💡 Загрузите себестоимость (/costs), чтобы найти товары в минус.")
    lines += ["", "📎 Полный отчёт — в файле ниже."]
    return "\n".join(lines)


def severity_title(severity: str) -> str:
    return SEVERITY_TITLES[Severity(severity)]


def run_failed(shop_name: str, reason: str) -> str:
    return f"❌ Анализ «{escape(shop_name)}» не получился.\n{escape(reason)}\n\nПопробуйте ещё раз: /analyze"
