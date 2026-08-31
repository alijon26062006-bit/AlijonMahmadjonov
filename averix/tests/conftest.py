"""
Общая подготовка для тестов.

База и загрузки создаются во временной папке: тесты никогда не трогают
данные с сервера и не оставляют мусора.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="averix-tests-")
os.environ["AVERIX_DATA_DIR"] = _TMP
os.environ["AVERIX_ALLOW_INSECURE"] = "1"
os.environ["AVERIX_SECURE_COOKIES"] = "0"
os.environ["AVERIX_SITE_URL"] = "https://averix.dev"

from fastapi.testclient import TestClient  # noqa: E402

from app import security  # noqa: E402
from app.db import connect  # noqa: E402
from app.main import app  # noqa: E402

ADMIN_LOGIN = "tester"
ADMIN_PASSWORD = "Test-Pass-9137!"


@pytest.fixture
def client():
    with TestClient(app) as c:
        with connect() as conn:
            conn.execute("DELETE FROM admins")
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM login_attempts")
            conn.execute("DELETE FROM projects")
            conn.execute("DELETE FROM team_members")
            conn.execute("DELETE FROM vacancies")
            conn.execute("DELETE FROM client_requests")
            conn.execute("DELETE FROM job_applications")
            conn.execute("DELETE FROM freelancers")
            conn.execute("DELETE FROM freelancer_sessions")
            conn.execute("DELETE FROM client_projects")
            conn.execute("DELETE FROM tasks")
            conn.execute("DELETE FROM task_history")
            conn.execute("DELETE FROM notifications")
            conn.execute("DELETE FROM admin_log")
            conn.execute("DELETE FROM user_sessions")
            conn.execute("DELETE FROM user_tokens")
            conn.execute("DELETE FROM client_profiles")
            conn.execute("DELETE FROM fl_rate_events")
            conn.execute("DELETE FROM users")
            conn.execute(
                "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                (ADMIN_LOGIN, security.hash_password(ADMIN_PASSWORD)),
            )
            conn.commit()
        yield c


@pytest.fixture
def db():
    return connect


def login(client) -> str:
    """Проходит вход и возвращает csrf-токен сессии."""
    import re

    page = client.get("/admin")
    lc = re.search(r'name="lc" value="([^"]+)"', page.text).group(1)
    done = client.post(
        "/admin/login",
        data={"username": ADMIN_LOGIN, "password": ADMIN_PASSWORD, "lc": lc},
        follow_redirects=True,
    )
    assert done.status_code == 200
    return re.search(r'name="csrf" value="([^"]+)"', done.text).group(1)


def make_project(slug="demo", status="published", featured=1, title="Проект"):
    with connect() as conn:
        conn.execute(
            "INSERT INTO projects (slug, category, year, title_ru, excerpt_ru,"
            " task_ru, status, featured) VALUES (?, 'web', 2025, ?, 'Описание.',"
            " 'Задача.', ?, ?)",
            (slug, title, status, featured),
        )
        conn.commit()
        return conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()["id"]
