"""Бот: кнопки и тексты.

Главное здесь — где именно живёт кнопка запуска игры. Ошибка в этом месте
не видна ни в коде, ни в тестах логики: бот работает, приложение открывается,
и только на телефоне выясняется, что игра не знает, кто зашёл.
"""

import pytest

from duel import bot as bot_module
from duel import storage
from duel.i18n import LANGS, t

URL = "https://duel.example.com/"


@pytest.fixture
def db(tmp_path):
    connection = storage.connect(tmp_path / "duel.sqlite3")
    yield connection
    connection.close()


# ── откуда запускается игра ─────────────────────────────────────────────────


@pytest.mark.parametrize("lang", LANGS)
def test_game_starts_from_a_button_under_the_message(lang):
    """Только у такой кнопки Telegram передаёт в приложение данные об игроке."""
    markup = bot_module.play_keyboard(lang, URL)
    launchers = [b for row in markup.inline_keyboard for b in row if b.web_app]
    assert len(launchers) == 1
    assert launchers[0].web_app.url == URL
    assert launchers[0].text == t("bot.play", lang)


@pytest.mark.parametrize("lang", LANGS)
def test_bottom_keyboard_never_launches_the_game(lang):
    """У кнопки нижней клавиатуры initData приходит пустой — игра не узнает
    игрока. На настоящем телефоне это и случилось: «Открой игру из Telegram»."""
    markup = bot_module.main_keyboard(lang)
    for row in markup.keyboard:
        for button in row:
            assert button.web_app is None, f"кнопка «{button.text}» открывает игру"


def test_invite_link_reaches_the_game_as_a_room_code():
    """Ссылка-приглашение должна донести код комнаты внутрь приложения."""
    markup = bot_module.play_keyboard("ru", f"{URL}?tgWebAppStartParam=ABC123")
    launcher = next(b for row in markup.inline_keyboard for b in row if b.web_app)
    assert "tgWebAppStartParam=ABC123" in launcher.web_app.url


def test_other_buttons_answer_without_opening_the_game():
    markup = bot_module.play_keyboard("ru", URL)
    actions = {b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data}
    assert actions == {"duel:top", "duel:me", "duel:rules", "duel:langs"}


# ── тексты ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("lang", LANGS)
def test_leaderboard_says_when_nobody_played(db, lang):
    assert bot_module.top_text(db, lang) == t("bot.top.empty", lang)


def test_leaderboard_shows_places_and_ratings(db):
    for user_id, name, score in ((1, "Алиджон", 1300), (2, "Соперник", 1100)):
        storage.touch_player(db, user_id, name)
        storage.apply_result(
            db, user_id, "rope", new_rating=score, outcome="win", correct=5, wrong=1, best_streak=3
        )
    text = bot_module.top_text(db, "ru")
    assert "🥇 Алиджон — 1300" in text
    assert "🥈 Соперник — 1100" in text


def test_profile_before_the_first_match(db):
    storage.touch_player(db, 1, "Алиджон")
    text = bot_module._profile_of(db, 1, "ru")
    assert "Алиджон" in text
    assert "Матчей ещё не было" in text


def test_profile_after_a_match(db):
    storage.touch_player(db, 1, "Алиджон")
    storage.apply_result(
        db, 1, "rope", new_rating=1250, outcome="win", correct=12, wrong=2, best_streak=6
    )
    text = bot_module._profile_of(db, 1, "ru")
    assert "1250" in text and "мастер" in text
    assert "Место: 1" in text
    assert "лучшая серия: 6" in text


def test_profile_speaks_tajik_too(db):
    storage.touch_player(db, 1, "Алиджон")
    storage.apply_result(
        db, 1, "rope", new_rating=1250, outcome="win", correct=12, wrong=2, best_streak=6
    )
    text = bot_module._profile_of(db, 1, "tg")
    assert "Ҷой: 1" in text
    assert "устод" in text, "звание тоже должно быть на таджикском"


def test_unknown_player_gets_an_empty_profile(db):
    assert "—" in bot_module._profile_of(db, 999, "ru")


def test_profile_keeps_each_game_apart(db):
    """Рейтинг морского боя не смешивается с канатом."""
    storage.touch_player(db, 1, "Алиджон")
    storage.apply_result(
        db, 1, "sea", new_rating=1310, outcome="win", correct=9, wrong=0, best_streak=9
    )
    text = bot_module._profile_of(db, 1, "ru")
    assert "Морской бой" in text and "1310" in text
    assert "Канат\nЕщё не играл" in text


def test_leaderboard_has_a_section_per_game(db):
    storage.touch_player(db, 1, "Алиджон")
    storage.touch_player(db, 2, "Соперник")
    storage.apply_result(db, 1, "rope", new_rating=1200, outcome="win", correct=5, wrong=1, best_streak=3)
    storage.apply_result(db, 2, "sea", new_rating=1150, outcome="win", correct=5, wrong=1, best_streak=3)
    text = bot_module.top_text(db, "ru")
    rope, sea = text.split("Морской бой")
    assert "🥇 Алиджон — 1200" in rope and "Соперник" not in rope
    assert "🥇 Соперник — 1150" in sea and "Алиджон" not in sea


@pytest.mark.parametrize(
    "text, game",
    [
        ("/duel", "rope"),
        ("/duel@KanatBot", "rope"),
        ("/duel море", "sea"),
        ("/duel sea", "sea"),
        ("/duel@KanatBot морской бой", "sea"),
        ("/duel канат", "rope"),
        ("/duel баҳрӣ", "sea"),
        ("/duel что-то", "rope"),
    ],
)
def test_duel_command_understands_the_game(text, game):
    assert bot_module.game_from_text(text) == game
