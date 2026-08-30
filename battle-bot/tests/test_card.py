"""Картинка участника для сторис."""
import sys
from io import BytesIO
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handlers import card as handler
from services import card, keyboards
from storage.db import connect
from storage.repo import Repo
from storage.settings import Settings
from tests.test_engine import make_config

LINK = "https://t.me/TestBot?start=v12_345"


@pytest.fixture()
def env(tmp_path):
    path = str(tmp_path / "card.db")
    repo = Repo(connect(path))
    config = make_config(db_path=path, bot_username="TestBot")
    settings = Settings(repo.conn, config)
    settings.bootstrap()
    return repo, config, settings


# ------------------------------------------------------------- имена

def test_emoji_are_dropped_from_a_nickname():
    """DejaVu рисует эмодзи пустыми квадратами — лучше их убрать."""
    assert card.clean("ник🔥🔥") == "ник"
    assert card.clean("👑") == "участник", "пустой ник — не пустая картинка"


def test_a_long_nickname_is_cut():
    assert len(card.clean("а" * 50)) == 20


def test_cyrillic_survives():
    assert card.clean("Алиджон_2006") == "Алиджон_2006"


def test_the_link_loses_the_tail():
    """На картинке важен адрес бота, а не длинный хвост ссылки."""
    assert card.clean_link(LINK) == "t.me/TestBot"


# ------------------------------------------------------------- рисование

def test_the_poster_is_a_story_sized_png():
    from PIL import Image

    data = card.render("alijon", "seady", LINK)
    image = Image.open(BytesIO(data))

    assert image.format == "PNG"
    assert image.size == (card.WIDTH, card.HEIGHT)
    assert card.HEIGHT > card.WIDTH, "сторис вертикальные"


def test_a_very_long_nickname_still_fits():
    """Шрифт подбирается по ширине — постер не должен ломаться о длинный ник."""
    data = card.render("а" * 20, "б" * 20, LINK, prize="Приз финала 1000 звёзд")

    assert len(data) > 1000


def test_drawing_works_without_a_rival():
    assert card.render("alijon", "", LINK)


# ------------------------------------------------------------- обработчик

@pytest.mark.asyncio
async def test_only_your_own_pair_gets_a_poster(env):
    """Чужую пару нарисовать нельзя — картинка именная."""
    repo, config, settings = env
    from datetime import datetime, timedelta

    from core.models import Player

    repo.upsert_user(1, "one", "One")
    repo.upsert_user(2, "two", "Two")
    deadline = datetime.now() + timedelta(hours=2)
    match_id = repo.create_match(
        battle_id=repo.create_battle(deadline), round_no=1, number=1,
        players=[Player(1, "one"), Player(2, "two")], advance=1, is_final=False,
        deadline=deadline,
    )

    image, reason = await handler.draw(repo, config, settings, match_id, 999)
    assert image is None and "не ваша" in reason

    image, link = await handler.draw(repo, config, settings, match_id, 1)
    assert image and link.endswith("v%s_1" % match_id)


def test_the_prize_comes_from_the_panel(env):
    _, _, settings = env
    settings.set("prizes", ["1000", "500"])
    assert handler.prize_of(settings) == "Приз финала 1000 звёзд"

    settings.set("prizes", ["Телефон", "Наушники"])
    assert handler.prize_of(settings) == "Приз финала: Телефон"

    settings.set("prizes", [])
    assert handler.prize_of(settings) == ""


def test_the_title_can_be_changed(env):
    _, _, settings = env
    settings.set("card_title", "НИКИ ДУШАНБЕ")

    assert handler.title_of(settings) == "НИКИ ДУШАНБЕ"


# ------------------------------------------------------------- кнопка

def test_the_button_appears_only_when_we_can_draw():
    config = make_config(bot_username="TestBot")

    with_card = keyboards.my_match(7, config, None, True, True)
    without = keyboards.my_match(7, config, None, True, False)

    actions = [b.callback_data for row in with_card.inline_keyboard for b in row]
    assert "card:7" in actions
    assert "card:7" not in [
        b.callback_data for row in without.inline_keyboard for b in row
    ]
