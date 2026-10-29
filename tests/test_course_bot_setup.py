"""Мастер установки бота курса: токен, владелец по «Старт», .env и автозапуск."""

import stat
from pathlib import Path

from course_bot import setup


def test_env_has_token_and_owner_and_is_private(tmp_path):
    path = tmp_path / ".env"
    setup.write_env("123:ABC", "555", path)
    text = path.read_text(encoding="utf-8")
    assert "BOT_TOKEN=123:ABC" in text and "ADMIN_IDS=555" in text
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_env_is_read_back_by_bot_config(tmp_path, monkeypatch):
    from course_bot import config

    setup.write_env("123:ABC", "555", tmp_path / ".env")
    monkeypatch.setattr(config, "HERE", tmp_path)
    # setenv+delenv: monkeypatch запомнит, что переменных не было, и уберёт то,
    # что load_dotenv положит в окружение, — соседние тесты его не увидят.
    for name in ("BOT_TOKEN", "ADMIN_IDS"):
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    cfg = config.load_config()
    assert cfg.token == "123:ABC" and cfg.admin_ids == frozenset({555})


def test_service_runs_course_bot_with_restart():
    unit = setup.render_service(Path("/root/coursebot/.venv/bin/python"), Path("/root/coursebot"), "root")
    assert "ExecStart=/root/coursebot/.venv/bin/python -m course_bot" in unit
    assert "WorkingDirectory=/root/coursebot" in unit
    assert "Restart=always" in unit


def test_owner_is_whoever_pressed_start(monkeypatch):
    updates = {"ok": True, "result": [{"update_id": 1, "message": {
        "message_id": 1, "text": "/start", "chat": {"id": 777, "type": "private"},
        "from": {"id": 777, "is_bot": False, "first_name": "Алиджон"}}}]}
    calls = []

    def fake_http(url, headers=None, timeout=30):
        calls.append(url)
        return (200, updates) if "getUpdates" in url else (200, {"ok": True})

    monkeypatch.setattr(setup, "http_json", fake_http)
    monkeypatch.setattr(setup.select, "select", lambda r, w, x, t: ([], [], []))
    assert setup.wait_for_start("123:ABC", "kurs_bot") == 777
    assert any("deleteWebhook" in u for u in calls)


def test_bad_token_is_rejected(monkeypatch):
    monkeypatch.setattr(setup, "http_json", lambda url, headers=None, timeout=30: (401, {"ok": False}))
    assert setup.check_token("123:WRONG") is None
    monkeypatch.setattr(setup, "http_json",
                        lambda url, headers=None, timeout=30: (200, {"ok": True, "result": {"username": "kurs_bot"}}))
    assert setup.check_token("123:GOOD") == "kurs_bot"
