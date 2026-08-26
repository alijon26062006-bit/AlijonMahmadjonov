"""Оформление: настраиваемые значки, разметка Telegram, история с возвратами."""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import env_fixture  # noqa: F401

from app import db, emoji, keyboards, runtime, texts
from app.handlers import profile as prof_h

PASS, FAIL = [], []

# Что Telegram понимает в режиме HTML.
ALLOWED_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "a", "code",
    "pre", "blockquote", "span", "tg-spoiler", "tg-emoji",
}
TAG_RE = re.compile(r"</?([a-zA-Z-]+)")


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"  — {detail}" if detail else ""))


class FakeUser:
    def __init__(self, uid=321, username="buyer", first_name="Покупатель"):
        self.id, self.username, self.first_name = uid, username, first_name


class FakeMessage:
    def __init__(self, user=None):
        self.from_user = user or FakeUser()
        self.replies: list[str] = []

    async def answer(self, text, **kw):
        self.replies.append(text)
        return self

    async def edit_text(self, text, **kw):
        self.replies.append(text)
        return self

    @property
    def last(self):
        return self.replies[-1] if self.replies else ""


class FakeCallback:
    def __init__(self, data, user=None):
        self.data = data
        self.from_user = user or FakeUser()
        self.message = FakeMessage(self.from_user)

    async def answer(self, text="", **kw):
        return None

    @property
    def last(self):
        return self.message.last


def all_templates() -> dict[str, str]:
    return {name: getattr(texts, name) for name in texts._RAW}


async def main() -> None:
    for sfx in ("", "-wal", "-shm"):
        Path(str(db.settings.db_file) + sfx).unlink(missing_ok=True)
    conn = await db.connect()
    try:
        await db.init(conn)
        await runtime.load(conn)
        await run(conn)
    finally:
        await conn.close()
    print(f"\n{'=' * 52}\nПройдено: {len(PASS)}   Провалено: {len(FAIL)}")
    if FAIL:
        print("ПРОВАЛЫ:", ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)


async def run(conn) -> None:
    templates = all_templates()

    # ------------------------------------------- разметка валидна для Telegram
    bad_tags = {}
    for name, text in templates.items():
        tags = {t.lower() for t in TAG_RE.findall(text)} - ALLOWED_TAGS
        if tags:
            bad_tags[name] = tags
    check("во всех текстах только теги, понятные Telegram", not bad_tags, str(bad_tags))

    unbalanced = []
    for name, text in templates.items():
        for tag in ("b", "i", "code", "blockquote"):
            if text.count(f"<{tag}>") + text.count(f"<{tag} ") != text.count(f"</{tag}>"):
                unbalanced.append(f"{name}:{tag}")
    check("теги парные, ничего не забыто", not unbalanced, str(unbalanced))

    leftovers = {n: t for n, t in templates.items() if "[[" in t or "]]" in t}
    check("незакрытых токенов значков не осталось", not leftovers, str(list(leftovers)))

    quoted = [n for n, t in templates.items() if "<blockquote" in t]
    check("цитаты используются в оформлении", len(quoted) >= 15, f"{len(quoted)} экранов")

    # ------------------------------------------------ значки настраиваются
    check("значков в реестре достаточно", len(emoji.DEFAULTS) >= 25,
          str(len(emoji.DEFAULTS)))
    check("по умолчанию Premium — корона", emoji.em("premium") == "👑")

    await runtime.set_value(conn, "emoji_premium", "💎")
    check("значок меняется", emoji.em("premium") == "💎")
    check("текст сразу подхватывает новый значок",
          "💎" in texts.PREMIUM_ENTRY, texts.PREMIUM_ENTRY[:40])
    labels = [b.text for row in keyboards.main_menu().inline_keyboard for b in row]
    check("кнопка сразу подхватывает новый значок",
          any("💎" in t for t in labels), str(labels))

    runtime._cache.clear()
    await runtime.load(conn)
    check("новый значок пережил перезапуск", emoji.em("premium") == "💎")

    await runtime.reset(conn, "emoji_premium")
    check("сброс возвращает значок по умолчанию", emoji.em("premium") == "👑")

    check("слова значком не считаются", not emoji.is_emoji_like("привет"))
    check("длинная строка значком не считается", not emoji.is_emoji_like("⭐️⭐️⭐️⭐️⭐️"))
    check("символ подходит как значок", emoji.is_emoji_like("•"))

    # ---------------------------------------- история показывает возвраты
    await db.upsert_user(conn, 321, "buyer", "Покупатель")
    await db.credit(conn, 321, 100000)

    done = await db.create_order(conn, user_id=321, product_type="stars",
                                 quantity=100, recipient="friend", price=2000)
    await db.update_order(conn, done.id, status=db.ORDER_DELIVERED)
    lost = await db.create_order(conn, user_id=321, product_type="premium",
                                 quantity=3, recipient="other", price=13000)
    await db.update_order(conn, lost.id, status=db.ORDER_REFUNDED)

    call = FakeCallback("p:history")
    await prof_h.cb_history(call, conn)
    text = call.last

    check("история показывает сводку по заказам",
          "Выполнено: <b>1</b>" in text and "Возвращено: <b>1</b>" in text,
          text.replace("\n", " ")[:150])
    check("видно, сколько всего потрачено", "20.00" in text)
    check("у возврата написано, что деньги вернулись",
          "вернулись на баланс" in text, text.replace("\n", " ")[-160:])
    check("у выполненного написано, что списано", "Списано:" in text)
    check("получатель показан у каждого заказа",
          "@friend" in text and "@other" in text)
    check("статусы понятны человеку",
          "Выполнен" in text and "Деньги возвращены" in text)

    # Пустая история тоже объясняет, что тут будет
    await db.upsert_user(conn, 322, "new", "Новичок")
    call = FakeCallback("p:history", FakeUser(322, "new", "Новичок"))
    await prof_h.cb_history(call, conn)
    check("пустая история объясняет, что появится",
          "Пока пусто" in call.last and "<blockquote>" in call.last)

    # ------------------------------------------- заголовки и разделители
    with_rule = [n for n, t in templates.items() if texts.LINE in t]
    check("на экранах есть разделители", len(with_rule) >= 15, f"{len(with_rule)}")

    check("в меню есть жирный заголовок", "<b>" in texts.MENU)
    check("в информации свёрнутый блок с вопросами",
          "<blockquote expandable>" in texts.INFO)


asyncio.run(main())
