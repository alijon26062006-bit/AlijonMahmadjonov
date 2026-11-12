import pytest
from fastapi.testclient import TestClient

from app.catalog import Catalog
from app.config import Settings
from app.db import Database
from app.main import create_app
from app.providers import Providers
from app.providers.demo import DemoDns, DemoRegistrar, DemoVps
from app.notify import Notifier
from app.services import Hosting


@pytest.fixture
def settings():
    return Settings(admin_email="boss@example.com", demo_payments=True,
                    payment_methods=["Алиф", "Душанбе Сити"], payment_instructions="Карта 0000 0000 0000 0000")


@pytest.fixture
def db():
    return Database(":memory:")


@pytest.fixture
def providers():
    vps = DemoVps()
    vps.BOOT_SECONDS = 0
    return Providers(vps=vps, dns=DemoDns(), registrar=DemoRegistrar(resolve=False))


@pytest.fixture
def hosting(settings, db, providers):
    return Hosting(settings, db, Catalog.load(), providers, run_async=lambda fn, *a: fn(*a), demo_password_delay=0,
                   notifier=Notifier(settings, background=False))


@pytest.fixture
def client(settings, db, hosting):
    app = create_app(settings, db, hosting, start_billing=False)
    with TestClient(app) as c:
        yield c


class Api:
    """Клиент как в браузере: куки сессии + заголовки CSRF."""

    def __init__(self, client: TestClient):
        self.c = client
        self.csrf = ""

    def _h(self):
        return {"X-Requested-With": "fetch", "X-CSRF-Token": self.csrf}

    def get(self, url, **kw):
        return self.c.get(url, headers=self._h(), **kw)

    def post(self, url, json=None):
        return self.c.post(url, json=json or {}, headers=self._h())

    def delete(self, url):
        return self.c.delete(url, headers=self._h())

    def signup(self, email="user@example.com", password="account-pass-1"):
        r = self.post("/api/auth/register", {"email": email, "password": password, "name": "Alijon"})
        assert r.status_code == 200, r.text
        self.csrf = self.get("/api/me").json()["csrf"]
        return self


@pytest.fixture
def api(client):
    return Api(client)
