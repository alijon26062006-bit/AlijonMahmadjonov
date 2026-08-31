"""
Профиль специалиста, портфолио и публичный каталог.

Проверяется не «страница открылась», а то, ради чего всё это писалось:
что скрытый профиль не виден, что анкета студии не публикуется никогда,
что чужую работу нельзя ни увидеть, ни изменить, ни удалить.
"""
import re
from urllib.parse import unquote

from conftest import login
from test_fl_auth import csrf_of, form_token, register

from app import specialists, taxonomy
from app.db import connect

PROFILE = "/freelance/profile"


# ============================================================
# Помощники
# ============================================================

def make_specialist(client, email="ivan@example.com", name="Пётр Смирнов",
                    ready=True):
    """Заводит специалиста и, если нужно, заполняет профиль до готового."""
    # Регистрация сама выполняет вход, а вошедшего форма регистрации
    # разворачивает в кабинет — поэтому перед заведением второго
    # человека выходим из первого
    client.cookies.clear()
    register(client, email=email, name=name, role="freelancer")
    with connect() as conn:
        row = conn.execute("SELECT id FROM freelancers WHERE name = ?",
                           (name,)).fetchone()
        fid = row["id"]
        if ready:
            category = conn.execute(
                "SELECT id FROM fl_categories WHERE slug = 'frontend'").fetchone()["id"]
            specialists.save_profile(conn, fid, {
                "title": "Frontend-разработчик",
                "category_id": category,
                "about": "Пишу интерфейсы четвёртый год: магазины, админки "
                         "и внутренние сервисы. Люблю задачи, где важна "
                         "скорость загрузки и понятная вёрстка.",
                "years": "4",
                "city": "Душанбе",
                "rate_hour": 5000,
            })
            taxonomy.set_freelancer_skills(conn, fid, "React, TypeScript, CSS")
        conn.commit()
    return fid


def publish(fid):
    with connect() as conn:
        problem = specialists.set_listing(conn, fid, "published")
        conn.commit()
    assert problem == "", problem


def slug_of(fid):
    with connect() as conn:
        return conn.execute("SELECT public_slug FROM freelancers WHERE id = ?",
                            (fid,)).fetchone()["public_slug"]


# ============================================================
# Деньги
# ============================================================

def test_money_is_read_as_whole_minor_units():
    assert specialists.parse_money("300") == 30000
    assert specialists.parse_money("300,50") == 30050
    assert specialists.parse_money("300.5") == 30050
    assert specialists.parse_money("1 200") == 120000
    assert specialists.parse_money("") is None
    assert specialists.parse_money("много") is None
    assert specialists.parse_money("-5") is None
    assert specialists.parse_money("999999999999") is None


def test_money_is_shown_back_the_same():
    assert specialists.format_money(30000) == "300"
    assert specialists.format_money(30050) == "300,50"
    # Между разрядами неразрывный пробел: иначе «12 000» переносится
    # на две строки и читается как два числа
    assert specialists.format_money(1200000) == "12 000"
    assert specialists.format_money(None) == ""


# ============================================================
# Заполнение профиля
# ============================================================

def test_profile_opens_only_for_specialists(client):
    register(client, role="client", name="ООО Ромашка")
    # У заказчика профиля специалиста нет — не показываем пустые формы
    answer = client.get(PROFILE, follow_redirects=False)
    assert answer.status_code == 303
    assert answer.headers["location"] == "/freelance/dashboard"


def test_profile_is_closed_without_login(client):
    answer = client.get(PROFILE, follow_redirects=False)
    assert answer.status_code == 303
    assert answer.headers["location"].startswith("/freelance/login")


def test_steps_save_what_was_typed(client):
    fid = make_specialist(client, ready=False)
    page = client.get(PROFILE + "/basics")
    csrf = csrf_of(page.text)

    client.post(PROFILE + "/basics", data={
        "csrf": csrf, "name": "Пётр Смирнов", "title": "Frontend-разработчик",
        "city": "Душанбе", "country": "Таджикистан"})
    client.post(PROFILE + "/experience", data={
        "csrf": csrf, "level": "senior", "years": "4",
        "about": "А" * 130, "experience": "Студия «Пример»"})
    client.post(PROFILE + "/terms", data={
        "csrf": csrf, "rate_hour": "300", "rate_project": "5 000",
        "availability": "available", "telegram": "@petr"})

    with connect() as conn:
        row = specialists.by_id(conn, fid)
    assert row["title"] == "Frontend-разработчик"
    assert row["level"] == "senior"
    assert row["rate_hour"] == 30000
    assert row["rate_project_min"] == 500000


def test_form_cannot_change_what_belongs_to_the_studio(client):
    fid = make_specialist(client)
    page = client.get(PROFILE + "/basics")
    csrf = csrf_of(page.text)

    with connect() as conn:
        before = specialists.by_id(conn, fid)

    # Подсовываем поля, которых в форме нет и быть не должно
    client.post(PROFILE + "/basics", data={
        "csrf": csrf, "name": "Пётр", "title": "Frontend",
        "status": "approved", "listing": "published", "login": "petr",
        "completed": "999", "admin_note": "сам себе одобрил"})

    with connect() as conn:
        after = specialists.by_id(conn, fid)
    assert after["status"] == before["status"]
    assert after["listing"] == before["listing"]
    assert after["login"] is None
    assert after["completed"] == before["completed"]
    assert after["admin_note"] == before["admin_note"]


def test_bad_price_is_refused_and_nothing_is_saved(client):
    fid = make_specialist(client)
    csrf = csrf_of(client.get(PROFILE + "/terms").text)
    client.post(PROFILE + "/terms", data={
        "csrf": csrf, "rate_hour": "триста", "availability": "available"})
    with connect() as conn:
        assert specialists.by_id(conn, fid)["rate_hour"] == 5000


def test_steps_need_csrf(client):
    fid = make_specialist(client)
    client.post(PROFILE + "/basics", data={"csrf": "чужое", "title": "Взломщик"})
    with connect() as conn:
        assert specialists.by_id(conn, fid)["title"] == "Frontend-разработчик"


def test_completeness_counts_real_fields(client):
    fid = make_specialist(client, ready=False)
    with connect() as conn:
        empty = specialists.completeness(conn, specialists.by_id(conn, fid))
    assert empty["percent"] < 40

    fid2 = make_specialist(client, email="anna@example.com", name="Анна")
    with connect() as conn:
        filled = specialists.completeness(conn, specialists.by_id(conn, fid2))
    assert filled["percent"] > empty["percent"]
    assert "Фотография" in filled["missing"]


# ============================================================
# Публикация
# ============================================================

def test_empty_profile_cannot_be_sent_for_review(client):
    fid = make_specialist(client, ready=False)
    csrf = csrf_of(client.get(PROFILE).text)
    client.post(PROFILE + "/publish", data={"csrf": csrf, "wanted": "1"})
    with connect() as conn:
        assert specialists.by_id(conn, fid)["listing"] == "draft"


def test_ready_profile_goes_to_review_but_not_to_the_catalogue(client):
    fid = make_specialist(client)
    csrf = csrf_of(client.get(PROFILE).text)
    client.post(PROFILE + "/publish", data={"csrf": csrf, "wanted": "1"})

    with connect() as conn:
        row = specialists.by_id(conn, fid)
        note = conn.execute("SELECT kind FROM notifications").fetchone()
    assert row["listing"] == "pending"
    assert row["public_slug"] is None
    assert note["kind"] == "listing"
    # До проверки человека в каталоге нет
    assert "Пётр Смирнов" not in client.get("/freelance/specialists").text


def test_published_profile_appears_in_the_catalogue(client):
    fid = make_specialist(client)
    publish(fid)
    page = client.get("/freelance/specialists")
    assert "Пётр Смирнов" in page.text
    assert "Frontend-разработчик" in page.text
    card = client.get(f"/freelance/specialists/{slug_of(fid)}")
    assert card.status_code == 200
    assert "Пишу интерфейсы" in card.text


def test_person_can_remove_own_profile_from_the_catalogue(client):
    fid = make_specialist(client)
    publish(fid)
    csrf = csrf_of(client.get(PROFILE).text)
    client.post(PROFILE + "/publish", data={"csrf": csrf, "wanted": "0"})

    assert "Пётр Смирнов" not in client.get("/freelance/specialists").text
    assert client.get(f"/freelance/specialists/{slug_of(fid)}").status_code == 404


def test_contacts_are_never_shown_in_the_catalogue(client):
    fid = make_specialist(client)
    with connect() as conn:
        specialists.save_profile(conn, fid, {"telegram": "@petr_secret",
                                             "email": "petr@example.com"})
        conn.commit()
    publish(fid)
    for url in ("/freelance/specialists", f"/freelance/specialists/{slug_of(fid)}"):
        body = client.get(url).text
        assert "petr_secret" not in body, url
        assert "petr@example.com" not in body, url


def test_studio_application_can_never_be_published(client):
    """Анкета из закрытой базы студии — не профиль площадки."""
    client.post("/freelance/apply", data={
        "name": "Аноним Незаметный", "telegram": "@anon", "skills": "React",
        "about": "Оставил анкету в студию, а не на площадку, и просил её "
                 "никому не показывать."})
    with connect() as conn:
        fid = conn.execute("SELECT id FROM freelancers").fetchone()["id"]
        problem = specialists.set_listing(conn, fid, "published")
        conn.commit()
    assert problem  # публикация не проходит

    # И даже если состояние выставить в базе руками — в каталог не попадёт
    with connect() as conn:
        conn.execute("UPDATE freelancers SET listing = 'published',"
                     " public_slug = 'anon' WHERE id = ?", (fid,))
        conn.commit()
    assert "Незаметный" not in client.get("/freelance/specialists").text
    assert client.get("/freelance/specialists/anon").status_code == 404
    assert "Незаметный" not in client.get("/sitemap.xml").text


def test_suspended_account_disappears_from_the_catalogue(client):
    fid = make_specialist(client)
    publish(fid)
    assert client.get(f"/freelance/specialists/{slug_of(fid)}").status_code == 200
    with connect() as conn:
        conn.execute("UPDATE users SET status = 'suspended'")
        conn.commit()
    assert client.get(f"/freelance/specialists/{slug_of(fid)}").status_code == 404
    assert "Пётр Смирнов" not in client.get("/freelance/specialists").text


def test_sitemap_lists_only_published_profiles(client):
    fid = make_specialist(client)
    body = client.get("/sitemap.xml").text
    assert "/freelance/specialists<" in body.replace("</loc>", "<")
    assert "/freelance/specialists/" not in body

    publish(fid)
    body = client.get("/sitemap.xml").text
    assert f"/freelance/specialists/{slug_of(fid)}" in body


# ============================================================
# Поиск и фильтры
# ============================================================

def test_search_and_filters_narrow_the_catalogue(client):
    first = make_specialist(client)
    publish(first)
    client.cookies.clear()
    second = make_specialist(client, email="anna@example.com", name="Анна Ким")
    with connect() as conn:
        design = conn.execute(
            "SELECT id FROM fl_categories WHERE slug = 'ui-ux'").fetchone()["id"]
        specialists.save_profile(conn, second, {"category_id": design,
                                                "title": "UI/UX дизайнер"})
        taxonomy.set_freelancer_skills(conn, second, "Figma")
        conn.commit()
    publish(second)

    both = client.get("/freelance/specialists").text
    assert "Пётр Смирнов" in both and "Анна Ким" in both

    found = client.get("/freelance/specialists?q=дизайнер").text
    assert "Анна Ким" in found and "Пётр Смирнов" not in found

    with connect() as conn:
        frontend = conn.execute(
            "SELECT id FROM fl_categories WHERE slug = 'frontend'").fetchone()["id"]
    by_category = client.get(f"/freelance/specialists?cat={frontend}").text
    assert "Пётр Смирнов" in by_category and "Анна Ким" not in by_category


def test_percent_in_search_does_not_match_everyone(client):
    fid = make_specialist(client)
    publish(fid)
    # «%» в LIKE — это «что угодно»; без экранирования нашлись бы все
    assert "Пётр Смирнов" not in client.get("/freelance/specialists?q=%").text


# ============================================================
# Портфолио и чужие работы
# ============================================================

def add_work(client, title="Сайт кофейни"):
    csrf = csrf_of(client.get(PROFILE + "/portfolio/new").text)
    client.post(PROFILE + "/portfolio/save", data={
        "csrf": csrf, "title": title, "description": "Сверстал и оживил.",
        "tech": "React"})
    with connect() as conn:
        return conn.execute("SELECT id FROM fl_portfolio WHERE title = ?",
                            (title,)).fetchone()["id"]


def test_work_is_added_and_shown_on_the_card(client):
    fid = make_specialist(client)
    add_work(client)
    publish(fid)
    card = client.get(f"/freelance/specialists/{slug_of(fid)}").text
    assert "Сайт кофейни" in card


def test_someone_elses_work_is_invisible_and_untouchable(client):
    make_specialist(client)
    mine = add_work(client, "Моя работа")
    client.post("/freelance/logout", data={"csrf": csrf_of(client.get(PROFILE).text)})
    client.cookies.clear()

    make_specialist(client, email="anna@example.com", name="Анна Ким")
    csrf = csrf_of(client.get(PROFILE).text)

    # Открыть чужую работу нельзя
    answer = client.get(f"{PROFILE}/portfolio/{mine}", follow_redirects=False)
    assert answer.status_code == 303
    assert "не найдена" in unquote(answer.headers["location"])

    # Изменить — тоже
    client.post(PROFILE + "/portfolio/save", data={
        "csrf": csrf, "id": mine, "title": "Теперь моя"})
    # Удалить — тоже
    client.post(f"{PROFILE}/portfolio/{mine}/delete", data={"csrf": csrf})

    with connect() as conn:
        row = conn.execute("SELECT title FROM fl_portfolio WHERE id = ?",
                           (mine,)).fetchone()
    assert row is not None, "чужая работа удалилась"
    assert row["title"] == "Моя работа", "чужую работу переписали"


def test_work_count_is_capped(client):
    make_specialist(client)
    for n in range(specialists.MAX_PORTFOLIO_ITEMS):
        add_work(client, f"Работа {n}")
    csrf = csrf_of(client.get(PROFILE + "/portfolio/new").text)
    client.post(PROFILE + "/portfolio/save", data={"csrf": csrf, "title": "Лишняя"})
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM fl_portfolio").fetchone()[0]
    assert total == specialists.MAX_PORTFOLIO_ITEMS


# ============================================================
# Проверка профилей в панели
# ============================================================

def test_moderation_page_is_closed_without_login(client):
    answer = client.get("/admin/freelance/specialists", follow_redirects=False)
    assert answer.status_code == 303
    assert answer.headers["location"] == "/admin"


def test_admin_publishes_and_the_log_remembers(client):
    fid = make_specialist(client)
    csrf = csrf_of(client.get(PROFILE).text)
    client.post(PROFILE + "/publish", data={"csrf": csrf, "wanted": "1"})
    client.cookies.clear()

    admin_csrf = login(client)
    client.post(f"/admin/freelance/specialists/{fid}/listing",
                data={"csrf": admin_csrf, "listing": "published"})

    with connect() as conn:
        row = specialists.by_id(conn, fid)
        entry = conn.execute(
            "SELECT action FROM admin_log WHERE action = 'FL_LISTING_CHANGED'"
        ).fetchone()
    assert row["listing"] == "published"
    assert row["public_slug"]
    assert entry is not None


def test_admin_rejection_reaches_the_specialist(client):
    fid = make_specialist(client)
    client.cookies.clear()
    admin_csrf = login(client)
    client.post(f"/admin/freelance/specialists/{fid}/listing",
                data={"csrf": admin_csrf, "listing": "rejected",
                      "note": "Добавьте примеры работ."})
    client.cookies.clear()

    page = client.get("/freelance/login")
    lc = re.search(r'name="fc" value="([^"]+)"', page.text).group(1)
    client.post("/freelance/login", data={"fc": lc, "email": "ivan@example.com",
                                          "password": "ochen-dlinnyy-parol"})
    assert "Добавьте примеры работ" in client.get(PROFILE).text


def test_slug_stays_the_same_after_hiding_and_publishing_again(client):
    fid = make_specialist(client)
    publish(fid)
    first = slug_of(fid)
    with connect() as conn:
        specialists.set_listing(conn, fid, "draft")
        specialists.set_listing(conn, fid, "published")
        conn.commit()
    # По прежнему адресу уже могли дать ссылку — он не меняется
    assert slug_of(fid) == first
