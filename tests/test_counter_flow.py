"""Проверяем бота целиком: от голосового до отчёта — но без Telegram."""

from __future__ import annotations

import pytest

from counter import db, handlers
from counter.config import Config
from counter.numbers import SCALE, format_amount

from conftest_counter import (
    FakeBot,
    FakeCallback,
    FakeMessage,
    FakeRecognizer,
    FakeVoice,
)


@pytest.fixture()
def config(tmp_path) -> Config:
    return Config(
        telegram_token="test",
        allowed_user_ids=frozenset(),
        data_dir=tmp_path,
        model_path=tmp_path / "model",
        tz_name="UTC",
        duplicate_window_seconds=0,   # в тестах повторы не мешают
    )


@pytest.fixture()
def conn(config):
    connection = db.connect(config.db_path)
    yield connection
    connection.close()


async def voice(text: str, conn, config, chat_id: int = 100) -> FakeMessage:
    message = FakeMessage(chat=_chat(chat_id), voice=FakeVoice())
    await handlers.on_voice(message, FakeBot(), conn, config, FakeRecognizer(text))
    return message


def _chat(chat_id: int = 100):
    from conftest_counter import FakeChat

    return FakeChat(chat_id)


async def add_person(conn, config, name: str, chat_id: int = 100) -> None:
    message = FakeMessage(text=name, chat=_chat(chat_id))
    db.set_pending(conn, chat_id, "add_worker")
    await handlers.on_text(message, conn, config)


# ── Основной сценарий ──────────────────────────────────────────────────────
async def test_full_day(conn, config):
    await handlers.cmd_start(FakeMessage(text="/start", chat=_chat()), conn, config)
    await add_person(conn, config, "Иброхим")

    message = await voice("семь шестьсот", conn, config)
    assert format_amount(7600 * SCALE) in message.last
    assert "Иброхим" in message.last

    message = await voice("пять четыреста", conn, config)
    assert format_amount(13000 * SCALE) in message.last          # 7600 + 5400 сложились

    session = db.current_session(conn, 100)
    count, total = db.grand_total(conn, 100, session["id"])
    assert (count, total) == (2, 13000 * SCALE)


async def test_second_person_gets_own_total(conn, config):
    await add_person(conn, config, "Иброхим")
    await voice("семь шестьсот", conn, config)

    await add_person(conn, config, "Азиз")    # добавили — и сразу пишем ему
    await voice("тысяча", conn, config)

    session = db.current_session(conn, 100)
    rows = {row["name"]: row["total"] for row in db.summary(conn, 100, session["id"])}
    assert rows == {"Иброхим": 7600 * SCALE, "Азиз": 1000 * SCALE}


async def test_switch_person_by_button(conn, config):
    await add_person(conn, config, "Иброхим")
    await add_person(conn, config, "Азиз")

    message = FakeMessage(text="👤 Иброхим", chat=_chat())
    await handlers.switch_worker(message, conn, config)
    assert "Иброхим" in message.last

    await voice("сто", conn, config)
    session = db.current_session(conn, 100)
    rows = {row["name"]: row["total"] for row in db.summary(conn, 100, session["id"])}
    assert rows["Иброхим"] == 100 * SCALE
    assert rows["Азиз"] == 0


# ── Ошибки и исправления ───────────────────────────────────────────────────
async def test_no_person_yet(conn, config):
    message = await voice("семь шестьсот", conn, config)
    assert "не заведён ни один человек" in message.last.lower()


async def test_nothing_recognized(conn, config):
    await add_person(conn, config, "Иброхим")
    message = await voice("привет как дела", conn, config)
    assert "не разобрал" in message.last.lower()
    session = db.current_session(conn, 100)
    assert db.grand_total(conn, 100, session["id"])[0] == 0


async def test_two_numbers_ask_which(conn, config):
    await add_person(conn, config, "Иброхим")
    message = await voice("пятьсот и триста", conn, config)
    assert "несколько чисел" in message.last

    session = db.current_session(conn, 100)
    assert db.grand_total(conn, 100, session["id"])[0] == 0   # пока ничего не записано

    worker = db.active_worker(conn, 100)
    callback = FakeCallback(f"add:{worker['id']}:1", message)
    await handlers.cb_add(callback, conn, config)
    assert db.grand_total(conn, 100, session["id"]) == (1, 300 * SCALE)


async def test_edit_entry(conn, config):
    await add_person(conn, config, "Иброхим")
    message = await voice("семь шестьсот", conn, config)
    session = db.current_session(conn, 100)
    entry = db.last_entry(conn, 100, session["id"])

    await handlers.cb_entry(FakeCallback(f"e:edit:{entry['id']}", message), conn, config)
    assert db.get_pending(conn, 100)[0] == f"edit:{entry['id']}"

    fix = FakeMessage(text="6500", chat=_chat())
    await handlers.on_text(fix, conn, config)
    assert db.get_entry(conn, entry["id"])["amount"] == 6500 * SCALE
    assert db.grand_total(conn, 100, session["id"]) == (1, 6500 * SCALE)
    assert "Исправил" in fix.last


async def test_delete_and_restore(conn, config):
    await add_person(conn, config, "Иброхим")
    message = await voice("семь шестьсот", conn, config)
    session = db.current_session(conn, 100)
    entry = db.last_entry(conn, 100, session["id"])

    await handlers.cb_entry(FakeCallback(f"e:del:{entry['id']}", message), conn, config)
    assert db.grand_total(conn, 100, session["id"]) == (0, 0)

    await handlers.cb_entry(FakeCallback(f"e:res:{entry['id']}", message), conn, config)
    assert db.grand_total(conn, 100, session["id"]) == (1, 7600 * SCALE)


async def test_undo_last(conn, config):
    await add_person(conn, config, "Иброхим")
    await voice("сто", conn, config)
    await voice("двести", conn, config)

    message = FakeMessage(text="↩️ Отменить", chat=_chat())
    await handlers.cmd_undo(message, conn, config)
    session = db.current_session(conn, 100)
    assert db.grand_total(conn, 100, session["id"]) == (1, 100 * SCALE)


async def test_huge_number_asks_confirmation(conn, config):
    await add_person(conn, config, "Иброхим")
    message = await voice("девять миллионов", conn, config)
    assert "слишком большое" in message.last.lower()
    session = db.current_session(conn, 100)
    assert db.grand_total(conn, 100, session["id"])[0] == 0


async def test_duplicate_guard(conn, config):
    guarded = Config(**{**config.__dict__, "duplicate_window_seconds": 60})
    await add_person(conn, guarded, "Иброхим")
    await voice("сто", conn, guarded)
    message = await voice("сто", conn, guarded)
    assert "случайно два раза" in message.last

    session = db.current_session(conn, 100)
    assert db.grand_total(conn, 100, session["id"])[0] == 1

    worker = db.active_worker(conn, 100)
    await handlers.cb_force(FakeCallback(f"force:{worker['id']}:{100 * SCALE}", message), conn, guarded)
    assert db.grand_total(conn, 100, session["id"])[0] == 2


async def test_voice_engine_missing_tells_how_to_type(conn, config):
    await add_person(conn, config, "Иброхим")
    message = FakeMessage(chat=_chat(), voice=FakeVoice())
    await handlers.on_voice(message, FakeBot(), conn, config, FakeRecognizer(problem="нет модели"))
    assert "цифрами" in message.last

    typed = FakeMessage(text="7600", chat=_chat())
    await handlers.on_text(typed, conn, config)
    session = db.current_session(conn, 100)
    assert db.grand_total(conn, 100, session["id"]) == (1, 7600 * SCALE)


# ── Смены и отчёты ─────────────────────────────────────────────────────────
async def test_new_session_resets_counters_but_keeps_history(conn, config):
    await add_person(conn, config, "Иброхим")
    await voice("сто", conn, config)

    message = FakeMessage(chat=_chat())
    await handlers.cb_new_session(FakeCallback("s:new:yes", message), conn, config)

    session = db.current_session(conn, 100)
    assert db.grand_total(conn, 100, session["id"]) == (0, 0)
    assert db.grand_total(conn, 100, None) == (1, 100 * SCALE)


async def test_report_files(conn, config):
    await add_person(conn, config, "Иброхим")
    await voice("семь шестьсот", conn, config)
    await add_person(conn, config, "Азиз")
    await voice("пять четыреста", conn, config)

    message = FakeMessage(chat=_chat())
    await handlers.cb_report(FakeCallback("rep:now:both", message), conn, config)

    documents = [item for item in message.sent if item.document is not None]
    assert len(documents) == 2
    names = sorted(doc.document.filename.rsplit(".", 1)[1] for doc in documents)
    assert names == ["pdf", "xlsx"]
    assert format_amount(13000 * SCALE) in documents[0].caption

    data = handlers.collect_report(conn, config, 100, "now")
    assert data.total == 13000 * SCALE
    assert [entry["name"] for entry in data.entries] == ["Иброхим", "Азиз"]


async def test_empty_report_is_explained(conn, config):
    message = FakeMessage(chat=_chat())
    await handlers.cb_report(FakeCallback("rep:now:xlsx", message), conn, config)
    assert "записей нет" in message.last.lower()


async def test_chats_do_not_mix(conn, config):
    await add_person(conn, config, "Иброхим", chat_id=100)
    await voice("сто", conn, config, chat_id=100)
    await add_person(conn, config, "Другой", chat_id=200)
    await voice("двести", conn, config, chat_id=200)

    assert db.grand_total(conn, 100, None) == (1, 100 * SCALE)
    assert db.grand_total(conn, 200, None) == (1, 200 * SCALE)


async def test_no_active_person_asks_who_then_which_number(conn, config):
    """Человек не выбран и чисел два — бот спросит и то, и другое, ничего не потеряв."""
    await add_person(conn, config, "Иброхим")
    await add_person(conn, config, "Азиз")
    db.set_active_worker(conn, 100, None)

    message = await voice("пятьсот и триста", conn, config)
    assert "Кому записать?" in message.last

    workers = {worker["name"]: worker["id"] for worker in db.list_workers(conn, 100)}
    await handlers.cb_add(FakeCallback(f"add:{workers['Азиз']}:ask", message), conn, config)
    assert "Какое число записать Азиз" in message.last

    session = db.current_session(conn, 100)
    assert db.grand_total(conn, 100, session["id"])[0] == 0

    await handlers.cb_add(FakeCallback(f"add:{workers['Азиз']}:0", message), conn, config)
    assert db.grand_total(conn, 100, session["id"]) == (1, 500 * SCALE)
    assert db.active_worker(conn, 100)["name"] == "Азиз"


async def test_no_active_person_single_number_goes_straight_in(conn, config):
    await add_person(conn, config, "Иброхим")
    db.set_active_worker(conn, 100, None)

    message = await voice("семь шестьсот", conn, config)
    assert "Кому записать?" in message.last

    worker = db.list_workers(conn, 100)[0]
    await handlers.cb_add(FakeCallback(f"add:{worker['id']}:0", message), conn, config)
    session = db.current_session(conn, 100)
    assert db.grand_total(conn, 100, session["id"]) == (1, 7600 * SCALE)
