"""Клиент Hetzner Cloud на подставных ответах (без сети и без ключа)."""
import json

import httpx
import pytest

from app.providers.base import ProviderError
from app.providers.hetzner import HetznerClient, HetznerDns, HetznerVps


class FakeHetzner:
    def __init__(self):
        self.calls = []
        self.rrsets = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/v1")
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, path, body, dict(request.url.params)))
        assert request.headers["Authorization"] == "Bearer test-token"
        m = request.method

        if m == "POST" and path == "/servers":
            return httpx.Response(201, json={
                "server": {"id": 42, "status": "initializing",
                           "public_net": {"ipv4": {"ip": "198.51.100.7"}, "ipv6": {"ip": "2001:db8:1::/64"}}},
                "action": {"id": 1, "status": "running"}, "root_password": "TempPass123"})
        if m == "GET" and path == "/servers/42":
            return httpx.Response(200, json={"server": {"id": 42, "status": "running",
                                                        "public_net": {"ipv4": {"ip": "198.51.100.7"}, "ipv6": {"ip": "2001:db8:1::/64"}}}})
        if m == "GET" and path == "/servers/404":
            return httpx.Response(404, json={"error": {"code": "not_found", "message": "server not found"}})
        if m == "POST" and path.startswith("/servers/42/actions/"):
            if path.endswith("reset_password"):
                return httpx.Response(201, json={"action": {"id": 2}, "root_password": "ResetPw987"})
            return httpx.Response(201, json={"action": {"id": 3, "status": "running"}})
        if m == "GET" and path == "/servers/42/metrics":
            return httpx.Response(200, json={"metrics": {"start": "x", "end": "y", "step": 60, "time_series": {
                "cpu": {"values": [[1700000000, "12.5"], [1700000060, "13.0"]]},
                "network.0.bandwidth.in": {"values": [[1700000000, "1000"]]},
                "unknown.series": {"values": [[1700000000, "1"]]},
            }}})
        if m == "POST" and path == "/servers/99/actions/poweron":
            return httpx.Response(429, json={"error": {"code": "rate_limit_exceeded", "message": "limit"}})

        # DNS
        if path == "/zones/example.com" and m == "GET":
            return httpx.Response(404, json={"error": {"code": "not_found", "message": "zone not found"}})
        if path == "/zones" and m == "POST":
            return httpx.Response(201, json={"zone": {"id": 1, "name": body["name"]}})
        if path.startswith("/zones/example.com/rrsets"):
            rest = path.removeprefix("/zones/example.com/rrsets").strip("/")
            if m == "POST" and rest == "":
                self.rrsets[(body["name"], body["type"])] = body
                return httpx.Response(201, json={"rrset": body})
            parts = rest.split("/")
            key = (parts[0], parts[1])
            if m == "GET":
                if key in self.rrsets:
                    return httpx.Response(200, json={"rrset": self.rrsets[key]})
                return httpx.Response(404, json={"error": {"code": "not_found", "message": "nope"}})
            if m == "POST" and parts[-1] == "set_records":
                self.rrsets[key]["records"] = body["records"]
                return httpx.Response(201, json={"action": {"id": 9}})
            if m == "POST" and parts[-1] == "change_ttl":
                self.rrsets[key]["ttl"] = body["ttl"]
                return httpx.Response(201, json={"action": {"id": 10}})
            if m == "DELETE":
                self.rrsets.pop(key, None)
                return httpx.Response(201, json={"action": {"id": 11}})
        return httpx.Response(500, json={"error": {"code": "unexpected", "message": f"{m} {path}"}})


@pytest.fixture
def fake():
    return FakeHetzner()


@pytest.fixture
def client(fake):
    return HetznerClient("test-token", "https://api.hetzner.cloud/v1", transport=httpx.MockTransport(fake))


def test_create_server_sends_expected_body(client, fake):
    vps = HetznerVps(client)
    res = vps.create_server(name="web-01-7", server_type="cx23", image="ubuntu-24.04", location="fsn1",
                            user_data="#cloud-config\n", labels={"panel_server": "7"})
    assert res.provider_id == "42" and res.status == "creating" and res.root_password == "TempPass123"
    method, path, body, _ = fake.calls[0]
    assert (method, path) == ("POST", "/servers")
    assert body["server_type"] == "cx23" and body["location"] == "fsn1" and body["start_after_create"] is True
    assert body["user_data"].startswith("#cloud-config")


def test_get_server_maps_status_and_ipv6(client):
    st = HetznerVps(client).get_server("42")
    assert st.status == "running" and st.ipv4 == "198.51.100.7" and st.ipv6 == "2001:db8:1::1"


def test_power_actions_map_to_hetzner(client, fake):
    vps = HetznerVps(client)
    vps.power("42", "start")
    vps.power("42", "stop")
    vps.power("42", "reboot")
    assert [c[1] for c in fake.calls] == ["/servers/42/actions/poweron", "/servers/42/actions/shutdown",
                                          "/servers/42/actions/reboot"]


def test_reset_password_returns_password(client):
    assert HetznerVps(client).reset_password("42") == "ResetPw987"


def test_metrics_parsing(client, fake):
    m = HetznerVps(client).metrics("42", 1700000000, 1700003600, 60)
    assert m.series["cpu"] == [[1700000000.0, 12.5], [1700000060.0, 13.0]]
    assert m.series["net_bps_in"] == [[1700000000.0, 1000.0]]
    assert "unknown.series" not in m.series
    params = fake.calls[0][3]
    assert params["type"] == "cpu,disk,network" and params["start"] == "2023-11-14T22:13:20Z"


def test_errors_are_translated(client):
    with pytest.raises(ProviderError) as e:
        HetznerVps(client).get_server("404")
    assert e.value.code == "not_found" and e.value.status == 404
    with pytest.raises(ProviderError) as e:
        HetznerVps(client).power("99", "start")
    assert e.value.status == 429 and "лимит" in e.value.message


def test_network_error():
    def boom(_):
        raise httpx.ConnectError("down")
    c = HetznerClient("test-token", transport=httpx.MockTransport(boom))
    with pytest.raises(ProviderError) as e:
        HetznerVps(c).get_server("42")
    assert e.value.code == "network"


def test_dns_zone_and_rrsets(client, fake):
    dns = HetznerDns(client)
    dns.ensure_zone("example.com")
    assert ("POST", "/zones") in [(c[0], c[1]) for c in fake.calls]

    dns.set_rrset("example.com", "@", "A", 3600, ["203.0.113.1"])
    assert fake.rrsets[("@", "A")]["records"] == [{"value": "203.0.113.1"}]
    dns.set_rrset("example.com", "@", "A", 300, ["203.0.113.1", "203.0.113.2"])
    assert fake.rrsets[("@", "A")]["records"] == [{"value": "203.0.113.1"}, {"value": "203.0.113.2"}]
    assert fake.rrsets[("@", "A")]["ttl"] == 300

    dns.set_rrset("example.com", "@", "TXT", 3600, ["v=spf1 -all"])
    assert fake.rrsets[("@", "TXT")]["records"] == [{"value": '"v=spf1 -all"'}]
    dns.set_rrset("example.com", "@", "MX", 3600, ["10 mail.example.com"])
    assert fake.rrsets[("@", "MX")]["records"] == [{"value": "10 mail.example.com."}]

    dns.set_rrset("example.com", "@", "A", 3600, [])
    assert ("@", "A") not in fake.rrsets
