import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import Slot
from services import texts

DEADLINE = datetime(2026, 8, 20, 18, 0)


def plain(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


@pytest.mark.parametrize(
    "count,expected",
    [(0, "голосов"), (1, "голос"), (2, "голоса"), (4, "голоса"), (5, "голосов"),
     (11, "голосов"), (21, "голос"), (22, "голоса"), (111, "голосов"), (104, "голоса")],
)
def test_votes_are_declined_correctly(count, expected):
    assert texts.votes_word(count).endswith(expected)


def test_bar_is_proportional():
    assert texts.bar(5, 10, width=10) == "▰▰▰▰▰▱▱▱▱▱"
    assert texts.bar(10, 10, width=10) == "▰" * 10
    assert texts.bar(0, 10, width=10) == "▱" * 10


def test_bar_without_votes_is_empty():
    assert texts.bar(0, 0, width=6) == "▱" * 6


def test_a_single_vote_still_shows_on_the_bar():
    """Один голос из ста не должен выглядеть как ноль."""
    assert texts.bar(1, 100, width=10).startswith("▰")


def test_bar_always_keeps_its_width():
    for value in range(0, 21):
        assert len(texts.bar(value, 20, width=10)) == 10


def test_scoreboard_marks_the_leader():
    slots = [Slot(1, "a", votes=9), Slot(2, "b", votes=3)]
    board = plain(texts.scoreboard(slots))
    assert "@a" in board and "👑" in board
    assert board.index("👑") < board.index("@b"), "корона должна стоять у лидера"
    assert "75%" in board and "25%" in board


def test_scoreboard_without_votes_has_no_crown():
    board = plain(texts.scoreboard([Slot(1, "a"), Slot(2, "b")]))
    assert "👑" not in board


def test_channel_post_keeps_the_expected_blocks():
    slots = [Slot(1, "mishzzxx"), Slot(2, "enriiqws")]
    post = texts.channel_post(
        1, False, slots, [1000, 500, 250], DEADLINE,
        "https://t.me/b?start=v1", "https://t.me/b?start=join",
    )
    body = plain(post)
    assert "1 Р А У Н Д" in body
    assert "У Ч А С Т Н И К И" in body
    assert "@mishzzxx" in body and "@enriiqws" in body
    assert "Итоги в 18:00 МСК" in body
    assert 'href="https://t.me/b?start=v1"' in post
    assert 'href="https://t.me/b?start=join"' in post


def test_final_results_show_medals_in_order():
    ranking = [Slot(1, "a", 40, 1), Slot(2, "b", 20, 2), Slot(3, "c", 10, 3)]
    body = plain(texts.channel_result(3, True, ranking, tie_broken=False))
    assert body.index("🥇") < body.index("🥈") < body.index("🥉")


def test_round_results_mark_winner_and_losers():
    ranking = [Slot(1, "a", 9, 1), Slot(2, "b", 2, 2)]
    body = plain(texts.channel_result(1, False, ranking, tie_broken=False))
    assert "✅" in body and "❌" in body


def test_a_coin_flip_is_announced():
    ranking = [Slot(1, "a", 5, 1), Slot(2, "b", 5, 2)]
    body = plain(texts.channel_result(1, False, ranking, tie_broken=True))
    assert "жребием" in body


def test_nicknames_are_escaped():
    """Ник из Telegram попадает в HTML — угловые скобки должны экранироваться."""
    assert texts.nick("<b>hack</b>") == "@&lt;b&gt;hack&lt;/b&gt;"


def test_voting_screen_shows_the_total():
    slots = [Slot(1, "a", 3), Slot(2, "b", 4)]
    body = plain(texts.voting_screen(2, False, slots, DEADLINE))
    assert "Всего: 7 голосов" in body
    assert "2 раунд" in body


def test_profile_of_a_newcomer_has_no_empty_holes():
    body = plain(texts.profile(None, None, 0))
    assert "без username" in body
    assert "—" in body  # лучшее место ещё не заработано


def test_empty_leaderboard_is_not_an_error():
    assert "Пока пусто" in plain(texts.leaderboard([]))


def test_button_colors_use_only_values_telegram_accepts():
    """Bot API принимает лишь primary / success / danger — иначе отклонит запрос."""
    from services import keyboards

    allowed = {"primary", "success", "danger"}
    assert {keyboards.BLUE, keyboards.GREEN, keyboards.RED} == allowed


def vote_buttons(markup):
    return [
        b
        for row in markup.inline_keyboard
        for b in row
        if b.callback_data and b.callback_data.startswith("vote:")
    ]


def test_only_the_leader_button_is_green():
    from services import keyboards
    from tests.test_engine import make_config

    slots = [Slot(1, "a", votes=3), Slot(2, "b", votes=1), Slot(3, "c", votes=0)]
    markup = keyboards.voting(7, slots, make_config(), post_url=None)

    leader, second, third = vote_buttons(markup)
    assert leader.style == keyboards.GREEN, "у кого больше голосов — тот зелёный"
    assert second.style is None
    assert third.style is None


def test_nobody_is_green_before_the_first_vote():
    from services import keyboards
    from tests.test_engine import make_config

    slots = [Slot(1, "a", votes=0), Slot(2, "b", votes=0)]
    markup = keyboards.voting(7, slots, make_config(), post_url=None)

    assert all(b.style is None for b in vote_buttons(markup))


def test_a_tie_lights_up_both_leaders():
    from services import keyboards
    from tests.test_engine import make_config

    slots = [Slot(1, "a", votes=2), Slot(2, "b", votes=2), Slot(3, "c", votes=1)]
    markup = keyboards.voting(7, slots, make_config(), post_url=None)

    first, second, third = vote_buttons(markup)
    assert first.style == second.style == keyboards.GREEN
    assert third.style is None


def test_service_buttons_stay_blue():
    from services import keyboards
    from tests.test_engine import make_config

    config = make_config()
    slots = [Slot(1, "a", votes=3), Slot(2, "b", votes=1)]
    markup = keyboards.voting(7, slots, config, post_url="https://t.me/c/1/2")

    buttons = [b for row in markup.inline_keyboard for b in row]
    service = [b for b in buttons if b not in vote_buttons(markup)]

    assert service and all(b.style == keyboards.BLUE for b in service)


def test_main_menu_highlights_the_primary_action():
    from services import keyboards
    from tests.test_engine import make_config

    menu = keyboards.main_menu(make_config())
    buttons = [b for row in menu.keyboard for b in row]
    join = next(b for b in buttons if "Принять участие" in b.text)

    assert join.style == keyboards.BLUE
    assert [b for b in buttons if b.style is None], "остальные кнопки обычного цвета"


# --- HTML собирается вручную, поэтому проверяем его целостность автоматически

SELF_CLOSING: set[str] = set()


def assert_html_is_valid(html: str) -> None:
    """Теги должны быть парными и правильно вложенными — иначе Telegram
    отклонит сообщение целиком."""
    stack: list[str] = []
    for raw in re.findall(r"<[^>]+>", html):
        name = re.sub(r"[<>/]", "", raw).split()[0].lower()
        if name in SELF_CLOSING:
            continue
        if raw.startswith("</"):
            assert stack, f"закрывающий </{name}> без открывающего в: {html[:120]}"
            opened = stack.pop()
            assert opened == name, f"</{name}> закрывает <{opened}> в: {html[:120]}"
        else:
            stack.append(name)
    assert not stack, f"не закрыты теги {stack} в: {html[:120]}"


def all_messages() -> list[str]:
    slots = [Slot(1, "mishzzxx", 12, 1), Slot(2, "enriiqws", 7, 2)]
    row = {"user_id": 1, "username": "a", "titles": 2, "wins": 5, "battles": 3}
    stats = {"battles": 3, "wins": 5, "titles": 2, "best_place": 1}
    return [
        texts.channel_post(1, False, slots, [1000, 500, 250], DEADLINE, "u1", "u2"),
        texts.channel_result(1, False, slots, tie_broken=False),
        texts.channel_result(3, True, slots, tie_broken=True),
        texts.round_announcement(2, False, 8, 2, DEADLINE),
        texts.round_announcement(3, True, 4, 1, DEADLINE),
        texts.postponed(2, 4, DEADLINE),
        texts.final_announcement(slots, [1000, 500]),
        texts.voting_screen(1, False, slots, DEADLINE),
        texts.welcome("https://t.me/test"),
        texts.pair_published("rival", "https://t.me/b?start=v1"),
        texts.advanced("https://t.me/b?start=v1"),
        texts.took_place(1, 1000),
        texts.profile("nick", stats, 4),
        texts.profile(None, None, 0),
        texts.leaderboard([row]),
        texts.leaderboard([]),
        texts.scoreboard(slots),
        texts.HELP,
        texts.APPLICATION_ACCEPTED,
        texts.IN_QUEUE,
        texts.match_result_dm(slots, 2, 1, False, False, False),
        texts.match_result_dm(slots, 1, 0, True, True, True),
        texts.BYE_ROUND,
        texts.NEED_USERNAME,
        texts.ALREADY_IN_BATTLE,
        texts.NO_ACTIVE_BATTLE,
    ]


@pytest.mark.parametrize("message", all_messages())
def test_every_message_has_valid_html(message):
    assert_html_is_valid(message)


@pytest.mark.parametrize("message", all_messages())
def test_no_message_is_empty_or_too_long(message):
    assert message.strip(), "пустое сообщение Telegram не примет"
    assert len(message) <= 4096, "предел одного сообщения Telegram"


def test_the_bar_is_never_wrapped_in_bold():
    """Шкала идёт моноширинной — жирный ломает выравнивание символов."""
    slots = [Slot(1, "a", 3), Slot(2, "b", 1)]
    board = texts.scoreboard(slots)
    assert "<b><code>" not in board and "<code><b>" not in board


def test_key_numbers_are_highlighted():
    slots = [Slot(1, "a", 3), Slot(2, "b", 1)]
    board = texts.scoreboard(slots)
    assert "<b>3 голоса</b>" in board
    assert "<b>75%</b>" in board
