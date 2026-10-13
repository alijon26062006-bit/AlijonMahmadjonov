"""Конкурс рефералов недели: засчитываются только друзья с подтверждённой почтой, одно устройство — один друг."""

from datetime import datetime, timedelta, timezone

from conftest import balance, csrf_of, web_login
from fastapi.testclient import TestClient

from donatix import accounts, contest, emailverify, referrals


def test_email_rules():
    assert contest.normalize_email("A.Li+promo@GMail.com") == "ali@gmail.com"
    assert contest.normalize_email("ali@googlemail.com") == "ali@gmail.com"
    assert contest.normalize_email("a.li+x@mail.ru") == "a.li@mail.ru"
    assert contest.disposable("x@mailinator.com") and contest.disposable("x@abc.yopmail.com")
    assert not contest.disposable("x@gmail.com")


def test_week_ends_sunday_20_local():
    now = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)   # среда
    start, end = contest.week_bounds(5, now)
    local = end.astimezone(timezone(timedelta(hours=5)))
    assert local.weekday() == 6 and local.hour == 20 and end - start == timedelta(days=7)


def _signup(app, config, conn, code, email, device, ua="UA-1"):
    c = TestClient(app, headers={"user-agent": ua})
    c.cookies.set("dx_vid", device)
    page = c.get(f"/register?ref={code}").text
    login = email.split("@")[0].replace(".", "").replace("+", "")[:20] + "x"
    r = c.post("/register", data={"csrf": csrf_of(page), "email": email, "login": login, "password": "password123",
                                   "password2": "password123"}, follow_redirects=False)
    assert r.status_code == 303, r.text
    uid = conn.execute("SELECT id FROM users WHERE email = ?", (email.lower(),)).fetchone()[0]
    return uid, c


def test_friends_count_only_after_email_and_once_per_device(app, config, conn):
    config.smtp_host = ""   # писем нет — подтверждаем ссылкой из токена
    ref = accounts.create_user(conn, email="r@example.com", login="inviter", password="password123", status="active")
    code = referrals.code_for(conn, ref)
    b, cb = _signup(app, config, conn, code, "friend.one@gmail.com", "aaaaaaaaaaaaaaaa")
    start, end = contest.week_bounds(config.tz_offset)
    assert contest.leaderboard(conn, start, end) == []                    # почта не подтверждена — не считается
    assert "Подтвердите почту" in cb.get("/panel").text
    r = cb.get(f"/verify-email?t={emailverify.token(config, b, 'friend.one@gmail.com')}", follow_redirects=True)
    assert "Почта подтверждена" in r.text
    assert contest.leaderboard(conn, start, end)[0]["friends"] == 1
    assert cb.get("/verify-email?t=1.1.bad", follow_redirects=True).status_code == 200   # подделка — без падения

    # тот же браузер (метка устройства) — второй друг не засчитывается
    c2, _ = _signup(app, config, conn, code, "second@mail.ru", "aaaaaaaaaaaaaaaa", ua="UA-2")
    contest.mark_verified(conn, c2)
    # копия той же Gmail-почты
    c3, _ = _signup(app, config, conn, code, "friendone+2@gmail.com", "bbbbbbbbbbbbbbbb", ua="UA-3")
    contest.mark_verified(conn, c3)
    # одноразовая почта
    c4, _ = _signup(app, config, conn, code, "zz@yopmail.com", "cccccccccccccccc", ua="UA-4")
    contest.mark_verified(conn, c4)
    # честный второй друг
    c5, _ = _signup(app, config, conn, code, "real@mail.ru", "dddddddddddddddd", ua="UA-5")
    contest.mark_verified(conn, c5)
    reasons = {r[0]: r[1] for r in conn.execute("SELECT user_id, reason FROM ref_signups")}
    assert "устройства" in reasons[c2] and "уже засчитывалась" in reasons[c3] and "одноразовая" in reasons[c4]
    assert reasons[c5] is None
    assert contest.leaderboard(conn, start, end)[0]["friends"] == 2

    # со своего устройства себя не пригласить
    conn.execute("INSERT INTO visits (ts, visitor, session, user_id, path, is_new) VALUES (?, ?, 's', ?, '/', 0)",
                 (datetime.now(timezone.utc).isoformat(), "eeeeeeeeeeeeeeee", ref))
    c6, _ = _signup(app, config, conn, code, "alt@mail.ru", "eeeeeeeeeeeeeeee", ua="UA-6")
    contest.mark_verified(conn, c6)
    assert "пригласившего" in conn.execute("SELECT reason FROM ref_signups WHERE user_id = ?", (c6,)).fetchone()[0]

    # страница конкурса у пригласившего
    c = TestClient(app)
    web_login(c, "r@example.com", "password123")
    page = c.get("/panel/referrals").text
    assert "Конкурс недели" in page and "50 сомони" in page and "1 месте" in page


def test_sunday_payout_once(app, config, conn):
    ref1 = accounts.create_user(conn, email="a@example.com", login="alpha", password="password123", status="active")
    ref2 = accounts.create_user(conn, email="b@example.com", login="bravo", password="password123", status="active")
    now = datetime.now(timezone.utc)
    start, _ = contest.week_bounds(config.tz_offset, now)
    inside = (start - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")   # прошлая неделя
    contest._ensure(conn)
    for i, r in enumerate((ref1, ref1, ref2)):
        uid = accounts.create_user(conn, email=f"f{i}@example.com", login=f"friend{i}", password="password123",
                                   status="active")
        conn.execute("INSERT INTO ref_signups (user_id, referrer_id, created_at, counted_at) VALUES (?, ?, ?, ?)",
                     (uid, r, inside, inside))
    before = balance(conn, ref1)
    assert contest.settle(conn, config, now) == 2
    assert contest.settle(conn, config, now) == 0                        # второй раз не платит
    from donatix import payments
    rate = payments.settings(conn, config)["tjs_rate"]
    assert balance(conn, ref1) - before == int(50 / rate * 10000)
    assert [r[0] for r in conn.execute("SELECT user_id FROM contest_winners ORDER BY place")] == [ref1, ref2]


def test_admin_contest_page(app, config, conn):
    adm = TestClient(app)
    web_login(adm, "admin@example.com", "adminpass123")
    page = adm.get("/admin/contest").text
    assert "Конкурс рефералов недели" in page
    adm.post("/admin/contest", data={"csrf": csrf_of(page), "enabled": "1", "p1": "100", "p2": "60", "p3": "30"})
    assert contest.prizes(conn) == [100, 60, 30]


def test_register_sends_code_and_code_verifies(app, config, conn, monkeypatch):
    """Регистрация → на почту код из 6 цифр (через Resend) → ввёл код → почта подтверждена.
    Неверный код — 5 попыток, потом нужен новый; новый код не чаще раза в минуту."""
    import re
    config.resend_key = "re_test_key_1234567890abcdef"
    sent = []

    class Resp:
        status_code = 200
        text = "{}"

    def fake_post(url, **kw):
        sent.append(kw["json"])
        return Resp()
    monkeypatch.setattr(emailverify.httpx, "post", fake_post)
    monkeypatch.setattr(emailverify.threading, "Thread",
                        lambda target, args, daemon: type("T", (), {"start": lambda self: target(*args)})())
    c = TestClient(app)
    page = c.get("/register").text
    r = c.post("/register", data={"csrf": csrf_of(page), "email": "new@mail.ru", "login": "newbie",
                                  "password": "password123", "password2": "password123"}, follow_redirects=False)
    assert r.headers["location"] == "/panel/verify-email"
    assert sent and sent[0]["to"] == ["new@mail.ru"]
    code = re.search(r"\b(\d{6})\b", sent[0]["subject"]).group(1)
    page = c.get("/panel/verify-email").text
    assert "Код из письма" in page
    token = csrf_of(page)
    wrong = "000000" if code != "000000" else "111111"
    r = c.post("/panel/verify-email/code", data={"csrf": token, "code": wrong}, follow_redirects=True)
    assert "Неверный код" in r.text
    r = c.post("/panel/verify-email", data={"csrf": token}, follow_redirects=True)   # сразу же — рано
    assert "Новый можно через" in r.text and len(sent) == 1
    r = c.post("/panel/verify-email/code", data={"csrf": token, "code": code[:3] + " " + code[3:]},
               follow_redirects=True)
    assert "Почта подтверждена" in r.text
    uid = conn.execute("SELECT id FROM users WHERE email = 'new@mail.ru'").fetchone()[0]
    assert conn.execute("SELECT email_verified_at FROM users WHERE id = ?", (uid,)).fetchone()[0]
    assert emailverify.check_code(conn, config, uid, code) == "expired"     # код одноразовый


def test_code_attempts_limit(config, conn):
    config.resend_key = ""
    config.smtp_host = "smtp.test"
    uid = accounts.create_user(conn, email="t@mail.ru", login="tester", password="password123", status="active")
    emailverify._ensure(conn)
    import time
    conn.execute("INSERT INTO email_codes (user_id, code_hash, email, expires_at, tries, sent_at) VALUES "
                 "(?, ?, 't@mail.ru', ?, 0, ?)", (uid, emailverify._hash(config, uid, "123456"), time.time() + 600,
                                                  time.time()))
    for _ in range(4):
        assert emailverify.check_code(conn, config, uid, "999999") == "bad"
    assert emailverify.check_code(conn, config, uid, "999999") == "expired"
    assert emailverify.check_code(conn, config, uid, "123456") == "expired"   # попытки кончились
