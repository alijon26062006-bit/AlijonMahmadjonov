"""Подбор соперника: близкие по рейтингу, но никто не ждёт вечно."""

from duel import matchmaking as mm
from duel.matchmaking import Queue, Ticket, make_match


def ticket(user_id, rating=1000, duration=60, level="normal", joined_at=0.0):
    return Ticket(
        user_id=user_id,
        name=f"Игрок {user_id}",
        rating=rating,
        duration=duration,
        level=level,
        joined_at=joined_at,
    )


def test_two_equals_are_matched_at_once():
    queue = Queue()
    queue.add(ticket(1, 1000))
    queue.add(ticket(2, 1030))
    pairs = queue.find_pairs(0.1)
    assert len(pairs) == 1
    assert {t.user_id for t in pairs[0]} == {1, 2}
    assert len(queue) == 0


def test_a_lone_player_keeps_waiting():
    queue = Queue()
    queue.add(ticket(1))
    assert queue.find_pairs(0.1) == []
    assert len(queue) == 1


def test_far_apart_ratings_do_not_meet_right_away():
    queue = Queue()
    queue.add(ticket(1, 800))
    queue.add(ticket(2, 1800))
    assert queue.find_pairs(0.1) == []


def test_waiting_widens_the_search():
    """Тот, кто ждёт долго, соглашается на более сильного соперника."""
    queue = Queue()
    queue.add(ticket(1, 800))
    queue.add(ticket(2, 1800))
    assert len(queue.find_pairs(30.0)) == 1


def test_different_durations_are_not_mixed_at_first():
    queue = Queue()
    queue.add(ticket(1, duration=30))
    queue.add(ticket(2, duration=300))
    assert queue.find_pairs(1.0) == []


def test_level_stops_mattering_after_a_while():
    queue = Queue()
    queue.add(ticket(1, level="easy"))
    queue.add(ticket(2, level="hard"))
    assert queue.find_pairs(1.0) == []
    assert len(queue.find_pairs(mm.FLEX_LEVEL_SEC + 1)) == 1


def test_after_long_wait_any_opponent_will_do():
    queue = Queue()
    queue.add(ticket(1, duration=30, level="easy"))
    queue.add(ticket(2, duration=300, level="hard"))
    assert len(queue.find_pairs(mm.FLEX_ANY_SEC + 1)) == 1


def test_the_closest_by_rating_are_paired_first():
    queue = Queue()
    for user_id, rating in ((1, 1000), (2, 1010), (3, 1600), (4, 1610)):
        queue.add(ticket(user_id, rating))
    pairs = queue.find_pairs(0.1)
    assert {frozenset(t.user_id for t in pair) for pair in pairs} == {
        frozenset({1, 2}),
        frozenset({3, 4}),
    }


def test_entering_twice_replaces_the_old_ticket():
    queue = Queue()
    queue.add(ticket(1, duration=30))
    queue.add(ticket(1, duration=300))
    assert len(queue) == 1
    assert queue.tickets[1].duration == 300


def test_leaving_the_queue_works():
    queue = Queue()
    queue.add(ticket(1))
    queue.remove(1)
    assert len(queue) == 0


def test_odd_player_out_stays_in_the_queue():
    queue = Queue()
    for user_id in (1, 2, 3):
        queue.add(ticket(user_id, 1000 + user_id))
    queue.find_pairs(0.1)
    assert len(queue) == 1


def test_room_lets_a_friend_in_by_code():
    queue = Queue()
    room = queue.create_room(ticket(1), 0.0)
    assert len(room.code) == mm.ROOM_CODE_LEN
    pair = queue.join_room(room.code, ticket(2))
    assert pair is not None and {t.user_id for t in pair} == {1, 2}
    assert queue.join_room(room.code, ticket(3)) is None, "код одноразовый"


def test_peeking_at_a_room_does_not_take_it():
    queue = Queue()
    room = queue.create_room(ticket(1), 0.0)
    assert queue.find_room(room.code) is room
    assert queue.find_room(room.code.lower()) is room
    assert queue.find_room("НЕТУ") is None
    assert queue.join_room(room.code, ticket(2)) is not None, "комната осталась свободной"


def test_room_code_is_case_insensitive():
    queue = Queue()
    room = queue.create_room(ticket(1), 0.0)
    assert queue.join_room(room.code.lower(), ticket(2)) is not None


def test_you_cannot_play_against_yourself():
    queue = Queue()
    room = queue.create_room(ticket(1), 0.0)
    assert queue.join_room(room.code, ticket(1)) is None


def test_wrong_code_returns_nothing():
    assert Queue().join_room("НЕТУ", ticket(2)) is None


def test_empty_rooms_are_swept_away():
    queue = Queue()
    queue.create_room(ticket(1), 0.0)
    assert queue.sweep_rooms(mm.ROOM_TTL_SEC - 1) == []
    assert len(queue.sweep_rooms(mm.ROOM_TTL_SEC + 1)) == 1
    assert queue.rooms == {}


def test_match_takes_settings_from_whoever_waited_longer():
    match = make_match(
        ticket(1, duration=300, level="hard", joined_at=0.0),
        ticket(2, duration=30, level="hard", joined_at=10.0),
        now=11.0,
    )
    assert match.duration == 300


def test_auto_level_yields_to_a_chosen_one():
    """Один выбрал сложность, другой отдал на усмотрение — играем по выбранной."""
    match = make_match(
        ticket(1, level="auto", joined_at=0.0),
        ticket(2, level="easy", joined_at=5.0),
        now=6.0,
    )
    assert match.level == "easy"


def test_a_fresh_match_starts_with_a_countdown():
    match = make_match(ticket(1), ticket(2), now=5.0)
    assert match.state == "countdown"
    assert match.starts_at > 5.0
    assert match.rope() == 0
