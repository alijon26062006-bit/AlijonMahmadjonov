"""
Справочники площадки: категории и навыки.

Главное, что здесь проверяется, — что справочник не превращается
в свалку из разных написаний одного слова и что слияние дубликатов
не теряет людей.
"""
from conftest import login

from app import taxonomy
from app.db import connect


def skill_names():
    with connect() as conn:
        return [s["name"] for s in taxonomy.skills(conn)]


def test_seed_gives_two_levels_of_categories(client):
    with connect() as conn:
        tree = taxonomy.category_tree(conn)
    names = [t["name"] for t in tree]
    assert "Разработка" in names
    development = next(t for t in tree if t["name"] == "Разработка")
    assert any(c["name"] == "Frontend" for c in development["children"])


def test_same_word_in_any_case_is_one_skill(client):
    with connect() as conn:
        first = taxonomy.find_or_create_skill(conn, "React")
        second = taxonomy.find_or_create_skill(conn, "react")
        third = taxonomy.find_or_create_skill(conn, "  REACT ")
        conn.commit()
    assert first == second == third


def test_new_skill_waits_for_a_human(client):
    with connect() as conn:
        skill_id = taxonomy.find_or_create_skill(conn, "Совершенно новый навык")
        row = taxonomy.get_skill(conn, skill_id)
        visible = [s["id"] for s in taxonomy.visible_skills(conn)]
        conn.commit()
    assert row["status"] == "pending"
    # В анкете он работает, в фильтрах каталога — ещё нет
    assert skill_id not in visible


def test_meaningless_name_does_not_become_a_skill(client):
    with connect() as conn:
        assert taxonomy.find_or_create_skill(conn, "!!!") is None
        assert taxonomy.find_or_create_skill(conn, "") is None
        assert taxonomy.find_or_create_skill(conn, "R") is None


def test_person_skills_are_saved_and_capped(client):
    with connect() as conn:
        conn.execute("INSERT INTO freelancers (name) VALUES ('Пётр')")
        fid = conn.execute("SELECT id FROM freelancers").fetchone()["id"]
        saved = taxonomy.set_freelancer_skills(
            conn, fid, "React, react, TypeScript, , Node.js")
        conn.commit()
    # Повтор в разном регистре схлопывается в один
    assert sorted(s["name"] for s in saved) == ["Node.js", "React", "TypeScript"]

    with connect() as conn:
        many = ", ".join(f"Навык{n}" for n in range(30))
        saved = taxonomy.set_freelancer_skills(conn, fid, many)
        conn.commit()
    assert len(saved) == taxonomy.MAX_SKILLS_PER_PERSON


def test_merge_moves_people_and_hides_the_duplicate(client):
    with connect() as conn:
        conn.execute("INSERT INTO freelancers (name) VALUES ('Пётр')")
        conn.execute("INSERT INTO freelancers (name) VALUES ('Анна')")
        petr, anna = [r["id"] for r in conn.execute("SELECT id FROM freelancers ORDER BY id")]
        taxonomy.set_freelancer_skills(conn, petr, "React.js")
        taxonomy.set_freelancer_skills(conn, anna, "React.js, React")

        source = taxonomy.find_or_create_skill(conn, "React.js")
        target = taxonomy.find_or_create_skill(conn, "React")
        assert taxonomy.merge_skills(conn, source, target) == ""
        conn.commit()

        petr_skills = [s["name"] for s in taxonomy.freelancer_skills(conn, petr)]
        anna_skills = [s["name"] for s in taxonomy.freelancer_skills(conn, anna)]
        hidden = taxonomy.get_skill(conn, source)

    # Никто не потерял навык, и ни у кого он не задвоился
    assert petr_skills == ["React"]
    assert anna_skills == ["React"]
    assert hidden["status"] == "hidden"
    assert hidden["merged_into_id"] == target


def test_merged_skill_is_never_assigned_again(client):
    with connect() as conn:
        source = taxonomy.find_or_create_skill(conn, "React.js")
        target = taxonomy.find_or_create_skill(conn, "React")
        taxonomy.merge_skills(conn, source, target)
        # Человек пишет старое написание — попадает в конечный навык
        again = taxonomy.find_or_create_skill(conn, "React.js")
        conn.commit()
    assert again == target


def test_skill_cannot_be_merged_with_itself(client):
    with connect() as conn:
        one = taxonomy.find_or_create_skill(conn, "React")
        assert taxonomy.merge_skills(conn, one, one) != ""


def test_category_is_switched_off_together_with_children(client):
    with connect() as conn:
        top = next(c for c in taxonomy.categories(conn) if c["name"] == "Дизайн")
        taxonomy.set_category_enabled(conn, top["id"], False)
        conn.commit()
        left = [c["name"] for c in taxonomy.categories(conn)]
    assert "Дизайн" not in left
    assert "UI/UX" not in left


def test_subcategory_cannot_be_nested_deeper(client):
    with connect() as conn:
        child = next(c for c in taxonomy.categories(conn) if c["name"] == "Frontend")
        new_id, problem = taxonomy.save_category(conn, None, "Ещё глубже", child["id"])
    assert new_id is None
    assert problem


# ============================================================
# Админка справочников
# ============================================================

def test_taxonomy_pages_are_closed_without_login(client):
    for url in ("/admin/freelance", "/admin/freelance/categories",
                "/admin/freelance/skills"):
        answer = client.get(url, follow_redirects=False)
        assert answer.status_code == 303, url
        assert answer.headers["location"] == "/admin"


def test_admin_can_add_and_approve_a_skill(client):
    csrf = login(client)
    client.post("/admin/freelance/skills",
                data={"csrf": csrf, "name": "Rust"})
    with connect() as conn:
        row = conn.execute("SELECT * FROM fl_skills WHERE slug = 'rust'").fetchone()
    # Заведённый администратором навык проверять не нужно
    assert row["status"] == "active"


def test_skill_changes_need_csrf(client):
    login(client)
    client.post("/admin/freelance/skills", data={"csrf": "чужое", "name": "Rust"})
    with connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM fl_skills WHERE slug = 'rust'").fetchone()[0] == 0


def test_admin_merge_leaves_a_record_in_the_log(client):
    csrf = login(client)
    with connect() as conn:
        source = taxonomy.find_or_create_skill(conn, "React.js")
        target = taxonomy.find_or_create_skill(conn, "React")
        conn.commit()
    client.post("/admin/freelance/skills/merge",
                data={"csrf": csrf, "source_id": source, "target_id": target})
    with connect() as conn:
        row = conn.execute(
            "SELECT action, entity FROM admin_log WHERE action = 'FL_TAXONOMY_CHANGED'"
        ).fetchone()
        merged = taxonomy.get_skill(conn, source)
    assert row is not None
    assert row["entity"] == "fl_skills"
    assert merged["status"] == "hidden"


def test_hub_shows_only_real_numbers(client):
    login(client)
    page = client.get("/admin/freelance")
    assert page.status_code == 200
    # Учётных записей нет — значит ноль, а не красивое число
    assert ">0<" in page.text.replace(" ", "").replace("\n", "")
