"""Выбор провайдеров по настройкам."""
from __future__ import annotations

from ..config import Settings
from .base import DnsProvider, ProviderError, Registrar, VpsProvider
from .demo import DemoDns, DemoRegistrar, DemoVps
from .hetzner import HetznerClient, HetznerDns, HetznerVps

__all__ = ["Providers", "ProviderError", "build_providers"]


class Providers:
    def __init__(self, vps: VpsProvider, dns: DnsProvider, registrar: Registrar):
        self.vps = vps
        self.dns = dns
        self.registrar = registrar


def build_providers(settings: Settings) -> Providers:
    client = None
    if "hetzner" in (settings.vps_provider, settings.dns_provider):
        client = HetznerClient(settings.hetzner_token, settings.hetzner_api_url)
    vps = HetznerVps(client) if settings.vps_provider == "hetzner" else DemoVps()
    dns = HetznerDns(client) if settings.dns_provider == "hetzner" else DemoDns()
    return Providers(vps=vps, dns=dns, registrar=DemoRegistrar())
