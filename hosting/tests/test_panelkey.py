"""Заказ через «настоящего» провайдера: ключ панели вместо пароля Hetzner."""
from app.catalog import Catalog
from app.notify import Notifier
from app.providers import Providers
from app.providers.demo import DemoDns, DemoRegistrar, DemoVps
from app.services import Hosting


class KeyedVps(DemoVps):
    name = "hetzner"  # ведёт себя как настоящий провайдер: пароль ставится по SSH

    def __init__(self):
        super().__init__()
        self.BOOT_SECONDS = 0
        self.keys_registered = []
        self.created_with = None

    def ensure_ssh_key(self, name, public_key):
        self.keys_registered.append((name, public_key))
        return name

    def create_server(self, **kw):
        self.created_with = kw.get("ssh_keys")
        created = super().create_server(**kw)
        created.root_password = None  # с ключом Hetzner пароль не выдаёт
        return created


def test_order_uses_panel_key_and_sets_password(settings, db, tmp_path, monkeypatch):
    settings.database_path = str(tmp_path / "hosting.db")
    vps = KeyedVps()
    h = Hosting(settings, db, Catalog.load(), Providers(vps, DemoDns(), DemoRegistrar(resolve=False)),
                run_async=lambda fn, *a: fn(*a), notifier=Notifier(settings, background=False))
    calls = []

    def fake_set(host, current, new, **kw):
        calls.append((host, current, new, kw.get("pkey") is not None))
        return "ssh-rsa HOSTKEY"
    monkeypatch.setattr("app.services.set_root_password", fake_set)
    uid = db.run("INSERT INTO users(email, pw_hash, balance_cents, verified, created_at) VALUES ('a@b.c', 'x', 5000, 1, 0)")
    user = db.one("SELECT * FROM users WHERE id = ?", (uid,))
    row, shown = h.order_server(user, plan_id="start", location="fsn1", image="ubuntu-24.04", name="web-01", root_password=None)
    assert vps.created_with and vps.created_with[0].startswith("averix-panel-")
    assert len(vps.keys_registered) == 1 and vps.keys_registered[0][1].startswith("ssh-rsa ")
    assert (tmp_path / "panel_ssh_key").exists()
    assert shown and len(shown) >= 16  # сгенерированный пароль показан клиенту
    assert calls == [(row["ipv4"], None, shown, True)]  # вход по ключу панели, без пароля Hetzner
    assert db.one("SELECT password_state FROM servers WHERE id = ?", (row["id"],))["password_state"] == "applied"
    # второй заказ не регистрирует ключ заново
    h.order_server(user, plan_id="start", location="fsn1", image="ubuntu-24.04", name="web-02", root_password=None)
    assert len(vps.keys_registered) == 1
