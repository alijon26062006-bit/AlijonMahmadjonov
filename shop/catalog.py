"""Каталоги молҳо. Нархҳо дар дирам (1 сомонӣ = 100 дирам) нигоҳ дошта мешаванд.

Ин рӯйхат қиматҳои ибтидоист: ҳангоми аввалин оғоз ба базаи маълумот
кӯчонида мешавад, баъд админ нархҳоро аз панели худ иваз карда метавонад.
Нархҳо дигар мешаванд, аммо SKU ва навъи мол ҳамеша аз ҳамин файл гирифта мешавад.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

# ── Бахшҳо ────────────────────────────────────────────────────────────
CAT_STARS = "tg_stars"
CAT_PREMIUM = "tg_premium"
CAT_FF_CIS = "ff_cis"
CAT_FF_ID = "ff_id"
CAT_PUBG = "pubg"
CAT_OTHER = "other_games"

CATEGORIES = (CAT_STARS, CAT_PREMIUM, CAT_FF_CIS, CAT_FF_ID, CAT_PUBG, CAT_OTHER)

# Чӣ тавр молро ба харидор мерасонем:
#   "username"      — ба @username-и Telegram
#   "player"        — ба ID-и бозӣ
#   "player_server" — ID-и бозигар ва рақами сервер (Mobile Legends)
TargetKind = Literal["username", "player", "player_server"]

# Чӣ тавр фармоиш иҷро мешавад:
#   "game"   — FireLoot: /validate + /order
#   "stars"  — Donatix, агар калид бошад; вагарна FireLoot /telegram/*
#   "premium"— Donatix; бе калиди Donatix — админ дастӣ
#   "manual" — API надорад, админ дастӣ иҷро мекунад
FulfillKind = Literal["game", "stars", "premium", "manual"]


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
        title="Free Fire",
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
    CAT_OTHER: Category(
        code=CAT_OTHER,
        title="Дигар бозиҳо",
        unit="дона",
        target="player",
        icon="🎮",
        hint="ID-и бозигарро нависед — танҳо рақамҳо.",
    ),
}

#: Зербахшҳое, ки ID ва рақами сервер талаб мекунанд (Mobile Legends).
SERVER_GROUPS = frozenset({"mlbb_all", "mlbbcis_all"})

#: Номи бозиҳо аз рӯи пешванди SKU — барои илова кардани бозии нав аз панел.
FAMILY_NAMES: dict[str, str] = {
    "diamonds": "Free Fire (ИДМ)", "voucher": "Free Fire — ваучерҳо",
    "levelpass": "Free Fire — пропускҳо",
    "id": "Free Fire Индонезия", "br": "Free Fire Бразилия",
    "latam": "Free Fire Латино", "mena": "Free Fire MENA", "eu": "Free Fire Аврупо",
    "sg": "Free Fire Сингапур", "tw": "Free Fire Тайван", "vn": "Free Fire Ветнам",
    "pk": "Free Fire Покистон", "bd": "Free Fire Бангладеш",
    "pubg": "PUBG Mobile", "mlbb": "Mobile Legends", "mlbbcis": "Mobile Legends (ИДМ)",
    "hok": "Honor of Kings", "bs": "Blood Strike", "mr": "Marvel Rivals",
    "ab": "Arena Breakout", "abi": "Arena Breakout Infinite",
    "stars": "Telegram Stars",
}

#: Аломати бозиҳо барои тугмаҳо.
FAMILY_ICONS: dict[str, str] = {
    "mlbb": "⚔️", "mlbbcis": "⚔️", "hok": "👑", "bs": "🩸", "mr": "🦸",
    "ab": "🔫", "abi": "🔫", "pubg": "🎯",
}


def family_of(sku: str) -> str:
    """«mlbb_diamonds_50» → «mlbb»."""
    return (sku or "").split("_")[0]


#: Дарозии ҳадди аксари коди мол. Telegram дар тугма зиёда аз 64 байт
#: намепазирад, ва «a:setprice:» + код бояд ҷо шавад — вагарна тамоми
#: рӯйхати нархҳо нишон дода намешуд.
MAX_CODE_BYTES = 40


def product_code_for(sku: str) -> str:
    """Коди моли нав аз SKU. SKU-и дароз кӯтоҳ мешавад, вале беҳамто мемонад."""
    if len(sku.encode()) <= MAX_CODE_BYTES and sku.isascii():
        return sku
    digest = hashlib.sha1(sku.encode()).hexdigest()[:8]
    head = "".join(ch for ch in sku if ch.isascii())[: MAX_CODE_BYTES - 9]
    return f"{head}_{digest}"


def family_title(family: str) -> str:
    icon = FAMILY_ICONS.get(family, "🎮")
    return f"{icon} {FAMILY_NAMES.get(family, family)}"


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
    Group("pubg_extra", CAT_PUBG, "👑 Prime ва Elite Pass"),
    Group("mlbb_all", CAT_OTHER, "⚔️ Mobile Legends"),
    Group("mlbbcis_all", CAT_OTHER, "⚔️ Mobile Legends (ИДМ)"),
    Group("hok_all", CAT_OTHER, "👑 Honor of Kings"),
    Group("bs_all", CAT_OTHER, "🩸 Blood Strike"),
    Group("mr_all", CAT_OTHER, "🦸 Marvel Rivals"),
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
    cost: int = 0            # нархи харид дар ҳазорумҳои доллар (0.886 $ → 886)
    active: bool = True      # моли нав хомӯш аст, то админ нархро тасдиқ кунад


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
    cost_usd: float = 0,
    active: bool = True,
) -> Product:
    """Нархҳо бо сомонӣ навишта мешаванд, дар база бо дирам нигоҳ дошта."""
    return Product(
        code, category, title, amount, round(price_somoni * 100),
        sku, kind, round(partner_somoni * 100), group,
        round(cost_usd * 1000), active,
    )


DEFAULT_PRODUCTS: tuple[Product, ...] = (
    # ── Telegram Stars (FireLoot /telegram/order) ─────────────────────
    _p("stars_50", CAT_STARS, "⭐ 50 Stars", 50, 9.80, "stars_50", "stars", group="stars_all"),
    _p("stars_100", CAT_STARS, "⭐ 100 Stars", 100, 19.25, "stars_100", "stars", group="stars_all"),
    _p("stars_500", CAT_STARS, "⭐ 500 Stars", 500, 90.00, "stars_500", "stars", group="stars_all"),
    _p("stars_1000", CAT_STARS, "⭐ 1000 Stars", 1000, 175.00, "stars_1000", "stars", group="stars_all"),
    _p("stars_2500", CAT_STARS, "⭐ 2500 Stars", 2500, 425.00, "stars_2500", "stars", group="stars_all"),

    # ── Telegram Premium (дастӣ — дар FireLoot нест) ──────────────────
    _p("prem_3", CAT_PREMIUM, "👑 Premium — 3 моҳ", 3, 165.00, "", "premium", group="prem_all"),
    _p("prem_6", CAT_PREMIUM, "👑 Premium — 6 моҳ", 6, 225.00, "", "premium", group="prem_all"),
    _p("prem_12", CAT_PREMIUM, "👑 Premium — 12 моҳ", 12, 390.00, "", "premium", group="prem_all"),

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

    # ── mlbb ──
    _p("mlbb_diamonds_32", CAT_OTHER, "32 + 3 💎", 35, 7.5, "mlbb_diamonds_32", group="mlbb_all", cost_usd=0.62, active=False),
    _p("mlbb_diamonds_50", CAT_OTHER, "50 + 5 💎", 55, 11.5, "mlbb_diamonds_50", group="mlbb_all", cost_usd=0.979, active=False),
    _p("mlbb_diamonds_150", CAT_OTHER, "150 + 15 💎", 165, 34.0, "mlbb_diamonds_150", group="mlbb_all", cost_usd=2.937, active=False),
    _p("mlbb_diamonds_250", CAT_OTHER, "250 + 25 💎", 275, 56.5, "mlbb_diamonds_250", group="mlbb_all", cost_usd=4.894, active=False),
    _p("mlbb_diamonds_500", CAT_OTHER, "500 + 65 💎", 565, 113.5, "mlbb_diamonds_500", group="mlbb_all", cost_usd=9.844, active=False),
    _p("mlbb_diamonds_1000", CAT_OTHER, "1000 + 155 💎", 1155, 227.5, "mlbb_diamonds_1000", group="mlbb_all", cost_usd=19.754, active=False),
    _p("mlbb_diamonds_1500", CAT_OTHER, "1500 + 265 💎", 1765, 340.0, "mlbb_diamonds_1500", group="mlbb_all", cost_usd=29.541, active=False),
    _p("mlbb_diamonds_2500", CAT_OTHER, "2500 + 475 💎", 2975, 567.0, "mlbb_diamonds_2500", group="mlbb_all", cost_usd=49.294, active=False),
    _p("mlbb_diamonds_5000", CAT_OTHER, "5000 + 1000 💎", 6000, 1132.5, "mlbb_diamonds_5000", group="mlbb_all", cost_usd=98.473, active=False),
    _p("mlbb_weekly", CAT_OTHER, "🎟 Weekly Pass", 0, 23.0, "mlbb_weekly", group="mlbb_all", cost_usd=1.966, active=False),
    _p("mlbb_super_value_pass", CAT_OTHER, "🎟 Super Value Pass", 0, 13.0, "mlbb_super_value_pass", group="mlbb_all", cost_usd=1.102, active=False),

    # ── mlbbcis ──
    _p("mlbbcis_diamonds_50", CAT_OTHER, "50 + 5 💎", 55, 9.5, "mlbbcis_diamonds_50", group="mlbbcis_all", cost_usd=0.79, active=False),
    _p("mlbbcis_diamonds_78", CAT_OTHER, "78 + 8 💎", 86, 14.5, "mlbbcis_diamonds_78", group="mlbbcis_all", cost_usd=1.251, active=False),
    _p("mlbbcis_diamonds_150", CAT_OTHER, "150 + 15 💎", 165, 27.5, "mlbbcis_diamonds_150", group="mlbbcis_all", cost_usd=2.376, active=False),
    _p("mlbbcis_diamonds_156", CAT_OTHER, "156 + 16 💎", 172, 28.5, "mlbbcis_diamonds_156", group="mlbbcis_all", cost_usd=2.477, active=False),
    _p("mlbbcis_diamonds_234", CAT_OTHER, "234 + 23 💎", 257, 41.0, "mlbbcis_diamonds_234", group="mlbbcis_all", cost_usd=3.552, active=False),
    _p("mlbbcis_diamonds_625", CAT_OTHER, "625 + 81 💎", 706, 112.5, "mlbbcis_diamonds_625", group="mlbbcis_all", cost_usd=9.748, active=False),
    _p("mlbbcis_diamonds_1860", CAT_OTHER, "1860 + 335 💎", 2195, 339.5, "mlbbcis_diamonds_1860", group="mlbbcis_all", cost_usd=29.511, active=False),
    _p("mlbbcis_diamonds_3099", CAT_OTHER, "3099 + 589 💎", 3688, 566.5, "mlbbcis_diamonds_3099", group="mlbbcis_all", cost_usd=49.224, active=False),
    _p("mlbbcis_diamonds_4649", CAT_OTHER, "4649 + 883 💎", 5532, 855.0, "mlbbcis_diamonds_4649", group="mlbbcis_all", cost_usd=74.327, active=False),
    _p("mlbbcis_diamonds_7740", CAT_OTHER, "7740 + 1548 💎", 9288, 1420.0, "mlbbcis_diamonds_7740", group="mlbbcis_all", cost_usd=123.449, active=False),
    _p("mlbbcis_weekly", CAT_OTHER, "🎟 Weekly", 0, 18.0, "mlbbcis_weekly", group="mlbbcis_all", cost_usd=1.545, active=False),
    _p("mlbbcis_weekly_elite_pack", CAT_OTHER, "🎟 Weekly Elite", 0, 9.5, "mlbbcis_weekly_elite_pack", group="mlbbcis_all", cost_usd=0.815, active=False),
    _p("mlbbcis_monthly_elite_pack", CAT_OTHER, "🎟 Monthly Elite", 0, 46.5, "mlbbcis_monthly_elite_pack", group="mlbbcis_all", cost_usd=4.014, active=False),
    _p("mlbbcis_twilight", CAT_OTHER, "🌙 Twilight", 0, 94.5, "mlbbcis_twilight", group="mlbbcis_all", cost_usd=8.178, active=False),

    # ── hok ──
    _p("hok_tokens_16", CAT_OTHER, "16 токен", 16, 2.5, "hok_tokens_16", group="hok_all", cost_usd=0.18, active=False),
    _p("hok_tokens_80", CAT_OTHER, "80 токен", 80, 10.0, "hok_tokens_80", group="hok_all", cost_usd=0.865, active=False),
    _p("hok_tokens_240", CAT_OTHER, "240 токен", 240, 30.5, "hok_tokens_240", group="hok_all", cost_usd=2.61, active=False),
    _p("hok_tokens_400", CAT_OTHER, "400 токен", 400, 50.5, "hok_tokens_400", group="hok_all", cost_usd=4.364, active=False),
    _p("hok_tokens_560", CAT_OTHER, "560 токен", 560, 70.5, "hok_tokens_560", group="hok_all", cost_usd=6.109, active=False),
    _p("hok_tokens_800", CAT_OTHER, "800 + 30 токен", 830, 100.5, "hok_tokens_800", group="hok_all", cost_usd=8.735, active=False),
    _p("hok_tokens_1200", CAT_OTHER, "1200 + 45 токен", 1245, 151.0, "hok_tokens_1200", group="hok_all", cost_usd=13.099, active=False),
    _p("hok_tokens_2400", CAT_OTHER, "2400 + 108 токен", 2508, 301.5, "hok_tokens_2400", group="hok_all", cost_usd=26.213, active=False),
    _p("hok_tokens_4000", CAT_OTHER, "4000 + 180 токен", 4180, 502.5, "hok_tokens_4000", group="hok_all", cost_usd=43.691, active=False),
    _p("hok_tokens_8000", CAT_OTHER, "8000 + 360 токен", 8360, 1005.5, "hok_tokens_8000", group="hok_all", cost_usd=87.397, active=False),
    _p("hok_weekly_card", CAT_OTHER, "🎟 Weekly Card", 0, 11.5, "hok_weekly_card", group="hok_all", cost_usd=0.971, active=False),
    _p("hok_weekly_card_plus", CAT_OTHER, "🎟 Weekly Card Plus", 0, 33.0, "hok_weekly_card_plus", group="hok_all", cost_usd=2.855, active=False),
    _p("hok_honor_point_value_pack", CAT_OTHER, "🎁 Honor Point Pack", 0, 3.5, "hok_honor_point_value_pack", group="hok_all", cost_usd=0.27, active=False),

    # ── bs ──
    _p("bs_gold_51", CAT_OTHER, "51 Gold", 51, 5.0, "bs_gold_51", group="bs_all", cost_usd=0.4, active=False),
    _p("bs_gold_100", CAT_OTHER, "100 + 5 Gold", 105, 9.5, "bs_gold_100", group="bs_all", cost_usd=0.792, active=False),
    _p("bs_gold_300", CAT_OTHER, "300 + 20 Gold", 320, 28.0, "bs_gold_300", group="bs_all", cost_usd=2.398, active=False),
    _p("bs_gold_500", CAT_OTHER, "500 + 40 Gold", 540, 46.5, "bs_gold_500", group="bs_all", cost_usd=4.005, active=False),
    _p("bs_gold_1000", CAT_OTHER, "1000 + 100 Gold", 1100, 92.5, "bs_gold_1000", group="bs_all", cost_usd=8.034, active=False),
    _p("bs_gold_2000", CAT_OTHER, "2000 + 260 Gold", 2260, 185.0, "bs_gold_2000", group="bs_all", cost_usd=16.075, active=False),
    _p("bs_gold_5000", CAT_OTHER, "5000 + 800 Gold", 5800, 463.5, "bs_gold_5000", group="bs_all", cost_usd=40.273, active=False),
    _p("bs_level_up_pass", CAT_OTHER, "🎟 Level Up Pass", 0, 18.5, "bs_level_up_pass", group="bs_all", cost_usd=1.599, active=False),
    _p("bs_strike_pass_elite", CAT_OTHER, "🎟 Strike Pass Elite", 0, 37.5, "bs_strike_pass_elite", group="bs_all", cost_usd=3.222, active=False),
    _p("bs_strike_pass_premium", CAT_OTHER, "🎟 Strike Pass Premium", 0, 83.5, "bs_strike_pass_premium", group="bs_all", cost_usd=7.259, active=False),
    _p("bs_value_season_pass", CAT_OTHER, "🎟 Value Season Pass", 0, 9.5, "bs_value_season_pass", group="bs_all", cost_usd=0.792, active=False),

    # ── mr ──
    _p("mr_lattice_100", CAT_OTHER, "100 Lattice", 100, 10.5, "mr_lattice_100", group="mr_all", cost_usd=0.906, active=False),
    _p("mr_lattice_500", CAT_OTHER, "500 Lattice", 500, 52.0, "mr_lattice_500", group="mr_all", cost_usd=4.519, active=False),
    _p("mr_lattice_1000", CAT_OTHER, "1000 Lattice", 1000, 104.0, "mr_lattice_1000", group="mr_all", cost_usd=9.029, active=False),
    _p("mr_lattice_2180", CAT_OTHER, "2180 Lattice", 2180, 208.0, "mr_lattice_2180", group="mr_all", cost_usd=18.065, active=False),
    _p("mr_lattice_5680", CAT_OTHER, "5680 Lattice", 5680, 519.5, "mr_lattice_5680", group="mr_all", cost_usd=45.159, active=False),
    _p("mr_lattice_11680", CAT_OTHER, "11680 Lattice", 11680, 1039.0, "mr_lattice_11680", group="mr_all", cost_usd=90.325, active=False),

    # ── pubg_extra ──
    _p("pubg_prime_1m", CAT_PUBG, "👑 Prime — 1 моҳ", 1, 10.5, "pubg_prime_1m", group="pubg_extra", cost_usd=0.878, active=False),
    _p("pubg_prime_3m", CAT_PUBG, "👑 Prime — 3 моҳ", 3, 30.5, "pubg_prime_3m", group="pubg_extra", cost_usd=2.635, active=False),
    _p("pubg_prime_6m", CAT_PUBG, "👑 Prime — 6 моҳ", 6, 61.0, "pubg_prime_6m", group="pubg_extra", cost_usd=5.269, active=False),
    _p("pubg_prime_12m", CAT_PUBG, "👑 Prime — 12 моҳ", 12, 121.5, "pubg_prime_12m", group="pubg_extra", cost_usd=10.539, active=False),
    _p("pubg_elite_pass_50", CAT_PUBG, "🎟 Elite Pass LV1-50", 0, 61.0, "pubg_elite_pass_50", group="pubg_extra", cost_usd=5.289, active=False),
    _p("pubg_elite_pass_100", CAT_PUBG, "🎟 Elite Pass LV1-100", 0, 123.0, "pubg_elite_pass_100", group="pubg_extra", cost_usd=10.669, active=False),
)

# Маблағҳои тайёр барои пур кардани ҳисоб (дирам).
TOPUP_PRESETS: tuple[int, ...] = (
    20_00, 50_00, 100_00, 200_00, 300_00, 500_00, 1000_00, 2000_00,
)


def category_of(code: str) -> Category:
    return CATEGORY_INFO[code]


def default_products_for(category: str) -> tuple[Product, ...]:
    return tuple(p for p in DEFAULT_PRODUCTS if p.category == category)
