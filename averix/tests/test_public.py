"""Публичная часть: страницы, формы, язык, выдача в поиске."""
from conftest import make_project

from app.db import connect


# ---------- страницы ----------

def test_pages_open(client):
    for url in ("/", "/projects", "/team", "/careers", "/thanks"):
        assert client.get(url).status_code == 200, url


def test_unknown_address_gives_404_in_site_style(client):
    page = client.get("/такой-страницы-нет")
    assert page.status_code == 404
    # именно страница сайта, а не служебная заглушка
    assert "AVERIX" in page.text and "foot" in page.text


def test_draft_project_is_hidden(client):
    make_project(slug="secret", status="draft")
    assert client.get("/projects/secret").status_code == 404
    assert "secret" not in client.get("/projects").text


def test_draft_and_missing_look_the_same(client):
    """По ответу нельзя понять, есть ли скрытый проект с таким адресом."""
    make_project(slug="secret", status="draft")
    hidden = client.get("/projects/secret")
    missing = client.get("/projects/такого-нет")
    assert hidden.status_code == missing.status_code == 404


def test_published_project_is_visible(client):
    make_project(slug="live", title="Живой проект")
    assert "Живой проект" in client.get("/projects").text
    page = client.get("/projects/live")
    assert page.status_code == 200
    assert "Живой проект" in page.text


def test_filter_by_category(client):
    make_project(slug="one")
    assert client.get("/projects?category=web").status_code == 200
    # выдуманная категория не должна ломать страницу
    assert client.get("/projects?category=' OR 1=1--").status_code == 200


# ---------- заявки ----------

def test_request_is_saved(client):
    answer = client.post("/request", data={
        "name": "Иван", "contact": "@ivan",
        "message": "Нужен сайт для кофейни, срок месяц.",
    }, follow_redirects=False)
    assert answer.status_code == 303
    assert answer.headers["location"] == "/thanks?kind=request"
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM client_requests").fetchone()[0] == 1


def test_request_without_contact_is_rejected(client):
    answer = client.post("/request", data={
        "name": "Иван", "contact": "", "message": "Нужен сайт для кофейни.",
    })
    assert answer.status_code == 400
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM client_requests").fetchone()[0] == 0


def test_honeypot_silently_drops_spam(client):
    answer = client.post("/request", data={
        "name": "Бот", "contact": "@bot", "message": "Спам спам спам спам.",
        "website": "http://spam.example",
    }, follow_redirects=False)
    # роботу отвечаем как человеку, но в базу не пишем
    assert answer.status_code == 303
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM client_requests").fetchone()[0] == 0


def test_too_many_requests_from_one_address(client):
    data = {"name": "Иван", "contact": "@ivan", "message": "Нужен сайт для кофейни."}
    for _ in range(3):
        client.post("/request", data=data)
    client.post("/request", data=data)
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM client_requests").fetchone()[0] == 3


def test_unknown_project_type_falls_back(client):
    client.post("/request", data={
        "name": "Иван", "contact": "@ivan", "message": "Нужен сайт для кофейни.",
        "project_type": "выдумка",
    })
    with connect() as conn:
        assert conn.execute("SELECT project_type FROM client_requests").fetchone()[0] == "other"


# ---------- отклики ----------

def test_application_is_saved(client):
    answer = client.post("/apply", data={
        "name": "Пётр", "telegram": "@petr",
        "message": "Пишу на React два года, хочу в студию.",
    }, follow_redirects=False)
    assert answer.status_code == 303
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM job_applications").fetchone()[0] == 1


def test_application_to_closed_vacancy_loses_link(client):
    with connect() as conn:
        conn.execute("INSERT INTO vacancies (title_ru, status) VALUES ('Закрытая', 'closed')")
        conn.commit()
        vid = conn.execute("SELECT id FROM vacancies").fetchone()["id"]
    client.post("/apply", data={
        "name": "Пётр", "telegram": "@petr", "vacancy_id": str(vid),
        "message": "Пишу на React два года, хочу в студию.",
    })
    with connect() as conn:
        assert conn.execute("SELECT vacancy_id FROM job_applications").fetchone()[0] is None


def test_short_story_is_rejected(client):
    answer = client.post("/apply", data={
        "name": "Пётр", "telegram": "@petr", "message": "привет",
    })
    assert answer.status_code == 400
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM job_applications").fetchone()[0] == 0


# ---------- язык ----------

def test_language_comes_from_cookie(client):
    with connect() as conn:
        conn.execute("UPDATE site_settings SET value_tj = 'Хуҷанд' WHERE key = 'city'")
        conn.commit()
    assert "Душанбе" in client.get("/").text
    client.cookies.set("averix-lang", "tg")
    tj = client.get("/")
    assert "Хуҷанд" in tj.text
    assert 'lang="tg"' in tj.text


def test_empty_tajik_falls_back_to_russian(client):
    with connect() as conn:
        conn.execute("UPDATE site_settings SET value_tj = '' WHERE key = 'city'")
        conn.commit()
    client.cookies.set("averix-lang", "tg")
    assert "Душанбе" in client.get("/").text


# ---------- поисковики ----------

def test_robots_closes_admin(client):
    body = client.get("/robots.txt").text
    assert "Disallow: /admin" in body
    assert "Sitemap: https://averix.dev/sitemap.xml" in body


def test_sitemap_lists_only_published(client):
    make_project(slug="live")
    make_project(slug="hidden", status="draft")
    body = client.get("/sitemap.xml").text
    assert "https://averix.dev/projects/live" in body
    assert "hidden" not in body


def test_project_can_be_closed_from_search(client):
    make_project(slug="private")
    with connect() as conn:
        conn.execute("UPDATE projects SET allow_indexing = 0 WHERE slug = 'private'")
        conn.commit()
    assert "private" not in client.get("/sitemap.xml").text
    assert "noindex" in client.get("/projects/private").text


def test_pages_have_canonical_and_open_graph(client):
    page = client.get("/projects").text
    assert '<link rel="canonical" href="https://averix.dev/projects">' in page
    assert 'property="og:title"' in page
    assert 'property="og:image"' in page


def test_thanks_page_is_not_indexed(client):
    assert "noindex" in client.get("/thanks").text
