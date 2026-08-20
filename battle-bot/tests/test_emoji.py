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
    """👑 и 👍 живут на кнопке и во всплывашке — Telegram их не заменит."""
    template = json.loads(
        (Path(__file__).resolve().parents[1] / "premium_emoji.example.json").read_text(
            encoding="utf-8"
        )
    )
    assert "👑" not in template
    assert "👍" not in template
    assert "⚡" not in template
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
