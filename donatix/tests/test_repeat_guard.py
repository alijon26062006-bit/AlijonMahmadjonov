"""ИИ-модератор повторных чеков — правило по решению суда (10 агентов и судья)."""

import pytest
from fastapi.testclient import TestClient

from conftest import csrf_of, web_login
from donatix import accounts, bots, db, orders, payments, repeat_guard

PNG = b"\x89PNG\r\n\x1a\n" + b"R" * 200
DAY = 86400


class Clock:
    def __init__(self):
        self.t = 1_800_000_000

    def __call__(self):
        return self.t


@pytest.fixture
def g(app, config, conn, monkeypatch):
    monkeypatch.setattr("donatix.worker.notify_admin_file", lambda *a, **k: None)
    sent = []
    monkeypatch.setattr("donatix.worker.notify_admin", lambda cfg, text, *a, **k: sent.append(text))
    monkeypatch.setattr("donatix.payments.read_receipt", lambda *a, **k: None)
    clock = Clock()
    monkeypatch.setattr(repeat_guard, "_now", clock)
    db.set_setting(conn, "repeat.start_ts", "0")   # правило уже действует
    config.pay_methods = {"alif": "Алиф: +992 90 000 00 00 (Али)"}
    uid = accounts.create_user(conn, email="rg@example.com", login="rgl", password="password123", status="active")
    user = accounts.get_user(conn, uid)
    first = payments.create(conn, config, user, "alif", "100")
    payments.attach_receipt(conn, config, uid, first, PNG, seen=None)
    payments.confirm(conn, config, first, 1)          # этот чек зачислен

    class G:
        pass
    o = G()
    o.uid, o.user, o.first, o.clock, o.sent, o.conn, o.config = uid, user, first, clock, sent, conn, config

    def again(ext: str = ""):
        """Тот же уже зачисленный чек — к новой заявке. Возвращает текст отказа."""
        pid = payments.create(conn, config, accounts.get_user(conn, uid), "alif", "100", ext_user=ext)
        with pytest.raises(payments.ReceiptUsed) as err:
            payments.attach_receipt(conn, config, uid, pid, PNG, seen=None)
        payments.cancel(conn, uid, pid, config)
        return str(err.value)
    o.again = again
    return o


def _hold(g, subject=None):
    return repeat_guard.active_hold(g.conn, subject or repeat_guard.subject_for(g.uid))


def test_before_start_date_only_refuses(g):
    db.set_setting(g.conn, "repeat.start_ts", str(g.clock.t + DAY))
    for _ in range(5):
        g.clock.t += 3600
        assert f"#{g.first}" in g.again()
    assert g.conn.execute("SELECT COUNT(*) FROM receipt_strikes").fetchone()[0] == 0


def test_ladder_refuse_warn_5_days_7_days_then_moderator(g):
    t1 = g.again()
    assert f"#{g.first}" in t1 and "Предупреждение" not in t1 and _hold(g) is None
    g.clock.t += 3600
    assert "Предупреждение" in g.again()
    assert repeat_guard.banner(g.conn, g.uid)["kind"] == "warn"
    g.clock.t += 3600
    with pytest.raises(payments.PaymentError):   # 3-й за 30 дней — блок: новые заявки уже не создаются
        pid = payments.create(g.conn, g.config, g.user, "alif", "100")
        payments.attach_receipt(g.conn, g.config, g.uid, pid, PNG, seen=None)
    h = _hold(g)
    assert h is not None and h["level"] == 3 and h["until_ts"] - h["ts"] == 5 * DAY
    # блок закончился — следующий повтор: 7 дней
    g.clock.t = h["until_ts"] + 60
    repeat_guard.tick(g.conn, g.config, g.clock.t)
    assert _hold(g) is None
    g.again()
    h = _hold(g)
    assert h["level"] == 4 and h["until_ts"] - h["ts"] == 7 * DAY
    g.clock.t = h["until_ts"] + 60
    repeat_guard.tick(g.conn, g.config, g.clock.t)
    g.again()
    h = _hold(g)
    assert h["level"] == 5 and h["kind"] == "perm_pending"          # вечную ИИ сам не выносит
    assert accounts.get_user(g.conn, g.uid)["status"] == "active"
    assert any("решение о вечной" in s for s in g.sent)


def test_same_case_within_10_minutes_counts_once(g):
    g.again()
    g.clock.t += 60
    g.again()
    g.clock.t += 120
    g.again()
    assert repeat_guard.level(g.conn, repeat_guard.subject_for(g.uid), g.clock.t) == 1


def test_only_exact_evidence_strikes_automatically(g):
    pid = payments.create(g.conn, g.config, g.user, "alif", "100")
    text = repeat_guard.on_used(g.conn, g.config, g.uid, pid, g.first, "picture")
    assert f"#{g.first}" in text
    assert g.conn.execute("SELECT COUNT(*) FROM receipt_strikes").fetchone()[0] == 0
    rv = g.conn.execute("SELECT * FROM receipt_reviews").fetchone()
    assert rv["status"] == "open"
    repeat_guard.review(g.conn, g.config, rv["id"], True, "модератор")   # модератор подтвердил — страйк
    assert repeat_guard.level(g.conn, repeat_guard.subject_for(g.uid), g.clock.t) == 1


def test_hold_blocks_orders_api_and_freezes_bot(g, client):
    bid = g.conn.execute("INSERT INTO bots (user_id, token_enc, admin_ids, enabled, created_at, updated_at) "
                         "VALUES (?, 'x', '1', 1, 'n', 'n')", (g.uid,)).lastrowid
    for _ in range(3):
        g.clock.t += 3600
        try:
            g.again()
        except Exception:  # noqa: BLE001 — на 3-м раз заявка уже не создаётся
            pass
    h = _hold(g)
    assert h is not None
    assert g.conn.execute("SELECT enabled, disabled_reason FROM bots WHERE id = ?", (bid,)).fetchone()[:] == (0, "hold")
    assert bots.can_enable(g.conn, bid)[0] is False
    with pytest.raises(orders.OrderError) as e:
        orders.create_order(g.conn, g.config, None, g.user, product_id="tg-stars", quantity=50,
                            fields={"telegram_username": "abcd_e"})
    assert e.value.code == "account_hold"
    key = accounts.create_api_key(g.conn, g.uid, "t")
    r = client.get("/api/v1/balance", headers={"X-API-Key": key})
    assert r.status_code == 403 and r.json()["code"] == "account_hold" and r.json()["blocked_until"]
    # блок кончился — бот включается сам, место за ним сохранялось
    g.clock.t = h["until_ts"] + 1
    repeat_guard.tick(g.conn, g.config, g.clock.t)
    assert g.conn.execute("SELECT enabled FROM bots WHERE id = ?", (bid,)).fetchone()[0] == 1


def test_permanent_needs_moderator_after_appeal_window_and_deletes_bot_after_notice(g):
    for lvl in range(5):
        g.clock.t += 3600 if lvl < 3 else 8 * DAY
        repeat_guard.tick(g.conn, g.config, g.clock.t)
        try:
            g.again()
        except Exception:  # noqa: BLE001
            pass
    h = _hold(g)
    assert h["kind"] == "perm_pending"
    bid = g.conn.execute("INSERT INTO bots (user_id, token_enc, admin_ids, enabled, created_at, updated_at) "
                         "VALUES (?, 'x', '1', 0, 'n', 'n')", (g.uid,)).lastrowid
    assert "Срок апелляции" in repeat_guard.confirm_perm(g.conn, g.config, h["id"], "мод")   # рано
    g.clock.t += 49 * 3600
    assert repeat_guard.confirm_perm(g.conn, g.config, h["id"], "мод") == ""
    assert accounts.get_user(g.conn, g.uid)["status"] == "blocked"
    repeat_guard.tick(g.conn, g.config, g.clock.t + 3600)
    assert g.conn.execute("SELECT 1 FROM bots WHERE id = ?", (bid,)).fetchone() is not None   # ещё уведомление
    repeat_guard.tick(g.conn, g.config, g.clock.t + 25 * 3600)
    assert g.conn.execute("SELECT 1 FROM bots WHERE id = ?", (bid,)).fetchone() is None   # место освобождено


def test_appeal_accepted_lifts_hold_and_revokes_strike(g):
    for _ in range(3):
        g.clock.t += 3600
        try:
            g.again()
        except Exception:  # noqa: BLE001
            pass
    h = _hold(g)
    repeat_guard.appeal(g.conn, g.config, g.uid, "Я ошибся и выбрал старый скриншот из галереи")
    assert any("Апелляция" in s for s in g.sent)
    with pytest.raises(ValueError):
        repeat_guard.appeal(g.conn, g.config, g.uid, "ещё раз то же самое обращение")
    repeat_guard.lift(g.conn, g.config, h["id"], "мод")
    assert _hold(g) is None
    assert repeat_guard.level(g.conn, repeat_guard.subject_for(g.uid), g.clock.t) == 2
    logs = [r["action"] for r in g.conn.execute("SELECT action FROM receipt_guard_log")]
    assert "appeal" in logs and "lifted" in logs


def test_appeal_closed_after_48_hours(g):
    for _ in range(3):
        g.clock.t += 3600
        try:
            g.again()
        except Exception:  # noqa: BLE001
            pass
    g.clock.t += 49 * 3600
    with pytest.raises(ValueError):
        repeat_guard.appeal(g.conn, g.config, g.uid, "Поздно, но всё же прошу разобраться")


def test_90_days_clean_lowers_level(g):
    g.again()
    g.clock.t += 3600
    g.again()
    assert repeat_guard.level(g.conn, repeat_guard.subject_for(g.uid), g.clock.t) == 2
    g.clock.t += 91 * DAY
    assert repeat_guard.level(g.conn, repeat_guard.subject_for(g.uid), g.clock.t) == 1
    text = g.again()    # после 90 дней это снова 2-я ступень (предупреждение), а не блок
    assert "Предупреждение" in text and _hold(g) is None


def test_partner_customer_is_punished_not_partner(g):
    for _ in range(3):
        g.clock.t += 3600
        try:
            g.again(ext="tg777")
        except Exception:  # noqa: BLE001
            pass
    assert _hold(g, repeat_guard.subject_for(g.uid, "tg777")) is not None
    assert _hold(g) is None                                    # аккаунт партнёра работает
    payments.create(g.conn, g.config, g.user, "alif", "100", ext_user="other")   # другой покупатель — можно
    with pytest.raises(payments.PaymentError):
        payments.create(g.conn, g.config, g.user, "alif", "100", ext_user="tg777")


def test_moderator_pages(g, app, conn):
    c = TestClient(app)
    web_login(c, "admin@example.com", "adminpass123")
    page = c.get("/admin/repeat-guard")
    assert page.status_code == 200 and "Повторные чеки" in page.text
    r = c.post("/admin/repeat-guard/act", data={"csrf": csrf_of(page.text), "act": "start", "start": "2026-12-08"},
               follow_redirects=False)
    assert r.status_code == 303
    assert repeat_guard.when(repeat_guard.start_ts(conn)).startswith("08.12.2026")
