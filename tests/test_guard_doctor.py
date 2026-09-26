"""Муҳофиз аз нусхаи дуюм ва «bot doctor»."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from shop import doctor, guard
from shop.db import Database


# ── қулфи «як нусха дар сервер» ───────────────────────────────────────
def test_second_copy_on_same_server_refuses_to_start(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "lock_dir", lambda: tmp_path)
    first = guard.acquire_instance_lock("1:TOKEN", Path("/opt/a"))
    try:
        with pytest.raises(guard.StartRefused) as exc:
            guard.acquire_instance_lock("1:TOKEN", Path("/root/b"))
        assert "/opt/a" in str(exc.value)        # мегӯяд, ки кӣ аллакай кор мекунад
    finally:
        first.close()


def test_lock_is_released_when_bot_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "lock_dir", lambda: tmp_path)
    guard.acquire_instance_lock("1:TOKEN", Path("/opt/a")).close()
    guard.acquire_instance_lock("1:TOKEN", Path("/opt/a")).close()


def test_other_bot_token_is_not_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "lock_dir", lambda: tmp_path)
    first = guard.acquire_instance_lock("1:TOKEN", Path("/opt/a"))
    second = guard.acquire_instance_lock("2:OTHER", Path("/opt/b"))
    first.close()
    second.close()


# ── сервери кӯҳна пас аз кӯчидан ──────────────────────────────────────
def test_moved_server_refuses_to_start(tmp_path):
    guard.mark_moved(tmp_path, "2.29.11.118 2026-09-26")
    with pytest.raises(guard.StartRefused) as exc:
        guard.check_not_moved(tmp_path)
    assert "2.29.11.118" in str(exc.value)


def test_normal_server_starts(tmp_path):
    guard.check_not_moved(tmp_path)


def test_main_exits_with_no_restart_code(monkeypatch, capsys):
    from shop import main as main_mod

    async def refuse():
        raise guard.StartRefused("нусхаи дуюм")

    monkeypatch.setattr(main_mod, "run", refuse)
    with pytest.raises(SystemExit) as exc:
        main_mod.main()
    assert exc.value.code == guard.EXIT_REFUSED
    assert "нусхаи дуюм" in capsys.readouterr().err


# ── тревога: ҳамин бот дар сервери дигар ──────────────────────────────
def test_restart_conflicts_do_not_alarm():
    """Пас аз азнавоғозкунӣ чанд «Conflict» дар 30 сония — ин нусхаи дуюм нест."""
    from shop.middlewares import ConflictWatch

    watch = ConflictWatch(lambda bot: None)
    assert not any(watch._hit(t) for t in (0, 2, 5, 9, 15, 22, 30))


def test_lasting_conflict_alarms_once_per_period():
    from shop.middlewares import ConflictWatch

    watch = ConflictWatch(lambda bot: None, every=900)
    alarms = [t for t in range(0, 600, 5) if watch._hit(t)]
    assert alarms == [90]                        # як бор, баъд то 15 дақиқа хомӯш


def test_quiet_gap_starts_a_new_streak():
    from shop.middlewares import ConflictWatch

    watch = ConflictWatch(lambda bot: None)
    for t in (0, 5, 10):
        watch._hit(t)
    # 10 дақиқа ором, баъд боз чанд конфликт — ин аз нав ҳисоб мешавад.
    assert not any(watch._hit(t) for t in (610, 615, 620, 630))


async def test_conflict_sends_alert_to_admin():
    from aiogram.exceptions import TelegramConflictError
    from shop.middlewares import ConflictWatch

    alerts = []

    async def notify(bot):
        alerts.append(bot)

    watch = ConflictWatch(notify, min_span=0, min_hits=1)

    async def conflict(bot, method):
        raise TelegramConflictError(method=None, message="Conflict: terminated by other getUpdates")

    for _ in range(3):
        with pytest.raises(TelegramConflictError):
            await watch(conflict, "bot", None)
    await asyncio.sleep(0)
    assert alerts == ["bot"]


async def test_normal_requests_pass_through():
    from shop.middlewares import ConflictWatch

    async def fine(bot, method):
        return "ok"

    assert await ConflictWatch(lambda bot: None)(fine, "bot", None) == "ok"


async def test_new_host_is_announced_to_admin(tmp_path):
    from shop import main as main_mod
    from test_shop_flow import FakeBot

    db = Database(tmp_path / "shop.sqlite3")
    bot = FakeBot()
    cfg = type("C", (), {"admin_ids": (1,)})()
    try:
        await main_mod._announce_host(bot, db, cfg, "old (1.1.1.1) /root/x")
        assert bot.messages == []                # бори аввал — хомӯш
        await main_mod._announce_host(bot, db, cfg, "old (1.1.1.1) /root/x")
        assert bot.messages == []                # ҳамон ҷо — хомӯш
        await main_mod._announce_host(bot, db, cfg, "uways (2.29.11.118) /opt/p")
        assert "ҷои нав" in bot.to(1) and "old (1.1.1.1)" in bot.to(1)
    finally:
        db.close()


# ── bot doctor ────────────────────────────────────────────────────────
def _install(root: Path, token: str, users=((1, 500),), orders=()) -> Path:
    (root / "shop").mkdir(parents=True)
    (root / "shop" / "main.py").write_text("")
    (root / "shop" / "db.py").write_text("")
    (root / ".env").write_text(f"SHOP_BOT_TOKEN={token}\n")
    db = Database(root / "data" / "shop.sqlite3")
    for uid, bal in users:
        db.touch_user(uid, f"u{uid}")
        if bal:
            db.change_balance(uid, bal, "topup")
    for uid, price, target in orders:
        db.create_order(user_id=uid, product_code="pubg_60", category="pubg", title="60 UC",
                        price=price, target=target, nickname=None)
    db.close()
    return root


def test_finds_installs_and_marks_duplicate(tmp_path, monkeypatch):
    main = _install(tmp_path / "opt" / "hosting-panel", "1:TOKEN")
    dupe = _install(tmp_path / "root" / "AlijonMahmadjonov", "1:TOKEN")
    other = _install(tmp_path / "home" / "otherbot", "9:OTHER")
    monkeypatch.setattr(doctor, "running_bots", lambda: [])
    monkeypatch.setattr(doctor, "shop_units", lambda: [])

    installs, _, _ = doctor.survey(main, roots=(str(tmp_path),))
    by_path = {i.path: i for i in installs}

    assert by_path[main.resolve()].is_main
    assert by_path[dupe.resolve()].same_bot and not by_path[dupe.resolve()].is_main
    assert not by_path[other.resolve()].same_bot
    assert by_path[dupe.resolve()].stats["users"] == 1


def test_processes_and_services_are_matched_to_folders(tmp_path, monkeypatch):
    main = _install(tmp_path / "opt" / "p", "1:TOKEN")
    dupe = _install(tmp_path / "root" / "copy", "1:TOKEN")
    monkeypatch.setattr(doctor, "running_bots",
                        lambda: [doctor.Proc(101, str(dupe), False), doctor.Proc(55, "/elsewhere", False)])
    monkeypatch.setattr(doctor, "shop_units",
                        lambda: [doctor.Unit("almaz-shop.service", str(main), "active", "enabled")])

    installs, stray, _ = doctor.survey(main, roots=(str(tmp_path),))
    by_path = {i.path: i for i in installs}

    assert [p.pid for p in by_path[dupe.resolve()].procs] == [101]
    assert by_path[main.resolve()].units[0].name == "almaz-shop.service"
    assert [p.pid for p in stray] == [55]


def test_divergence_shows_money_and_orders_only_in_copy(tmp_path):
    main = _install(tmp_path / "a", "1:T", users=((1, 500), (2, 0)))
    dupe = _install(tmp_path / "b", "1:T", users=((1, 900), (2, 0)), orders=((1, 300, "5123456789"),))

    diff = doctor.diverged(main / "data" / "shop.sqlite3", dupe / "data" / "shop.sqlite3")

    assert diff["balances"] == [(1, "u1", 500, 600)]           # 900 − 300 фармоиш
    assert [o[3] for o in diff["orders_only_there"]] == ["5123456789"]


def test_fix_backs_up_and_marks_copy_without_deleting(tmp_path, monkeypatch):
    main = _install(tmp_path / "opt" / "p", "1:TOKEN")
    dupe = _install(tmp_path / "root" / "copy", "1:TOKEN", users=((7, 1234),))
    monkeypatch.setattr(doctor, "running_bots", lambda: [])
    monkeypatch.setattr(doctor, "shop_units", lambda: [])
    calls = []
    monkeypatch.setattr(doctor, "_systemctl", lambda *a: calls.append(a) or "")

    installs, _, _ = doctor.survey(main, roots=(str(tmp_path),))
    copy = next(i for i in installs if i.path == dupe.resolve())
    saved = doctor.backup_db(copy.db, main / "data" / "other-copies", str(copy.path))
    doctor.stop_install(copy, "uways /opt/p")

    assert saved.is_file()
    con = sqlite3.connect(saved)
    assert con.execute("SELECT balance FROM users WHERE id = 7").fetchone()[0] == 1234
    con.close()
    assert copy.db.is_file()                                  # ҳеҷ чиз нест нашуд
    assert guard.moved_to(copy.db.parent).startswith("лишняя копия")
    with pytest.raises(guard.StartRefused):
        guard.check_not_moved(copy.db.parent)


def test_fix_stops_services_of_the_copy(tmp_path, monkeypatch):
    _install(tmp_path / "opt" / "p", "1:TOKEN")
    dupe = _install(tmp_path / "root" / "copy", "1:TOKEN")
    unit = doctor.Unit("shop-copy.service", str(dupe), "active", "enabled")
    calls = []
    monkeypatch.setattr(doctor, "_systemctl", lambda *a: calls.append(a) or "")
    inst = doctor.Install(path=dupe, token_tag="x", db=dupe / "data" / "shop.sqlite3",
                          is_main=False, same_bot=True, stats=None, units=[unit])

    doctor.stop_install(inst, "main")

    assert ("stop", "shop-copy.service") in calls
    assert ("disable", "shop-copy.service") in calls


def test_doctor_report_runs(tmp_path, monkeypatch, capsys):
    main = _install(tmp_path / "opt" / "p", "1:TOKEN")
    _install(tmp_path / "root" / "copy", "1:TOKEN")
    monkeypatch.setattr(doctor, "ROOT", main)
    monkeypatch.setattr(doctor, "SEARCH_ROOTS", (str(tmp_path),))
    monkeypatch.setattr(doctor, "running_bots", lambda: [])
    monkeypatch.setattr(doctor, "shop_units", lambda: [])
    monkeypatch.setattr(doctor, "docker_bots", lambda: [])
    assert doctor.run([]) == 0
    out = capsys.readouterr().out
    assert "ОСНОВНАЯ" in out and "ЛИШНЯЯ КОПИЯ" in out
    assert "bot doctor --fix" not in out            # копия не запущена — выключать нечего
