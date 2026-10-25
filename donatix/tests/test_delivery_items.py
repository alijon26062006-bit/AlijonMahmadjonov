"""Подарочные карты: код, PIN и ссылка активации доходят до покупателя — в любом формате ответа поставщика."""
import json

from donatix.orders import delivery_items


def _vals(items):
    return {(i["label"], i["value"]) for i in items}


def test_codes_list_and_message():
    got = delivery_items({"codes": [{"code": "AAAA-BBBB"}, "CCCC"], "message": "Активируйте в приложении"})
    assert ("Код", "AAAA-BBBB") in _vals(got) and ("Код", "CCCC") in _vals(got)
    assert ("Сообщение", "Активируйте в приложении") in _vals(got)


def test_gift_card_with_pin_and_redeem_link():
    got = delivery_items({"cards": [{"card_number": "6011 0000", "pin": "1234", "expires_at": "2027-01-01",
                                     "redeem_url": "https://store.example/redeem?c=1"}], "status": "completed"})
    vals = _vals(got)
    assert ("Номер карты", "6011 0000") in vals and ("PIN", "1234") in vals
    assert ("Действует до", "2027-01-01") in vals
    link = [i for i in got if i["link"]]
    assert link and link[0]["value"] == "https://store.example/redeem?c=1"
    assert not any(i["value"] == "completed" for i in got)      # служебные поля не показываем


def test_unknown_url_key_and_plain_payload():
    assert delivery_items({"data": {"activation": "https://x.example/a"}})[0]["link"] == "1"
    assert delivery_items({"payload": "ZXCV-1234"}) == [{"label": "Код", "value": "ZXCV-1234", "link": ""}]
    assert delivery_items(None) == [] and delivery_items({}) == []


def test_bot_text_shows_link_and_pin():
    from donatix.shopbot import delivery_text
    row = {"delivery_json": json.dumps({"cards": [{"pin": "9999", "redeem_link": "https://r.example/x"}]})}
    text = delivery_text(row)
    assert "PIN" in text and "<code>9999</code>" in text and "https://r.example/x" in text


def test_api_order_has_delivery_items(client, conn, shop, supplier):
    from donatix import catalog, db
    catalog.sync_catalog(conn, supplier)
    r = client.post("/api/v1/orders", headers=shop["h"], json={"product_id": "gc-steam-5", "quantity": 1})
    assert r.status_code in (200, 201), r.text
    oid = r.json()["order"]["order_id"]
    with db.tx(conn):
        conn.execute("UPDATE orders SET status = 'completed', delivery_json = ? WHERE public_id = ?",
                     (json.dumps({"cards": [{"code": "STEAM-123", "url": "https://s.example/r"}]}), oid))
    order = client.get(f"/api/v1/orders/{oid}", headers=shop["h"]).json()["order"]
    assert {"label": "Код", "value": "STEAM-123", "link": ""} in order["delivery_items"]
    assert any(i["link"] and i["value"] == "https://s.example/r" for i in order["delivery_items"])
