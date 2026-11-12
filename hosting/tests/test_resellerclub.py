"""Клиент ResellerClub (LogicBoxes) на подставных ответах."""
import httpx
import pytest

from app.providers.base import ProviderError
from app.providers.resellerclub import ResellerClub, split_phone


class FakeRC:
    def __init__(self):
        self.calls = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        q = req.url.params
        self.calls.append((req.method, req.url.host, req.url.path, q.multi_items()))
        assert q["auth-userid"] == "111" and q["api-key"] == "key"
        path = req.url.path.removeprefix("/api/")
        if path == "domains/available.json":
            label = q["domain-name"]
            return httpx.Response(200, json={f"{label}.{z}": {"classkey": "x", "status": "available" if z != "net" else "regthroughothers"}
                                             for z in q.get_list("tlds")})
        if path == "contacts/add.json":
            assert q["customer-id"] == "222" and q["type"] == "Contact" and q["phone-cc"] == "992"
            return httpx.Response(200, json=4567)
        if path == "domains/register.json":
            if q["domain-name"] == "broke.com":
                return httpx.Response(500, json={"status": "ERROR", "message": "Insufficient funds in reseller account"})
            assert q.get_list("ns") == ["ns1.x.com", "ns2.x.com"] and q["reg-contact-id"] == "4567"
            assert q["invoice-option"] == "NoInvoice"
            return httpx.Response(200, json={"entityid": "9001", "actionstatus": "Success", "description": q["domain-name"]})
        if path == "domains/details-by-name.json":
            return httpx.Response(200, json={"orderid": "9001", "endtime": "1900000000"})
        if path == "domains/renew.json":
            assert q["order-id"] == "9001" and q["exp-date"] == "1800000000"
            return httpx.Response(200, json={"actionstatus": "Success"})
        if path == "domains/modify-ns.json":
            return httpx.Response(200, json={"actionstatus": "Success"})
        if path == "domains/orderid.json":
            return httpx.Response(200, json=9001)
        if path == "customers/details-by-id.json":
            return httpx.Response(200, json={"customerid": "222", "username": "shop@example.com"})
        return httpx.Response(404, json={"status": "ERROR", "message": "unknown " + path})


@pytest.fixture
def fake():
    return FakeRC()


@pytest.fixture
def rc(fake):
    return ResellerClub("111", "key", "222", test=True, transport=httpx.MockTransport(fake))


def test_check_many_single_request(rc, fake):
    res = rc.check_many("mysite", ["com", "net", "tj"])
    assert res == {"mysite.com": True, "mysite.net": False, "mysite.tj": True}
    assert len(fake.calls) == 1 and fake.calls[0][1] == "test.httpapi.com"


def test_live_uses_domaincheck_host(fake):
    live = ResellerClub("111", "key", "222", test=False, transport=httpx.MockTransport(fake))
    live.check("a.com")
    assert fake.calls[0][1] == "domaincheck.httpapi.com"


def test_contact_register_renew_ns(rc, fake):
    user = {"id": 1, "email": "a@b.c", "name": "Ali", "phone": "992 900123456", "country": "tj", "city": "D",
            "address": "R 1", "zipcode": "734000"}
    cid = rc.ensure_contact(user)
    assert cid == "4567"
    assert rc.ensure_contact({**user, "registrar_contact_id": "77"}) == "77"
    reg = rc.register("mysite.com", 1, cid, ["ns1.x.com", "ns2.x.com"])
    assert reg.order_id == "9001" and reg.expires_at == 1900000000
    assert rc.renew("mysite.com", "9001", 1, 1800000000) == 1900000000
    rc.set_nameservers("mysite.com", "9001", ["a.ns.com", "b.ns.com"])
    assert all(c[0] == "POST" for c in fake.calls if c[2].endswith(("register.json", "renew.json", "modify-ns.json", "add.json")))


def test_errors_translated(rc):
    with pytest.raises(ProviderError) as e:
        rc.register("broke.com", 1, "4567", ["ns1.x.com", "ns2.x.com"])
    assert "недостаточно средств" in e.value.message


def test_ping(rc):
    assert "shop@example.com" in rc.ping() and "тестовый" in rc.ping()


def test_split_phone():
    assert split_phone("992 900123456") == ("992", "900123456")
    assert split_phone("+7 999 1234567") == ("7", "9991234567")


def test_missing_config():
    with pytest.raises(ProviderError):
        ResellerClub("", "k", "c")
