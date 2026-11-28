"""Сервер ревизии: вход через Telegram, счёт, права, чтение ценника (Claude подменён)."""

import io
import json
import time
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer
from openpyxl import load_workbook

from reviziya_server import db, report
from reviziya_server.app import create_app
from reviziya_server.config import Config
from reviziya_server.reader import ReaderError, parse_answer, thinking_off
from reviziya_server.tgauth import AuthError, check_init_data, sign_init_data

TOKEN = "123456:TEST-TOKEN"
IMAGE = "/9j/4AAQSkZJRg=="  # любой корректный base64


def init_data(user_id=1, name="Алишер", token=TOKEN, auth_date=None, **extra):
    user = {"id": user_id, "first_name": name, **extra}
    return sign_init_data(
        {"auth_date": str(int(auth_date or time.time())), "query_id": "q", "user": json.dumps(user, ensure_ascii=False)},
        token,
    )


# ── вход через Telegram ────────────────────────────────────────────────────

def test_init_data_accepts_a_signed_launch():
    assert check_init_data(init_data(42), TOKEN)["id"] == 42


def test_init_data_rejects_tampering_wrong_token_and_old_launches():
    good = init_data(42)
    with pytest.raises(AuthError):
        check_init_data(good.replace("%22id%22%3A+42", "%22id%22%3A+43"), TOKEN)
    with pytest.raises(AuthError):
        check_init_data(good, "999:OTHER")
    with pytest.raises(AuthError):
        check_init_data(init_data(42, auth_date=time.time() - 10 * 86400), TOKEN)
    with pytest.raises(AuthError):
        check_init_data("", TOKEN)


# ── ответ Claude ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("3000", (3000, False)),
    ("3 000", (3000, False)),
    ("3000?", (3000, True)),
    ("Цена: 2000", (2000, False)),
    ("-", (0, False)),
    ("", (0, False)),
    ("нет ценника", (0, False)),
    ("0", (0, False)),
])
def test_parse_answer(text, expected):
    assert parse_answer(text) == expected


def test_thinking_is_switched_off_the_way_each_model_accepts():
    assert thinking_off("claude-haiku-5-5") == {"type": "disabled"}
    assert thinking_off("claude-sonnet-5-5") == {"type": "between_tools"}


# ── база ───────────────────────────────────────────────────────────────────

@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


def test_first_person_is_admin_the_rest_wait(conn):
    owner, new = db.upsert_user(conn, 1, "Владелец", None)
    assert new and owner["role"] == "admin" and owner["status"] == "active"
    staff, new = db.upsert_user(conn, 2, "Фарход", "farhod")
    assert new and staff["role"] == "staff" and staff["status"] == "pending"
    again, new = db.upsert_user(conn, 2, "Фарход", "farhod")
    assert not new and again["status"] == "pending"


def test_totals_count_scans_minuses_and_voids(conn):
    me, _ = db.upsert_user(conn, 1, "Владелец", None)
    first = db.add_entry(conn, 1, 3000, 0.9)
    db.add_entry(conn, 1, 2000, 1.1)
    db.add_entry(conn, 1, -500)
    assert db.void_entry(conn, first["id"], me)
    assert not db.void_entry(conn, first["id"], me)  # второй раз отменить нельзя
    t = db.totals(conn, 1)
    assert (t["sum"], t["scans"], t["minuses"], t["minus_sum"], t["voids"]) == (1500, 1, 1, 500, 1)
    assert t["avg"] == pytest.approx(1.0)


def test_staff_cannot_void_someone_elses_entry_but_admin_can(conn):
    admin, _ = db.upsert_user(conn, 1, "Владелец", None)
    db.upsert_user(conn, 2, "Фарход", None)
    staff = db.set_user(conn, 2, status="active")
    mine, theirs = db.add_entry(conn, 1, 1000), db.add_entry(conn, 2, 2000)
    assert not db.void_entry(conn, mine["id"], staff)
    assert db.void_entry(conn, theirs["id"], admin)


def test_new_revision_starts_from_zero_and_keeps_old_entries(conn):
    db.upsert_user(conn, 1, "Владелец", None)
    old = db.current_revision(conn)
    db.add_entry(conn, 1, 3000)
    new = db.new_revision(conn, "Ревизия 2027")
    assert new["id"] != old["id"] and db.totals(conn, 1)["sum"] == 0
    assert len(db.all_entries(conn, old["id"])) == 1


def test_report_has_totals_and_every_entry(conn):
    db.upsert_user(conn, 1, "Владелец", None)
    db.add_entry(conn, 1, 3000, 0.9)
    db.add_entry(conn, 1, -1000)
    data, filename = report.build_xlsx(conn)
    book = load_workbook(io.BytesIO(data))
    assert filename.endswith(".xlsx")
    assert [c.value for c in book["Сотрудники"][4]][:3] == ["Владелец", 1, 2000]
    assert book["Записи"].max_row == 3


# ── запросы мини-аппа ──────────────────────────────────────────────────────

class FakeReader:
    def __init__(self):
        self.answers, self.calls = [], 0

    async def read(self, image_b64):
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeNotifier:
    def __init__(self):
        self.requests, self.decisions, self.reports = [], [], []

    async def access_request(self, user):
        self.requests.append(user["tg_id"])

    async def access_decided(self, user, allowed):
        self.decisions.append((user["tg_id"], allowed))

    async def send_report(self, admin_id, data, filename):
        self.reports.append((admin_id, filename, len(data)))


@pytest.fixture
async def site(tmp_path):
    web_dir = Path(__file__).resolve().parent.parent / "reviziya"
    config = Config(bot_token=TOKEN, anthropic_api_key="x", public_url="https://x.test",
                    data_dir=tmp_path, web_dir=web_dir)
    conn = db.connect(":memory:")
    reader, notifier = FakeReader(), FakeNotifier()
    client = TestClient(TestServer(create_app(config, conn, reader, notifier)))
    await client.start_server()

    async def call(path, user_id=1, name="Владелец", body=None, raw_init=None):
        headers = {"X-Tg-Init-Data": raw_init if raw_init is not None else init_data(user_id, name)}
        response = await client.post("/api/" + path, json=body or {}, headers=headers)
        return response.status, await response.json()

    yield type("Site", (), {"call": staticmethod(call), "reader": reader, "notifier": notifier,
                            "conn": conn, "client": client})
    await client.close()
    conn.close()


async def test_requests_without_a_valid_telegram_signature_are_refused(site):
    assert (await site.call("me", raw_init=""))[0] == 401
    assert (await site.call("me", raw_init=init_data(1, token="999:OTHER")))[0] == 401


async def test_scan_adds_the_price_to_the_persons_total(site):
    site.reader.answers = [(3000, False), (2000, False)]
    status, first = await site.call("scan", body={"image": IMAGE})
    assert status == 200 and first["result"] == "ok" and first["price"] == 3000
    _, second = await site.call("scan", body={"image": IMAGE})
    assert second["totals"]["sum"] == 5000 and second["totals"]["scans"] == 2
    _, profile = await site.call("me")
    assert [e["amt"] for e in profile["log"]] == [2000, 3000]


async def test_unsure_price_is_not_counted_until_confirmed(site):
    site.reader.answers = [(2000, True)]
    _, answer = await site.call("scan", body={"image": IMAGE})
    assert answer["result"] == "unsure" and answer["price"] == 2000
    assert (await site.call("me"))[1]["totals"]["sum"] == 0
    _, confirmed = await site.call("add", body={"price": 2000, "sec": 0.8})
    assert confirmed["totals"]["sum"] == 2000


async def test_unreadable_tag_and_claude_failure_count_nothing(site):
    site.reader.answers = [(0, False), ReaderError("rate")]
    assert (await site.call("scan", body={"image": IMAGE}))[1]["result"] == "none"
    status, answer = await site.call("scan", body={"image": IMAGE})
    assert (status, answer["error"]) == (502, "reader_rate")
    assert (await site.call("me"))[1]["totals"]["sum"] == 0


async def test_bad_image_never_reaches_claude(site):
    for image in (None, "", "не base64!!", "A" * 700_000):
        assert (await site.call("scan", body={"image": image}))[0] in (400, 413)
    assert site.reader.calls == 0


async def test_minus_and_void(site):
    site.reader.answers = [(3000, False)]
    _, scanned = await site.call("scan", body={"image": IMAGE})
    _, after_minus = await site.call("minus", body={"amount": 1000})
    assert after_minus["totals"]["sum"] == 2000
    _, after_void = await site.call("void", body={"id": scanned["entry"]["id"]})
    assert after_void["totals"]["sum"] == -1000 and after_void["totals"]["voids"] == 1
    assert (await site.call("minus", body={"amount": 0}))[0] == 400
    assert (await site.call("void", body={"id": 999}))[0] == 404


async def test_new_person_waits_for_the_admin_and_cannot_scan(site):
    await site.call("me")                                  # владелец входит первым
    status, profile = await site.call("me", user_id=2, name="Фарход")
    assert status == 200 and profile["user"]["status"] == "pending"
    assert site.notifier.requests == [2]
    site.reader.answers = [(3000, False)]
    assert (await site.call("scan", user_id=2, name="Фарход", body={"image": IMAGE}))[0] == 403
    assert site.reader.calls == 0

    _, summary = await site.call("admin/user", body={"id": 2, "status": "active"})
    assert site.notifier.decisions == [(2, True)] and summary["pending"] == []
    _, scanned = await site.call("scan", user_id=2, name="Фарход", body={"image": IMAGE})
    assert scanned["totals"]["sum"] == 3000


async def test_admin_pages_are_closed_to_staff_and_admin_cannot_lock_himself_out(site):
    await site.call("me")
    await site.call("me", user_id=2, name="Фарход")
    await site.call("admin/user", body={"id": 2, "status": "active"})
    assert (await site.call("admin", user_id=2, name="Фарход"))[0] == 403
    assert (await site.call("admin/user", body={"id": 1, "status": "blocked"}))[1]["error"] == "self"


async def test_admin_sees_everyone_and_gets_the_report(site):
    site.reader.answers = [(3000, False), (2000, False)]
    await site.call("scan", body={"image": IMAGE})
    await site.call("me", user_id=2, name="Фарход")
    await site.call("admin/user", body={"id": 2, "status": "active"})
    await site.call("scan", user_id=2, name="Фарход", body={"image": IMAGE})
    _, summary = await site.call("admin")
    assert summary["sum"] == 5000 and [u["name"] for u in summary["users"]] == ["Владелец", "Фарход"]
    assert (await site.call("admin/report"))[1] == {"sent": True}
    assert site.notifier.reports[0][0] == 1

    _, fresh = await site.call("admin/new_revision", body={"title": "Ревизия 2027"})
    assert fresh["sum"] == 0 and fresh["revision"]["title"] == "Ревизия 2027"


async def test_the_page_itself_is_served(site):
    response = await site.client.get("/")
    assert response.status == 200 and "Ревизия" in await response.text()
    assert response.headers["Cache-Control"] == "no-cache"
