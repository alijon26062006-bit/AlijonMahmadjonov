import pytest

from app.cloudinit import build_user_data
from app.security import generate_root_password, hash_password, root_password_problems, verify_password
from app.services import _downsample
from app.validators import ValidationError, normalize_domain, validate_record, validate_server_name


def test_password_hashing():
    h = hash_password("secret-123")
    assert verify_password("secret-123", h)
    assert not verify_password("secret-124", h)
    assert not verify_password("x", "garbage")


def test_root_password_policy():
    assert root_password_problems("Str0ng!Root#Pass") == []
    assert "не короче 12 символов" in root_password_problems("Aa1!")
    assert root_password_problems("aaaaaaaaaaaaaa")  # нет заглавных, цифр, символов
    assert root_password_problems("Str0ng!Root#Pass'")  # кавычка не разрешена
    assert root_password_problems("Пароль1!Пароль")  # кириллица не разрешена
    for _ in range(50):
        assert root_password_problems(generate_root_password()) == []


@pytest.mark.parametrize("raw,expected", [
    ("Example.COM", "example.com"),
    ("https://www.example.com/path", "example.com"),
    ("пример.рф", "xn--e1afmkfd.xn--p1ai"),
])
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize("raw", ["", "localhost", "-bad.com", "a..b.com", "exa mple.com"])
def test_normalize_domain_rejects(raw):
    with pytest.raises(ValidationError):
        normalize_domain(raw)


def test_server_name():
    assert validate_server_name(" Web-01 ") == "web-01"
    with pytest.raises(ValidationError):
        validate_server_name("web_01")


@pytest.mark.parametrize("args,expected", [
    (("a", "WWW", "203.0.113.5", 300), ("A", "www", "203.0.113.5", 300)),
    (("AAAA", "@", "2001:DB8:0::1", 3600), ("AAAA", "@", "2001:db8::1", 3600)),
    (("CNAME", "shop", "Example.com.", 3600), ("CNAME", "shop", "example.com", 3600)),
    (("TXT", "@", '"v=spf1 -all"', 3600), ("TXT", "@", "v=spf1 -all", 3600)),
    (("SRV", "_sip._tcp", "10 5 5060 sip.example.com", 3600), ("SRV", "_sip._tcp", "10 5 5060 sip.example.com", 3600)),
    (("CAA", "@", "0 issue letsencrypt.org", 3600), ("CAA", "@", '0 issue "letsencrypt.org"', 3600)),
    (("A", "*.app", "203.0.113.5", 60), ("A", "*.app", "203.0.113.5", 60)),
])
def test_validate_record_ok(args, expected):
    assert validate_record(*args) == expected


@pytest.mark.parametrize("args,field", [
    (("A", "@", "2001:db8::1", 3600), "value"),
    (("AAAA", "@", "1.2.3.4", 3600), "value"),
    (("MX", "@", "mail.example.com", 3600), "value"),
    (("CNAME", "@", "example.com", 3600), "name"),
    (("A", "bad name", "1.2.3.4", 3600), "name"),
    (("A", "@", "1.2.3.4", 7), "ttl"),
    (("PTR", "@", "x", 3600), "type"),
    (("TXT", "@", 'a"b', 3600), "value"),
])
def test_validate_record_errors(args, field):
    with pytest.raises(ValidationError) as e:
        validate_record(*args)
    assert e.value.field == field


def test_cloud_init_contains_agent_and_config():
    ud = build_user_data("https://panel.example.com", 7, "tok123")
    assert ud.startswith("#cloud-config") and "ssh_pwauth: true" in ud
    assert "averix-agent.service" in ud and "tok123" not in ud  # токен только внутри base64
    import base64
    import re
    blobs = [base64.b64decode(b).decode() for b in re.findall(r"content: (\S+)", ud)]
    assert any("TOKEN=tok123" in b and "SERVER_ID=7" in b for b in blobs)
    assert len(ud.encode()) < 32 * 1024  # лимит Hetzner на user_data


def test_downsample():
    pts = [[0, 10], [30, 20], [60, 30], [90, 50]]
    assert _downsample(pts, 60) == [[0, 15.0], [60, 40.0]]
    assert _downsample(pts, 30) == pts
