"""Каталоги молҳо. Нархҳо дар дирам (1 сомонӣ = 100 дирам) нигоҳ дошта мешаванд.

Ин рӯйхат қиматҳои ибтидоист: ҳангоми аввалин оғоз ба базаи маълумот
кӯчонида мешавад, баъд админ нархҳоро аз панели худ иваз карда метавонад.
Нархҳо дигар мешаванд, аммо SKU ва навъи мол ҳамеша аз ҳамин файл гирифта мешавад.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# ── Бахшҳо ────────────────────────────────────────────────────────────
CAT_STARS = "tg_stars"
CAT_PREMIUM = "tg_premium"
CAT_FF_CIS = "ff_cis"
CAT_FF_ID = "ff_id"
CAT_PUBG = "pubg"

CATEGORIES = (CAT_STARS, CAT_PREMIUM, CAT_FF_CIS, CAT_FF_ID, CAT_PUBG)

# Чӣ тавр молро ба харидор мерасонем:
#   "username" — ба @username-и Telegram
#   "player"   — ба ID-и бозӣ
TargetKind = Literal["username", "player"]

# Чӣ тавр фармоиш иҷро мешавад:
#   "game"   — FireLoot: /validate + /order
#   "stars"  — FireLoot: /telegram/check + /telegram/order
#   "manual" — API надорад, админ дастӣ иҷро мекунад
FulfillKind = Literal["game", "stars", "manual"]


@dataclass(frozen=True)
class Category:
    code: str
    title: str
    unit: str
    target: TargetKind
    icon: str
    hint: str


CATEGORY_INFO: dict[str, Category] = {
    CAT_STARS: Category(
        code=CAT_STARS,
        title="Telegram Stars",
        unit="ситора",
        target="username",
        icon="⭐️",
        hint="@username-и аккаунтеро нависед, ки ситораҳо ба он равона мешаванд.",
    ),
    CAT_PREMIUM: Category(
        code=CAT_PREMIUM,
        title="Telegram Premium",
        unit="моҳ",
        target="username",
        icon="👑",
        hint="@username-и аккаунтеро нависед, ки Premium ба он фаъол мешавад.",
    ),
    CAT_FF_CIS: Category(
        code=CAT_FF_CIS,
        title="Free Fire (ИДМ)",
        unit="алмос",
        target="player",
        icon="🔥",
        hint="ID-и бозигари Free Fire-ро нависед — танҳо рақамҳо.",
    ),
    CAT_FF_ID: Category(
        code=CAT_FF_ID,
        title="Free Fire (Индонезия)",
        unit="алмос",
        target="player",
        icon="🇮🇩",
        hint="ID-и бозигари Free Fire Indonesia-ро нависед — танҳо рақамҳо.",
    ),
    CAT_PUBG: Category(
        code=CAT_PUBG,
        title="PUBG Mobile",
        unit="UC",
        target="player",
        icon="🎯",
        hint="ID-и бозигари PUBG Mobile-ро нависед — танҳо рақамҳо.",
    ),
}


@dataclass(frozen=True)
class Group:
    """Зербахш: масалан «Алмосҳо» ва «Ваучерҳо» дар Free Fire."""

    code: str
    category: str
    title: str


DEFAULT_GROUPS: tuple[Group, ...] = (
    Group("stars_all", CAT_STARS, "⭐️ Ситораҳо"),
    Group("prem_all", CAT_PREMIUM, "👑 Обуна"),
    Group("ffcis_diamonds", CAT_FF_CIS, "💎 Алмосҳо"),
    Group("ffcis_vouchers", CAT_FF_CIS, "🎟 Ваучерҳо"),
    Group("ffid_diamonds", CAT_FF_ID, "💎 Алмосҳо"),
    Group("ffid_member", CAT_FF_ID, "🎟 Membership"),
    Group("pubg_uc", CAT_PUBG, "🎮 UC"),
)


def groups_of(category: str) -> tuple[Group, ...]:
    return tuple(g for g in DEFAULT_GROUPS if g.category == category)


@dataclass(frozen=True)
class Product:
    code: str
    category: str
    title: str
    amount: int          # ситора/алмос/UC/моҳ
    price: int           # дирам — нархи оддӣ
    sku: str             # SKU-и FireLoot ("" барои молҳои дастӣ)
    kind: FulfillKind
    partner_price: int = 0   # дирам; 0 — шарик нархи оддиро мепардозад
    group: str = ""          # зербахш (Group.code)


def _p(
    code: str,
    category: str,
    title: str,
    amount: int,
    price_somoni: float,
    sku: str,
    kind: FulfillKind = "game",
    partner_somoni: float = 0,
    group: str = "",
) -> Product:
    """Нархҳо бо сомонӣ навишта мешаванд, дар база бо дирам нигоҳ дошта."""
    return Product(
        code, category, title, amount, round(price_somoni * 100),
        sku, kind, round(partner_somoni * 100), group,
    )


DEFAULT_PRODUCTS: tuple[Product, ...] = (
    # ── Telegram Stars (FireLoot /telegram/order) ─────────────────────
    _p("stars_50", CAT_STARS, "⭐ 50 Stars", 50, 9.80, "stars_50", "stars", group="stars_all"),
    _p("stars_100", CAT_STARS, "⭐ 100 Stars", 100, 19.25, "stars_100", "stars", group="stars_all"),
    _p("stars_500", CAT_STARS, "⭐ 500 Stars", 500, 90.00, "stars_500", "stars", group="stars_all"),
    _p("stars_1000", CAT_STARS, "⭐ 1000 Stars", 1000, 175.00, "stars_1000", "stars", group="stars_all"),
    _p("stars_2500", CAT_STARS, "⭐ 2500 Stars", 2500, 425.00, "stars_2500", "stars", group="stars_all"),

    # ── Telegram Premium (дастӣ — дар FireLoot нест) ──────────────────
    _p("prem_3", CAT_PREMIUM, "👑 Premium — 3 моҳ", 3, 165.00, "", "manual", group="prem_all"),
    _p("prem_6", CAT_PREMIUM, "👑 Premium — 6 моҳ", 6, 225.00, "", "manual", group="prem_all"),
    _p("prem_12", CAT_PREMIUM, "👑 Premium — 12 моҳ", 12, 390.00, "", "manual", group="prem_all"),

    # ── Free Fire ИДМ — алмосҳо ──────────────────────────────────────
    _p("ffcis_110", CAT_FF_CIS, "💎 110 Алмаз", 110, 9.00, "diamonds_110", partner_somoni=8.4, group="ffcis_diamonds"),
    _p("ffcis_341", CAT_FF_CIS, "💎 341 Алмаз", 341, 28.00, "diamonds_341", partner_somoni=25.0, group="ffcis_diamonds"),
    _p("ffcis_572", CAT_FF_CIS, "💎 572 Алмаз", 572, 45.00, "diamonds_572", partner_somoni=42.5, group="ffcis_diamonds"),
    _p("ffcis_1166", CAT_FF_CIS, "💎 1166 Алмаз", 1166, 89.90, "diamonds_1166", partner_somoni=86.0, group="ffcis_diamonds"),
    _p("ffcis_2398", CAT_FF_CIS, "💎 2398 Алмаз", 2398, 177.00, "diamonds_2398", partner_somoni=170.0, group="ffcis_diamonds"),
    _p("ffcis_6160", CAT_FF_CIS, "💎 6160 Алмаз", 6160, 429.00, "diamonds_6160", partner_somoni=414.0, group="ffcis_diamonds"),
    # ── Free Fire ИДМ — ваучерҳо ─────────────────────────────────────
    _p("ffcis_week_lite", CAT_FF_CIS, "🔹 Ваучери Лайт (Weekly Lite)", 0, 6.00, "voucher_week_lite_2", partner_somoni=4.5, group="ffcis_vouchers"),
    _p("ffcis_week", CAT_FF_CIS, "🎟 Ваучери Ҳафтаина", 0, 16.80, "voucher_week", partner_somoni=16.2, group="ffcis_vouchers"),
    _p("ffcis_month", CAT_FF_CIS, "🎟 Ваучери Моҳона", 0, 64.80, "voucher_month", partner_somoni=59.0, group="ffcis_vouchers"),

    # ── Free Fire Индонезия — алмосҳо ────────────────────────────────
    _p("ffid_50", CAT_FF_ID, "💎 50 Алмаз", 50, 5.50, "id_diamonds_50", group="ffid_diamonds"),
    _p("ffid_100", CAT_FF_ID, "💎 100 Алмаз", 100, 10.50, "id_diamonds_100", group="ffid_diamonds"),
    _p("ffid_140", CAT_FF_ID, "💎 140 Алмаз", 140, 14.00, "id_diamonds_140", group="ffid_diamonds"),
    _p("ffid_210", CAT_FF_ID, "💎 210 Алмаз", 210, 19.00, "id_diamonds_210", group="ffid_diamonds"),
    _p("ffid_280", CAT_FF_ID, "💎 280 Алмаз", 280, 24.00, "id_diamonds_280", group="ffid_diamonds"),
    _p("ffid_355", CAT_FF_ID, "💎 355 Алмаз", 355, 30.00, "id_diamonds_355", group="ffid_diamonds"),
    _p("ffid_500", CAT_FF_ID, "💎 500 Алмаз", 500, 45.00, "id_diamonds_500", group="ffid_diamonds"),
    _p("ffid_720", CAT_FF_ID, "💎 720 Алмаз", 720, 60.00, "id_diamonds_720", group="ffid_diamonds"),
    _p("ffid_1000", CAT_FF_ID, "💎 1000 Алмаз", 1000, 85.00, "id_diamonds_1000", group="ffid_diamonds"),
    _p("ffid_1450", CAT_FF_ID, "💎 1450 Алмаз", 1450, 114.00, "id_diamonds_1450", group="ffid_diamonds"),
    _p("ffid_2180", CAT_FF_ID, "💎 2180 Алмаз", 2180, 175.00, "id_diamonds_2180", group="ffid_diamonds"),
    _p("ffid_3640", CAT_FF_ID, "💎 3640 Алмаз", 3640, 290.00, "id_diamonds_3640", group="ffid_diamonds"),
    _p("ffid_7290", CAT_FF_ID, "💎 7290 Алмаз", 7290, 600.00, "id_diamonds_7290", group="ffid_diamonds"),
    # ── Free Fire Индонезия — Membership ─────────────────────────────
    _p("ffid_week", CAT_FF_ID, "🎟 Ҳафтаина (Weekly)", 0, 19.50, "id_membership_weekly", group="ffid_member"),
    _p("ffid_month", CAT_FF_ID, "🎟 Моҳона (Monthly)", 0, 69.80, "id_membership_monthly", group="ffid_member"),

    # ── PUBG Mobile UC ───────────────────────────────────────────────
    _p("pubg_60", CAT_PUBG, "🎮 60 UC", 60, 10.00, "pubg_uc_60", partner_somoni=9.6, group="pubg_uc"),
    _p("pubg_325", CAT_PUBG, "🎮 300 + 25 UC", 325, 48.95, "pubg_uc_325", partner_somoni=47.8, group="pubg_uc"),
    _p("pubg_660", CAT_PUBG, "🎮 600 + 60 UC", 660, 93.70, "pubg_uc_660", partner_somoni=92.0, group="pubg_uc"),
    _p("pubg_1800", CAT_PUBG, "🎮 1 500 + 300 UC", 1800, 241.00, "pubg_uc_1800", partner_somoni=235.0, group="pubg_uc"),
    _p("pubg_3850", CAT_PUBG, "🎮 3 000 + 850 UC", 3850, 452.00, "pubg_uc_3850", partner_somoni=440.0, group="pubg_uc"),
    _p("pubg_8100", CAT_PUBG, "🎮 6 000 + 2 100 UC", 8100, 900.00, "pubg_uc_8100", partner_somoni=865.0, group="pubg_uc"),
    _p("pubg_16200", CAT_PUBG, "🎮 12 000 + 4 200 UC", 16200, 1800.00, "pubg_uc_16200", partner_somoni=1670.0, group="pubg_uc"),
    _p("pubg_24300", CAT_PUBG, "🎮 18 000 + 6 300 UC", 24300, 2700.00, "pubg_uc_24300", partner_somoni=2650.0, group="pubg_uc"),
    _p("pubg_32400", CAT_PUBG, "🎮 24 000 + 8 400 UC", 32400, 3700.00, "pubg_uc_32400", partner_somoni=3650.0, group="pubg_uc"),
    _p("pubg_40500", CAT_PUBG, "🎮 30 000 + 10 500 UC", 40500, 4500.00, "pubg_uc_40500", partner_somoni=4450.0, group="pubg_uc"),
)

# Маблағҳои тайёр барои пур кардани ҳисоб (дирам).
TOPUP_PRESETS: tuple[int, ...] = (
    20_00, 50_00, 100_00, 200_00, 300_00, 500_00, 1000_00, 2000_00,
)


def category_of(code: str) -> Category:
    return CATEGORY_INFO[code]


def default_products_for(category: str) -> tuple[Product, ...]:
    return tuple(p for p in DEFAULT_PRODUCTS if p.category == category)
