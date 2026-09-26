from conftest import make_client, web_login


def test_telegram_section_has_stars_and_premium(client, conn):
    make_client(conn)
    web_login(client, "shop1@example.com", "password123")
    page = client.get("/panel/catalog?kind=telegram").text
    assert "Telegram Stars" in page and "Telegram Premium" in page
    assert "/panel/catalog?kind=telegram_stars" in page and "/panel/catalog?kind=telegram_premium" in page
    assert "нет в наличии" not in page and "/ звезда" in page
    assert 'aria-current="page"' in page and "<span>Telegram</span>" in page
    prem = client.get("/panel/catalog?kind=telegram_premium").text
    assert "Premium" in prem and 'href="/panel/catalog?kind=telegram"' in prem and "tg-premium-3" in prem
