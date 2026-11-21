import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sitora import db  # noqa: E402
from sitora.config import Config  # noqa: E402
from sitora.supplier import Supplier  # noqa: E402
from sitora.tg import Bot  # noqa: E402

TOKEN = "123456:TEST-token"


@pytest.fixture
def config(tmp_path):
    c = Config(name="Sitora", bot_token=TOKEN, admin_ids=[999], base_url="https://stars.example.tj",
               db_path=str(tmp_path / "s.db"), fazer_key="k", receipts_dir=str(tmp_path / "r"))
    db.init(c.db_path)
    conn = db.connect(c.db_path)
    for k, v in {"star_usd": "0.015", "star_min": "50", "star_max": "10000", "rate": "11", "markup": "10",
                 "premium": json.dumps([{"months": 3, "price_usd": "12"}, {"months": 6, "price_usd": "16"}]),
                 "gifts": json.dumps([{"id": "g1", "stars": 15, "emoji": "❤"}])}.items():
        db.set_setting(conn, k, v)
    conn.execute("INSERT INTO cards (method, details, created_at) VALUES ('alif', 'Алиф +992 90 000 00 00 Али', 'x')")
    return c


@pytest.fixture
def conn(config):
    return db.connect(config.db_path)


class FakeSupplier:
    """Поставщик: что вернуть на покупку и на проверку статуса."""
    def __init__(self):
        self.buy = {"ok": True, "order": {"id": "F1", "status": "processing"}}
        self.order = {"ok": True, "order": {"id": "F1", "status": "completed"}}
        self.calls, self.fail = [], None

    def transport(self):
        def h(req: httpx.Request):
            self.calls.append((req.method, req.url.path, req.headers.get("Idempotency-Key"),
                               json.loads(req.content or b"{}") if req.method == "POST" else None))
            if self.fail == "net":
                raise httpx.ConnectError("down")
            if self.fail == "reject":
                return httpx.Response(400, json={"ok": False, "error": "user not found"})
            if req.url.path.endswith("/buy"):
                return httpx.Response(200, json=self.buy)
            if "/orders/" in req.url.path:
                return httpx.Response(200, json=self.order)
            if req.url.path.endswith("/balance"):
                return httpx.Response(200, json={"ok": True, "balance": "203.55"})
            return httpx.Response(404, json={"ok": False})
        return httpx.MockTransport(h)


@pytest.fixture
def fake():
    return FakeSupplier()


@pytest.fixture
def supplier(fake):
    return Supplier("k", "https://sup.test/api/v2", transport=fake.transport())


class FakeTg:
    def __init__(self):
        self.calls = []
        self.gift_error = None
        self.file_bytes = __import__("gzip").compress(b'{"v":"5.5.2","fr":60,"ip":0,"op":180,"w":512,"h":512,"layers":[]}')

    def transport(self):
        def h(req: httpx.Request):
            method = req.url.path.rsplit("/", 1)[-1]
            self.calls.append((method, req.content))
            if method == "sendGift" and self.gift_error:
                return httpx.Response(400, json={"ok": False, "error_code": 400, "description": self.gift_error})
            if method in ("sendPhoto", "sendDocument"):
                return httpx.Response(200, json={"ok": True, "result": {"message_id": 7, "photo": [{"file_id": "F"}]}})
            if method == "getFile":
                return httpx.Response(200, json={"ok": True, "result": {"file_path": "stickers/g1.tgs", "file_size": 30}})
            if req.url.path.startswith("/file/"):
                return httpx.Response(200, content=self.file_bytes)
            if method == "getMe":
                return httpx.Response(200, json={"ok": True, "result": {"username": "SitoraTestBot"}})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 5}})
        return httpx.MockTransport(h)

    def methods(self):
        return [m for m, _ in self.calls]


@pytest.fixture
def faketg():
    return FakeTg()


@pytest.fixture
def bot(faketg):
    return Bot(TOKEN, transport=faketg.transport())
