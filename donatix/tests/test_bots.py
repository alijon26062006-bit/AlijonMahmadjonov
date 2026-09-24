"""Конструктор ботов: подключение по токену, запуск процесса с нужными настройками, остановка."""

import json
import sys
import time

import httpx
import pytest
from conftest import web_login
from fastapi.testclient import TestClient

from donatix import accounts, bots

TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw1"


def _tg(ok=True):
    body = {"ok": ok, "result": {"username": "shop_test_bot"}}
    return httpx.MockTransport(lambda req: httpx.Response(200, json=body))


def test_check_token():
    assert bots.check_token(TOKEN, transport=_tg()) == "shop_test_bot"
    with pytest.raises(bots.BotError):
        bots.check_token("nope")
    with pytest.raises(bots.BotError):
        bots.check_token(TOKEN, transport=_tg(ok=False))
    assert bots.parse_admin_ids("111, 222") == "111,222"
    with pytest.raises(bots.BotError):
        bots.parse_admin_ids("@user")


def test_runner_starts_bot_with_donatix_settings(config, conn, tmp_path, monkeypatch):
    # вместо настоящего магазина — крошечный app/main.py, который пишет свои настройки и ждёт
    tpl = tmp_path / "tpl"
    (tpl / "app").mkdir(parents=True)
    (tpl / "app" / "__init__.py").write_text("")
    (tpl / "app" / "main.py").write_text(
        "import json, os, time\n"
        "keys = ['BOT_TOKEN','ADMIN_IDS','FRAGMENT_MODE','FAZER_API_KEY','FAZER_BASE_URL','DONATIX_URL','DB_PATH']\n"
        "open(os.environ['DB_PATH'] + '.env.json', 'w').write(json.dumps({k: os.environ.get(k) for k in keys}))\n"
        "time.sleep(60)\n")
    monkeypatch.setattr(bots, "TEMPLATE_DIR", tpl)
    uid = accounts.create_user(conn, email="o@example.com", login="owner", password="password123", status="active")
    bid = bots.create(conn, config, user_id=uid, token=TOKEN, admin_ids="555", username="shop_test_bot")
    with pytest.raises(bots.BotError):
        bots.create(conn, config, user_id=uid, token=TOKEN, admin_ids="555", username="x")  # второй раз нельзя
    runner = bots.BotRunner(config, "http://127.0.0.1:8000", python=sys.executable)
    try:
        runner.sync()
        dump = bots.bot_dir(config, bid) / "bot.sqlite3.env.json"
        for _ in range(100):
            if dump.exists():
                break
            time.sleep(0.05)
        env = json.loads(dump.read_text())
        assert env["BOT_TOKEN"] == TOKEN and env["ADMIN_IDS"] == "555" and env["FRAGMENT_MODE"] == "fazer"
        assert env["FAZER_BASE_URL"] == env["DONATIX_URL"] == "http://127.0.0.1:8000"
        assert accounts.user_by_api_key(conn, env["FAZER_API_KEY"])["id"] == uid  # ключ владельца, создан сам
        assert runner.state(bid)["running"]
        bots.set_enabled(conn, bid, False)
        runner.sync()
        assert not runner.state(bid)["running"]
        bots.delete(conn, bid)
        assert accounts.user_by_api_key(conn, env["FAZER_API_KEY"]) is None  # ключ отозван
    finally:
        runner.stop()


def test_admin_bots_page(app, config, conn, monkeypatch):
    monkeypatch.setattr(bots, "check_token", lambda token: "shop_test_bot")
    admin = TestClient(app)
    token = web_login(admin, "admin@example.com", "adminpass123")
    r = admin.post("/admin/bots", data={"csrf": token, "token": TOKEN, "admin_ids": "555", "user_id": "0"})
    assert "Бот @shop_test_bot подключён" in r.text and "@shop_test_bot" in r.text
    assert TOKEN not in r.text  # токен на странице не показываем
    (bots.bot_dir(config, 1)).mkdir(parents=True, exist_ok=True)
    (bots.bot_dir(config, 1) / "bot.log").write_text(f"start with {TOKEN}\n")
    assert TOKEN not in admin.get("/admin/bots/1/log").text


def test_no_double_start_and_conflict_warning(config, conn, tmp_path, monkeypatch):
    import threading
    tpl = tmp_path / "tpl2"
    (tpl / "app").mkdir(parents=True)
    (tpl / "app" / "__init__.py").write_text("")
    (tpl / "app" / "main.py").write_text("import time\ntime.sleep(60)\n")
    monkeypatch.setattr(bots, "TEMPLATE_DIR", tpl)
    uid = accounts.create_user(conn, email="d@example.com", login="dbl", password="password123", status="active")
    bid = bots.create(conn, config, user_id=uid, token=TOKEN, admin_ids="1", username="dbl_bot")
    runner = bots.BotRunner(config, "http://x", python=sys.executable)
    spawned = []
    real = runner._spawn
    monkeypatch.setattr(runner, "_spawn", lambda py, row: (spawned.append(row["id"]), real(py, row)))
    try:
        ts = [threading.Thread(target=runner.sync) for _ in range(5)]  # кнопка + фоновая проверка разом
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        assert spawned == [bid]
        (bots.bot_dir(config, bid) / "bot.log").write_text(
            "aiogram.exceptions.TelegramConflictError: Conflict: terminated by other getUpdates request\n")
        assert runner.state(bid)["conflict"] is True
    finally:
        runner.stop()
