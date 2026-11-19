import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789-abcdefghijklmnop")
os.environ.setdefault("ADMIN_EMAILS", "boss@example.com")
os.environ.setdefault("DEFAULT_MARKUP_PERCENT", "10")
TEST_DB = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test.db")
os.environ["DATABASE_URL"] = TEST_DB

import pytest  # noqa: E402
import respx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as dbmod  # noqa: E402
from app.db import Base  # noqa: E402
from app.main import create_app  # noqa: E402
from app.routers import auth as auth_router  # noqa: E402
from app.supplier import SupplierClient, set_supplier  # noqa: E402

SUPPLIER = "https://supplier.test"
API_KEY = "fc_test_secret_key_value"


@pytest.fixture
def engine():
    eng = dbmod.init_engine(TEST_DB)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def mock():
    with respx.mock(base_url=SUPPLIER + "/api/v2", assert_all_called=False) as m:
        yield m


@pytest.fixture
def client(engine, mock):
    set_supplier(SupplierClient(SUPPLIER, API_KEY))
    auth_router._FAILS.clear()
    with TestClient(create_app()) as c:
        yield c
    set_supplier(None)


def register(c, email="user@example.com", username="user1", password="password123"):
    return c.post("/api/auth/register", json={"email": email, "username": username, "password": password})
