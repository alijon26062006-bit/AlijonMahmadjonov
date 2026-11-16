"""Гонка мини-приложения: комнаты, боты из зерна, честный финиш, монеты с лимитом, магазин цветов."""

import time

import pytest

from donatix import race


@pytest.fixture
def uid(conn):
    from conftest import make_client
    return make_client(conn)[0]


def test_rnd_matches_js_formula():
    # те же числа даёт формула в tg_race.html (Math.imul) — боты одинаковые у всех
    assert 0 <= race.rnd(12345, 0) < 1 and race.rnd(12345, 0) != race.rnd(12345, 1)
    assert race.bot_finish_ms(7, 0) == int((race.TRACK / race.bot_speed(7, 0) + 1.5) * 1000)


def test_join_same_room_and_tick(conn, uid):
    from conftest import make_client
    other = make_client(conn, login="racer2")[0]
    a = race.join(conn, uid, "Али")
    b = race.join(conn, other, "Фаррух")
    assert a["room"] == b["room"] and a["seed"] == b["seed"] and 0 < b["start_in"] <= race.WAIT
    assert race.online(conn) == 2
    seen = race.tick(conn, uid, a["room"], 120.5, 2.0, 50)["players"]
    assert [p["name"] for p in seen] == ["Фаррух"]
    assert race.tick(conn, other, a["room"], 0, 0, 0)["players"][0]["z"] == 120.5


def test_late_player_gets_new_room(conn, uid):
    from conftest import make_client
    a = race.join(conn, uid, "Али")
    conn.execute("UPDATE race_rooms SET start_at = ? WHERE id = ?", (time.time() + 1, a["room"]))   # старт вот-вот
    b = race.join(conn, make_client(conn, login="late")[0], "Поздний")
    assert b["room"] != a["room"]


def _started(conn, room, seconds_ago):
    conn.execute("UPDATE race_rooms SET start_at = ? WHERE id = ?", (time.time() - seconds_ago, room))


def test_finish_place_coins_and_checks(conn, uid):
    a = race.join(conn, uid, "Али")
    with pytest.raises(race.RaceError):                       # быстрее, чем возможно
        _started(conn, a["room"], 5)
        race.finish(conn, uid, a["room"], 5000)
    with pytest.raises(race.RaceError):                       # время не сходится с часами сервера
        _started(conn, a["room"], 10)
        race.finish(conn, uid, a["room"], 45000)
    fast = min(race.bot_finish_ms(a["seed"], i) for i in range(5)) - 500
    _started(conn, a["room"], fast / 1000)
    r = race.finish(conn, uid, a["room"], fast)
    assert r["place"] == 1 and r["won"] == race.PRIZES[1] and r["coins"] == 10 and r["wins"] == 1
    with pytest.raises(race.RaceError):                       # второй раз тот же финиш не засчитать
        race.finish(conn, uid, a["room"], fast)


def test_slow_player_is_behind_bots(conn, uid):
    a = race.join(conn, uid, "Али")
    slow = max(race.bot_finish_ms(a["seed"], i) for i in range(5)) + 800
    _started(conn, a["room"], slow / 1000)
    r = race.finish(conn, uid, a["room"], slow)
    assert r["place"] == 6 and r["won"] == 0


def test_day_cap(conn, uid):
    conn.execute("INSERT OR IGNORE INTO race_wallet (user_id) VALUES (?)", (uid,))
    conn.execute("UPDATE race_wallet SET day = ?, day_coins = ? WHERE user_id = ?", (race._today(5), race.DAY_CAP - 4, uid))
    a = race.join(conn, uid, "Али")
    fast = min(race.bot_finish_ms(a["seed"], i) for i in range(5)) - 500
    _started(conn, a["room"], fast / 1000)
    r = race.finish(conn, uid, a["room"], fast)
    assert r["won"] == 4 and r["day_left"] == 0                # не больше лимита в день


def test_shop_buy_and_select(conn, uid):
    race.wallet(conn, uid, "Али")
    with pytest.raises(race.RaceError):
        race.shop(conn, uid, "red")                            # монет нет
    conn.execute("UPDATE race_wallet SET coins = 25 WHERE user_id = ?", (uid,))
    r = race.shop(conn, uid, "red")
    assert r == {"coins": 5, "color": "red", "owned": ["violet", "red"]}
    assert race.shop(conn, uid, "violet")["coins"] == 5        # уже купленный — бесплатно
    assert race.shop(conn, uid, "red")["coins"] == 5
    with pytest.raises(race.RaceError):
        race.shop(conn, uid, "nope")


def test_api_needs_telegram_signature(client):
    assert client.post("/tg/api/race/profile", json={}).status_code == 403
    assert client.get("/tg/race").status_code == 200


def test_solo_room_is_private_and_starts_fast(conn, uid):
    from conftest import make_client
    a = race.join(conn, uid, "Али", solo=True)
    assert 0 < a["start_in"] <= race.WAIT_SOLO
    b = race.join(conn, make_client(conn, login="racer3")[0], "Фаррух")        # «с людьми» в чужой заезд с ботами не попадает
    assert b["room"] != a["room"]


def test_upgrade_costs_grow_and_stop_at_max(conn, uid):
    p = race.profile(conn, uid, "Али")
    assert p["upg"] == {"engine": 0, "accel": 0, "nitro": 0} and p["track"] == race.TRACK and p["nitro_k"] == race.NITRO_K
    with pytest.raises(race.RaceError):
        race.upgrade(conn, uid, "engine")                      # монет нет
    conn.execute("UPDATE race_wallet SET coins = 1000 WHERE user_id = ?", (uid,))
    assert race.upgrade(conn, uid, "engine") == {"coins": 1000 - race.UPG_COST, "upg": {"engine": 1, "accel": 0, "nitro": 0}}
    assert race.upgrade(conn, uid, "engine")["coins"] == 1000 - race.UPG_COST * 3      # второй уровень дороже
    for _ in range(race.UPG_MAX - 2):
        race.upgrade(conn, uid, "engine")
    with pytest.raises(race.RaceError):
        race.upgrade(conn, uid, "engine")                      # максимум
    with pytest.raises(race.RaceError):
        race.upgrade(conn, uid, "wings")
    # даже полностью прокачанная машина на сплошном нитро не проедет быстрее серверного минимума
    assert race.TRACK / ((race.VMAX + race.UPG["engine"] * race.UPG_MAX) * race.NITRO_K) * 1000 >= race.MIN_MS


def test_online_counts_everyone_in_the_app(conn, uid):
    from conftest import make_client
    other = make_client(conn, login="viewer")[0]
    race.seen(conn, uid, "Али", "garage")
    race.seen(conn, other, "Фаррух", "app")
    lob = race.lobby(conn, uid)
    assert lob["online"] == 2 and lob["garage"] == 1 and lob["rooms"] == []
    conn.execute("UPDATE race_seen SET at = ? WHERE user_id = ?", (time.time() - race.ONLINE_SEC - 5, other))
    assert race.online(conn) == 1                               # закрыл приложение — уже не «в сети»


def test_lobby_shows_waiting_player_and_second_human_speeds_start(conn, uid):
    from conftest import make_client
    a = race.join(conn, uid, "Али")
    assert race.WAIT - 1 < a["start_in"] <= race.WAIT           # один — ждём соперников дольше
    other = make_client(conn, login="racer4")[0]
    lob = race.lobby(conn, other)
    assert lob["rooms"][0]["players"] == ["Али"] and not lob["rooms"][0]["mine"]
    b = race.join(conn, other, "Фаррух")
    assert b["room"] == a["room"] and b["start_in"] <= race.WAIT_PAIR    # двое живых — старт скоро
    assert race.lobby(conn, other)["rooms"][0]["mine"]


def test_results_build_rating_and_stats(conn, uid):
    a = race.join(conn, uid, "Али")
    fast = min(race.bot_finish_ms(a["seed"], i) for i in range(5)) - 500
    _started(conn, a["room"], fast / 1000)
    race.finish(conn, uid, a["room"], fast)
    st = race.stats(conn, uid)
    assert st["races"] == 1 and st["wins"] == 1 and st["podium"] == 1 and st["best_ms"] == fast
    assert st["points"] == race.POINTS[1] and st["rank_week"] == 1 and st["win_rate"] == 100
    top = race.top(conn, period="week")
    assert top[0]["user_id"] == uid and top[0]["points"] == race.POINTS[1]
    assert race.top(conn, period="all")[0]["wins"] == 1
