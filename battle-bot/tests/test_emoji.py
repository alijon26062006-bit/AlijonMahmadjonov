import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.emoji import PremiumEmojiMiddleware, load_table, render

TABLE = {"🏆": "5368324170671202286", "✅": "5210956306952758910"}


def test_plain_emoji_becomes_a_premium_tag():
    assert render("🏆 победа", TABLE) == (
        '<tg-emoji emoji-id="5368324170671202286">🏆</tg-emoji> победа'
    )


def test_without_a_table_the_text_is_untouched():
    assert render("🏆 победа", {}) == "🏆 победа"


def test_unknown_emoji_stays_as_it_is():
    assert render("🍋 призы", TABLE) == "🍋 призы"


def test_html_tags_and_links_survive():
    source = '<b>🏆</b> <a href="https://t.me/x">клик ✅</a>'
    result = render(source, TABLE)
    assert '<a href="https://t.me/x">' in result
    assert result.count("<tg-emoji") == 2
    assert "<b>" in result and "</b>" in result


def test_already_wrapped_emoji_is_not_wrapped_twice():
    source = '<tg-emoji emoji-id="111">🏆</tg-emoji> и ещё 🏆'
    result = render(source, TABLE)
    assert result.count("<tg-emoji") == 2
    assert 'emoji-id="111"' in result  # готовый тег не переписан


def test_every_occurrence_is_replaced():
    assert render("🏆🏆🏆", TABLE).count("<tg-emoji") == 3


def test_table_ignores_empty_and_placeholder_values(tmp_path):
    path = tmp_path / "table.json"
    path.write_text(
        json.dumps({"🏆": "123", "✅": "", "🍋": "  ", "🎁": "<сюда id>"}),
        encoding="utf-8",
    )
    assert load_table(path) == {"🏆": "123"}


def test_missing_file_disables_substitution(tmp_path):
    assert load_table(tmp_path / "нет.json") == {}


def test_broken_file_does_not_crash_the_bot(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{ это не json", encoding="utf-8")
    assert load_table(path) == {}


def test_template_covers_only_emoji_that_can_be_premium():
    """👍 живёт во всплывающем уведомлении — там Telegram премиум не рисует.
    👑 и ⚡ стоят на кнопках, но их можно отдать через icon_custom_emoji_id."""
    template = json.loads(
        (Path(__file__).resolve().parents[1] / "premium_emoji.example.json").read_text(
            encoding="utf-8"
        )
    )
    assert "👍" not in template
    assert "👑" in template and "⚡" in template
    assert "🏆" in template and "⭐" in template
    assert all(value == "" for value in template.values())


class FakeMethod:
    def __init__(self, text: str) -> None:
        self.text = text


@pytest.mark.asyncio
async def test_middleware_rewrites_outgoing_text():
    middleware = PremiumEmojiMiddleware(TABLE)
    method = FakeMethod("🏆 итоги")
    captured = {}

    async def make_request(bot, sent):
        captured["text"] = sent.text
        return "ok"

    assert await middleware(make_request, None, method) == "ok"
    assert "<tg-emoji" in captured["text"]


@pytest.mark.asyncio
async def test_middleware_is_a_noop_without_a_table():
    middleware = PremiumEmojiMiddleware({})
    method = FakeMethod("🏆 итоги")

    async def make_request(bot, sent):
        return sent.text

    assert await middleware(make_request, None, method) == "🏆 итоги"


class FakeSend:
    def __init__(self, chat_id: int, text: str) -> None:
        self.chat_id = chat_id
        self.text = text


@pytest.mark.asyncio
async def test_channel_messages_keep_plain_emoji_by_default():
    """Без Fragment-username Telegram отклонил бы пост с tg-emoji — батл встал бы."""
    middleware = PremiumEmojiMiddleware(TABLE, skip_chats={-1001234567890})
    method = FakeSend(-1001234567890, "🏆 итоги раунда")

    async def make_request(bot, sent):
        return sent.text

    assert await middleware(make_request, None, method) == "🏆 итоги раунда"


@pytest.mark.asyncio
async def test_private_messages_still_get_premium_emoji():
    middleware = PremiumEmojiMiddleware(TABLE, skip_chats={-1001234567890})
    method = FakeSend(12345, "🏆 вы прошли")

    async def make_request(bot, sent):
        return sent.text

    assert "<tg-emoji" in await make_request_result(middleware, make_request, method)


async def make_request_result(middleware, make_request, method):
    return await middleware(make_request, None, method)


def test_leading_emoji_moves_to_the_button_icon():
    from services.emoji import leading_emoji

    assert leading_emoji("🏆 Победа", TABLE) == ("Победа", TABLE["🏆"])


def test_leading_emoji_leaves_unknown_symbols_in_place():
    from services.emoji import leading_emoji

    assert leading_emoji("🍋 Призы", TABLE) == ("🍋 Призы", None)
    assert leading_emoji("Обновить", TABLE) == ("Обновить", None)


def test_collect_ids_reads_custom_emoji_from_a_message():
    from aiogram.types import MessageEntity
    from services.emoji import collect_ids

    # смещения Telegram считает в единицах UTF-16: 🏆 занимает две, ⭐ — одну
    entities = [
        MessageEntity(type="custom_emoji", offset=0, length=2, custom_emoji_id="555"),
        MessageEntity(type="bold", offset=3, length=6),
        MessageEntity(type="custom_emoji", offset=10, length=1, custom_emoji_id="666"),
    ]
    assert collect_ids("🏆 жирный ⭐", entities) == {"🏆": "555", "⭐": "666"}


def test_collect_ids_on_a_message_without_premium_emoji():
    from services.emoji import collect_ids

    assert collect_ids("обычный текст 🏆", None) == {}
    assert collect_ids(None, []) == {}


def test_saved_table_can_be_read_back(tmp_path):
    from services.emoji import load_table, save_table

    path = tmp_path / "sub" / "table.json"
    save_table(path, {"🏆": "555", "⭐": "666"})
    assert load_table(path) == {"🏆": "555", "⭐": "666"}


def test_shipped_table_matches_the_template():
    """premium_emoji.json не должен разъезжаться с шаблоном и со списком мест."""
    root = Path(__file__).resolve().parents[1]
    table = json.loads((root / "premium_emoji.json").read_text(encoding="utf-8"))
    template = json.loads((root / "premium_emoji.example.json").read_text(encoding="utf-8"))

    assert set(table) == set(template), "набор символов разошёлся с шаблоном"

    filled = {char: value for char, value in table.items() if value}
    assert len(filled) == 22
    assert all(value.isdigit() for value in filled.values()), "ID должны быть числовыми"
    assert len(set(filled.values())) == len(filled), "один ID не должен стоять дважды"


def test_preview_covers_every_symbol_in_the_table():
    from handlers.emoji import PLACES

    root = Path(__file__).resolve().parents[1]
    table = json.loads((root / "premium_emoji.json").read_text(encoding="utf-8"))
    places = dict(PLACES)

    assert set(places) == set(table), "предпросмотр и таблица должны совпадать"
    assert len(PLACES) == len(places), "в предпросмотре есть дубли"


def test_menu_buttons_answer_with_and_without_the_premium_icon():
    """С премиум-иконкой эмодзи уезжает из подписи — фильтр должен ловить оба вида."""
    from services import keyboards

    for label in (
        keyboards.BTN_JOIN,
        keyboards.BTN_INVITE,
        keyboards.BTN_BUY,
        keyboards.BTN_PROFILE,
        keyboards.BTN_HELP,
    ):
        accepted = keyboards.variants(label)
        assert label in accepted, "подпись без премиума"
        assert label[2:] in accepted, "подпись с премиум-иконкой"
        assert len(accepted) == 2


def test_menu_button_labels_lose_the_emoji_when_the_table_has_it(monkeypatch):
    from dataclasses import replace
    from services import keyboards
    from tests.test_engine import make_config

    config = make_config()
    config.premium_emoji = {"🚀": "111", "👤": "222"}
    menu = keyboards.main_menu(config)
    labels = [button.text for row in menu.keyboard for button in row]

    assert "Принять участие" in labels
    assert "Профиль" in labels
    # у символов без ID подпись остаётся прежней
    assert keyboards.BTN_HELP in labels
    # и всё это ловится фильтрами
    for label in labels:
        assert any(
            label in keyboards.variants(known)
            for known in (
                keyboards.BTN_JOIN,
                keyboards.BTN_INVITE,
                keyboards.BTN_BUY,
                keyboards.BTN_CHANNEL,
                keyboards.BTN_PROFILE,
                keyboards.BTN_HELP,
            )
        ), f"кнопка «{label}» не ловится ни одним фильтром"
