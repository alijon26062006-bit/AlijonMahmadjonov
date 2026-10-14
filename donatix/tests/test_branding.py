"""Сайт явно независимый: дисклеймер на всех страницах, нет логотипов правообладателей, только ID — без пароля."""

import re

from conftest import web_login
from fastapi.testclient import TestClient

RU = "не являемся официальным сайтом, партнёром или"
EN = "is not affiliated with, endorsed by, or an official"


def test_disclaimer_on_public_and_panel_pages(app, conn):
    from donatix import accounts
    guest = TestClient(app)
    for url in ("/", "/login", "/register", "/terms", "/privacy", "/reviews", "/docs", "/panel/catalog?kind=topup"):
        html = guest.get(url).text
        text = " ".join(re.sub(r"<[^>]+>", " ", html).split())
        assert RU in text and EN in text, url
    accounts.create_user(conn, email="b@example.com", login="brand", password="password123", status="active")
    c = TestClient(app)
    web_login(c, "b@example.com", "password123")
    text = " ".join(re.sub(r"<[^>]+>", " ", c.get("/panel").text).split())
    assert RU in text


def test_no_supplier_logos_and_id_only_notice(app, conn):
    conn.execute("UPDATE products SET image_url = 'https://cdn.example/garena-ff-logo.png' WHERE kind = 'topup'")
    pid = conn.execute("SELECT id FROM products WHERE kind = 'topup' AND active = 1 LIMIT 1").fetchone()["id"]
    guest = TestClient(app)
    for url in ("/", "/panel/catalog?kind=topup", f"/panel/buy/{pid}"):
        assert "garena-ff-logo" not in guest.get(url).text, url
    buy = guest.get(f"/panel/buy/{pid}").text
    assert "Вводите только ID игрока, никогда не вводите" in buy and "Неофициальный реселлер" in buy


def test_no_official_wording_and_terms_section(app):
    guest = TestClient(app)
    for url in ("/", "/panel/catalog?kind=topup", "/panel/catalog?kind=telegram", "/terms"):
        html = guest.get(url).text
        head = html.split("</head>")[0]
        assert not re.search(r"официальн|official|garena top ?up", head, re.I), url   # title, description, og
    terms = guest.get("/terms").text
    assert 'id="trademarks"' in terms and "товарные знаки" in terms and "никогда" in terms
