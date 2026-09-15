"""Реквизитҳои пардохт: Душанбе Сити ва Alif Mobi.

Ду тарзи пардохт аз аввал ҷойгиранд, ҳаволаҳояшон омодаанд. Админ танҳо
рақами корт, ном ва рақами ҳисобро иваз мекунад — ё яке аз тарзҳоро хомӯш.

Қиматҳо дар база нигоҳ дошта мешаванд: ҳангоми аввалин оғоз аз `.env`
гирифта мешаванд, баъдан танҳо панели админ онҳоро идора мекунад.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import payments
from .config import Config
from .db import Database

CARD_KEY = "card_number"
HOLDER_KEY = "card_holder"
ALIF_KEY = "alif_account"
DC_ON_KEY = "dc_enabled"
ALIF_ON_KEY = "alif_enabled"

#: Тарзҳои пардохт — номҳо барои панел ва тугмаҳо.
DC_NAME = "Душанбе Сити"
ALIF_NAME = "Alif Mobi"


@dataclass(frozen=True)
class Requisites:
    card: str
    holder: str
    alif_account: str
    dc_enabled: bool
    alif_enabled: bool

    @property
    def any_enabled(self) -> bool:
        return (self.dc_enabled and bool(self.card)) or (
            self.alif_enabled and bool(self.alif_account)
        )


def seed(db: Database, cfg: Config) -> None:
    """Ҳангоми аввалин оғоз қиматҳоро аз `.env` мегирад."""
    defaults = {
        CARD_KEY: cfg.card_number,
        HOLDER_KEY: cfg.card_holder,
        ALIF_KEY: cfg.alif_account,
        DC_ON_KEY: "1",
        ALIF_ON_KEY: "1" if cfg.alif_account else "0",
    }
    for key, value in defaults.items():
        if not db.setting(key):
            db.set_setting(key, value or "")


def get(db: Database, cfg: Config) -> Requisites:
    return Requisites(
        card=db.setting(CARD_KEY) or cfg.card_number,
        holder=db.setting(HOLDER_KEY) or cfg.card_holder,
        alif_account=db.setting(ALIF_KEY) or cfg.alif_account,
        dc_enabled=db.setting(DC_ON_KEY, "1") == "1",
        alif_enabled=db.setting(ALIF_ON_KEY, "1") == "1",
    )


def pay_links(req: Requisites, cfg: Config, amount: int, code: str) -> tuple[str | None, str | None]:
    """Ҳаволаҳои Душанбе Сити ва Alif барои ин маблағ."""
    dc = (
        payments.build_pay_link(cfg.pay_link, card=req.card, amount=amount, comment=code)
        if req.dc_enabled and req.card
        else None
    )
    alif = (
        payments.build_alif_link(cfg.alif_link, account=req.alif_account, amount=amount)
        if req.alif_enabled and req.alif_account
        else None
    )
    return dc, alif
