"""Автоплатёж криптой: баланс зачисляется сам, без чека и без админа.

TRC20 (свой кошелёк). Клиенту показываем ваш адрес и уникальную сумму —
например 50.0037 USDT: по последним цифрам узнаём, чей это перевод. Раз в
минуту смотрим входящие USDT на адрес через TronGrid; пришла ровно такая
сумма после создания заявки — зачисляем. Один перевод засчитывается один раз.

Binance Pay (мерчант). Создаём заказ в Binance, клиент платит по ссылке.
Статус узнаём сами запросом к Binance (подписанным вашим секретом) — поэтому
подделать «оплачено» извне нельзя, даже присылая фальшивые уведомления.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import ROUND_UP, Decimal
from typing import Any

import httpx

from . import db
from .config import Config

log = logging.getLogger(__name__)

USDT_TRC20 = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"   # контракт USDT в сети Tron
TRONGRID = "https://api.trongrid.io"
BINANCE = "https://bpay.binanceapi.com"
TRON_ADDRESS_RE = re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b")
AUTO_KINDS = {"trc20": "Автозачисление: USDT TRC20 (блокчейн)", "binance": "Автозачисление: Binance Pay",
              "bybit": "Автозачисление: Bybit (перевод по UID)"}
BYBIT = "https://api.bybit.com"
UNIQUE_KINDS = ("trc20", "bybit")   # у этих перевод узнаём по «хвосту» суммы
WINDOW_HOURS = 48          # сколько ждём перевод по заявке
PAY_MINUTES = 15           # USDT (TRC20, Bybit): на оплату 15 минут, потом заявка закрывается
LATE_HOURS = 3             # перевод позже 15 минут ещё ловим 3 часа, потом сумма свободна для других
EXPIRED_NOTE = "Время на оплату (15 минут) вышло — создайте новую заявку"

_lock = threading.Lock()
_last_check = 0.0


class CryptoPayError(RuntimeError):
    pass


# ── TRC20 ────────────────────────────────────────────────────


def tron_address(details: str) -> str:
    found = TRON_ADDRESS_RE.search(details or "")
    return found.group(0) if found else ""


def unique_amount(conn: sqlite3.Connection, usd: Decimal, address: str = "", exclude: int = 0) -> Decimal:
    """Сумма к переводу. Обычно ровная (10.00). «Хвост» 0.001–0.099 — только если ровно такую же сумму сейчас ждём
    НА ТОТ ЖЕ АДРЕС (та же сеть) от другого клиента: иначе два одинаковых перевода не различить.
    10 $ в BEP20 и 10 $ в TRC20 — разные адреса, обоим ровно 10."""
    base = usd.quantize(Decimal("0.01"), rounding=ROUND_UP)
    sql = ("SELECT pay_amount FROM payments WHERE auto_kind IN ('trc20', 'bybit') AND id != ? AND (status = 'pending' "
           "OR (status = 'cancelled' AND admin_note = ? AND created_at >= ?))")
    args: list[Any] = [exclude, EXPIRED_NOTE, _since_hours(LATE_HOURS)]
    if address:
        sql += " AND lower(pay_address) = lower(?)"
        args.append(address)
    taken = {Decimal(r[0]) for r in conn.execute(sql, args) if r[0]}
    if base not in taken:
        return base
    for _ in range(200):
        n = secrets.randbelow(99) + 1
        if n % 10 == 0:   # 10.010 = 10.01 — такая сумма бывает и ровной у другого клиента
            continue
        amount = (base + Decimal(n) / 1000).quantize(Decimal("0.001"))   # 10.001, 10.002 … 10.099
        if amount not in taken:
            return amount
    raise CryptoPayError("Слишком много заявок одновременно — попробуйте через минуту.")


def _since_hours(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")


def _waiting(conn: sqlite3.Connection, kind: str) -> list[sqlite3.Row]:
    """Ждущие заявки и закрытые по таймеру (вдруг клиент перевёл чуть позже 15 минут — деньги не теряем)."""
    rows = conn.execute("SELECT * FROM payments WHERE auto_kind = ? AND ((status = 'pending' AND created_at >= ?) "
                        "OR (status = 'cancelled' AND admin_note = ? AND created_at >= ?)) ORDER BY id",
                        (kind, _since_hours(WINDOW_HOURS), EXPIRED_NOTE, _since_hours(LATE_HOURS))).fetchall()
    return [r for r in rows if time.time() * 1000 - _ms(r["created_at"]) < WINDOW_HOURS * 3600 * 1000]


def _reopen(conn: sqlite3.Connection, r: sqlite3.Row) -> None:
    if r["status"] == "cancelled":
        conn.execute("UPDATE payments SET status = 'pending', admin_note = NULL, resolved_at = NULL "
                     "WHERE id = ? AND status = 'cancelled' AND admin_note = ?", (r["id"], EXPIRED_NOTE))


def expire(conn: sqlite3.Connection, payment_id: int | None = None) -> int:
    """Закрыть USDT-заявки (TRC20, Bybit), которые ждут дольше 15 минут."""
    sql = ("UPDATE payments SET status = 'cancelled', admin_note = ?, resolved_at = ? "
           "WHERE auto_kind IN ('trc20', 'bybit') AND status = 'pending' AND created_at < ?")
    args: list[Any] = [EXPIRED_NOTE, db.now(), _since_hours(PAY_MINUTES / 60)]
    if payment_id is not None:
        sql += " AND id = ?"
        args.append(payment_id)
    return conn.execute(sql, args).rowcount


def seconds_left(created_at: str) -> int:
    return max(0, int(PAY_MINUTES * 60 - (time.time() * 1000 - _ms(created_at)) / 1000))


def _get_json(url: str, params: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    r = httpx.get(url, params=params, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


def incoming_usdt(config: Config, address: str, since_ms: int) -> list[dict[str, Any]]:
    """Входящие USDT на адрес: [{tx, amount(Decimal), ts(ms)}]."""
    headers = {"Accept": "application/json"}
    if config.trongrid_key:
        headers["TRON-PRO-API-KEY"] = config.trongrid_key
    data = _get_json(f"{TRONGRID}/v1/accounts/{address}/transactions/trc20",
                     {"only_to": "true", "only_confirmed": "true", "limit": 200, "contract_address": USDT_TRC20,
                      "min_timestamp": since_ms}, headers)
    out = []
    for t in data.get("data") or []:
        token = t.get("token_info") or {}
        if token.get("address") and token["address"] != USDT_TRC20:
            continue
        if str(t.get("to", "")) != address:
            continue
        decimals = int(token.get("decimals") or 6)
        out.append({"tx": str(t.get("transaction_id")), "ts": int(t.get("block_timestamp") or 0),
                    "amount": Decimal(str(t.get("value") or "0")) / (Decimal(10) ** decimals)})
    return out


def _ms(stamp: str) -> int:
    dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def check_trc20(conn: sqlite3.Connection, config: Config) -> int:
    """Сверить ждущие TRC20-заявки с блокчейном. Возвращает, сколько зачислено."""
    from . import payments
    fresh = _waiting(conn, "trc20")
    done = 0
    by_address: dict[str, list[sqlite3.Row]] = {}
    for r in fresh:
        if r["pay_address"]:
            by_address.setdefault(r["pay_address"], []).append(r)
    for address, items in by_address.items():
        since = min(_ms(r["created_at"]) for r in items) - 60_000
        try:
            txs = incoming_usdt(config, address, since)
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("trc20: не удалось проверить %s: %s", address, exc)
            continue
        for r in items:
            want = Decimal(r["pay_amount"])
            for t in txs:
                if t["amount"] != want or t["ts"] < _ms(r["created_at"]) - 60_000:
                    continue
                if conn.execute("SELECT 1 FROM payments WHERE ext_id = ?", (t["tx"],)).fetchone():
                    continue  # этот перевод уже засчитан другой заявке
                _reopen(conn, r)
                try:
                    conn.execute("UPDATE payments SET ext_id = ?, reference = ? WHERE id = ? AND status = 'pending'",
                                 (t["tx"], t["tx"][:200], r["id"]))
                except sqlite3.IntegrityError:   # другой процесс уже засчитал этот перевод
                    continue
                if payments.confirm(conn, config, r["id"], _admin_id(conn), who="автоматически"):
                    done += 1
                    _tell_admin(conn, config, r["id"], "USDT TRC20")
                    log.info("trc20: заявка #%s оплачена, tx %s", r["id"], t["tx"])
                break
    return done


# ── Bybit (свой аккаунт, ключ «только чтение») ───────────────


def bybit_ready(config: Config) -> bool:
    return bool(config.bybit_key and config.bybit_secret)


def _bybit_get(config: Config, path: str, params: dict[str, Any]) -> dict[str, Any]:
    """Подписанный GET к Bybit v5: HMAC-SHA256(timestamp + key + recv_window + query)."""
    from urllib.parse import urlencode
    query = urlencode(params)
    ts, window = str(int(time.time() * 1000)), "10000"
    sign = hmac.new(config.bybit_secret.encode(), f"{ts}{config.bybit_key}{window}{query}".encode(),
                    hashlib.sha256).hexdigest()
    headers = {"X-BAPI-API-KEY": config.bybit_key, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": window,
               "X-BAPI-SIGN": sign}
    try:
        # Только IPv4: ключ Bybit привязан к IPv4 сервера, а IPv6 Bybit в белый список не принимает
        with httpx.Client(transport=httpx.HTTPTransport(local_address="0.0.0.0"), timeout=15) as client:
            r = client.get(f"{BYBIT}{path}?{query}", headers=headers)
        data = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise CryptoPayError(f"Bybit не отвечает: {exc}") from exc
    if data.get("retCode") != 0:
        raise CryptoPayError(f"Bybit: {data.get('retMsg') or data}")
    return data.get("result") or {}


# Сеть способа оплаты → как её называет Bybit
BYBIT_CHAINS = {"TRC20": ("TRX", "TRC20"), "BEP20": ("BSC", "BEP20"), "TON": ("TON",), "ERC20": ("ETH", "ERC20"),
                "APTOS": ("APTOS", "APT"), "SOL": ("SOL", "SOLANA")}
_min_cache: dict[str, Any] = {}


def bybit_deposit_min(config: Config, network: str) -> Decimal:
    """Минимальное пополнение USDT в этой сети по данным самого Bybit (меньше — Bybit не зачислит). Держим 6 часов.
    Не узнали — 0: тогда действует только ваш минимум."""
    if not bybit_ready(config) or network not in BYBIT_CHAINS:
        return Decimal(0)
    if not _min_cache or time.monotonic() - _min_cache.get("at", 0) > 6 * 3600:
        try:
            rows = _bybit_get(config, "/v5/asset/coin/query-info", {"coin": "USDT"}).get("rows") or []
            mins = {}
            for c in (rows[0].get("chains") or []) if rows else []:
                try:
                    value = Decimal(str(c.get("depositMin") or "0"))
                except Exception:  # noqa: BLE001
                    continue
                for name in (c.get("chain"), c.get("chainType")):
                    if name:
                        mins[str(name).upper()] = value
            _min_cache.clear()
            _min_cache.update({"at": time.monotonic(), "mins": mins})
        except Exception as exc:  # noqa: BLE001 — Bybit молчит: не мешаем оплате
            log.warning("bybit: минимум пополнения не узнали: %s", exc)
            return Decimal(0)
    mins = _min_cache.get("mins") or {}
    return max((mins.get(n, Decimal(0)) for n in BYBIT_CHAINS[network]), default=Decimal(0))
_addr_cache: dict[str, tuple[float, tuple[str, str]]] = {}


def bybit_address(config: Config, network: str) -> tuple[str, str]:
    """Адрес пополнения USDT на вашем Bybit в этой сети (и memo/тег, если сеть его требует). Держим час."""
    hit = _addr_cache.get(network)
    if hit and time.monotonic() - hit[0] < 3600:
        return hit[1]
    names = BYBIT_CHAINS.get(network)
    if not names:
        raise CryptoPayError(f"Сеть {network} для Bybit не поддерживается.")
    chains = _bybit_get(config, "/v5/asset/deposit/query-address", {"coin": "USDT"}).get("chains") or []
    for c in chains:
        if str(c.get("chain", "")).upper() in names or str(c.get("chainType", "")).upper() in names:
            addr = str(c.get("addressDeposit") or "").strip()
            if addr:
                got = (addr, str(c.get("tagDeposit") or "").strip())
                _addr_cache[network] = (time.monotonic(), got)
                return got
    raise CryptoPayError(f"Bybit не дал адрес USDT в сети {network}. Откройте в Bybit «Активы → Пополнить → USDT → "
                         f"{network}» один раз, чтобы адрес создался, и попробуйте снова.")


def bybit_incoming(config: Config, since_ms: int) -> list[dict[str, Any]]:
    """Зачисленные USDT на аккаунт Bybit: внутренние переводы (по UID) и пополнения из блокчейна."""
    end = int(time.time() * 1000)
    params = {"coin": "USDT", "startTime": max(since_ms, end - 7 * 86400_000), "endTime": end, "limit": 50}
    out = []
    for r in _bybit_get(config, "/v5/asset/deposit/query-internal-record", params).get("rows") or []:
        if str(r.get("status")) == "2":  # 2 — успешно
            out.append({"tx": f"bybit-int-{r.get('id') or r.get('txID')}", "amount": Decimal(str(r.get("amount"))),
                        "ts": int(r.get("createdTime") or 0), "uid": True, "address": ""})
    for r in _bybit_get(config, "/v5/asset/deposit/query-record", params).get("rows") or []:
        if str(r.get("depositStatus", r.get("status"))) == "3":  # 3 — зачислено
            out.append({"tx": f"bybit-{r.get('txID') or r.get('id')}", "amount": Decimal(str(r.get("amount"))),
                        "ts": int(r.get("successAt") or r.get("createdTime") or 0), "uid": False,
                        "address": str(r.get("toAddress") or "").strip()})
    return out


def check_bybit(conn: sqlite3.Connection, config: Config) -> int:
    from . import payments
    if not bybit_ready(config):
        return 0
    rows = _waiting(conn, "bybit")
    if not rows:
        return 0
    try:
        txs = bybit_incoming(config, min(_ms(r["created_at"]) for r in rows) - 60_000)
    except CryptoPayError as exc:
        log.warning("bybit: %s", exc)
        return 0
    done = 0
    for r in rows:
        want = Decimal(r["pay_amount"])
        by_uid = bool(re.fullmatch(r"\d{5,12}", r["pay_address"] or ""))
        for t in txs:
            if t["amount"] != want or (t["ts"] and t["ts"] < _ms(r["created_at"]) - 60_000):
                continue
            # перевод по UID — только к заявке «по UID»; из блокчейна — только на адрес этой заявки (её сеть)
            if t.get("uid", by_uid) != by_uid or (t.get("address") and r["pay_address"]
                                                   and t["address"].lower() != r["pay_address"].lower()):
                continue
            if conn.execute("SELECT 1 FROM payments WHERE ext_id = ?", (t["tx"],)).fetchone():
                continue
            _reopen(conn, r)
            try:
                conn.execute("UPDATE payments SET ext_id = ?, reference = ? WHERE id = ? AND status = 'pending'",
                             (t["tx"], t["tx"][:200], r["id"]))
            except sqlite3.IntegrityError:   # другой процесс уже засчитал этот перевод
                continue
            if payments.confirm(conn, config, r["id"], _admin_id(conn), who="автоматически"):
                done += 1
                _tell_admin(conn, config, r["id"], "Bybit")
                log.info("bybit: заявка #%s оплачена (%s)", r["id"], t["tx"])
            break
    return done


# ── Binance Pay ──────────────────────────────────────────────


def binance_ready(config: Config) -> bool:
    return bool(config.binance_pay_key and config.binance_pay_secret)


def _binance_post(config: Config, path: str, body: dict[str, Any]) -> dict[str, Any]:
    """Подписанный запрос к Binance Pay: HMAC-SHA512(timestamp\\nnonce\\nbody\\n)."""
    payload = json.dumps(body, separators=(",", ":"))
    ts = str(int(time.time() * 1000))
    nonce = secrets.token_hex(16)
    sign = hmac.new(config.binance_pay_secret.encode(), f"{ts}\n{nonce}\n{payload}\n".encode(),
                    hashlib.sha512).hexdigest().upper()
    headers = {"Content-Type": "application/json", "BinancePay-Timestamp": ts, "BinancePay-Nonce": nonce,
               "BinancePay-Certificate-SN": config.binance_pay_key, "BinancePay-Signature": sign}
    try:
        r = httpx.post(BINANCE + path, content=payload, headers=headers, timeout=20)
        data = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise CryptoPayError(f"Binance Pay не отвечает: {exc}") from exc
    if data.get("status") != "SUCCESS":
        raise CryptoPayError(f"Binance Pay: {data.get('errorMessage') or data.get('code') or data}")
    return data.get("data") or {}


def binance_create(config: Config, payment_id: int, amount_usdt: str) -> dict[str, str]:
    trade_no = f"DX{payment_id}T{secrets.token_hex(6)}"
    data = _binance_post(config, "/binancepay/openapi/v2/order", {
        "env": {"terminalType": "WEB"},
        "merchantTradeNo": trade_no,
        "orderAmount": float(Decimal(amount_usdt)),
        "currency": "USDT",
        "goods": {"goodsType": "02", "goodsCategory": "Z000", "referenceGoodsId": f"topup-{payment_id}",
                  "goodsName": f"Donatix balance #{payment_id}"},
        "returnUrl": f"{config.base_url}/panel/balance",
        "webhookUrl": f"{config.base_url}/pay/binance/webhook",
    })
    url = data.get("checkoutUrl") or data.get("universalUrl") or ""
    if not url:
        raise CryptoPayError("Binance Pay не вернул ссылку на оплату.")
    return {"trade_no": trade_no, "url": url}


def binance_status(config: Config, trade_no: str) -> str:
    return str(_binance_post(config, "/binancepay/openapi/v2/order/query",
                             {"merchantTradeNo": trade_no}).get("status") or "")


def check_binance(conn: sqlite3.Connection, config: Config, only_id: int | None = None) -> int:
    from . import payments
    if not binance_ready(config):
        return 0
    sql = "SELECT * FROM payments WHERE auto_kind = 'binance' AND status = 'pending' AND ext_id IS NOT NULL"
    args: tuple = ()
    if only_id is not None:
        sql, args = sql + " AND id = ?", (only_id,)
    done = 0
    for r in conn.execute(sql, args).fetchall():
        try:
            status = binance_status(config, r["ext_id"])
        except CryptoPayError as exc:
            log.warning("binance: заявка #%s: %s", r["id"], exc)
            continue
        if status == "PAID":
            if payments.confirm(conn, config, r["id"], _admin_id(conn), who="автоматически"):
                done += 1
                _tell_admin(conn, config, r["id"], "Binance Pay")
        elif status in ("EXPIRED", "CANCELED", "CANCELLED", "ERROR"):
            if conn.execute("UPDATE payments SET status = 'cancelled', admin_note = ?, resolved_at = ? "
                            "WHERE id = ? AND status = 'pending'",
                            (f"Binance Pay: {status}", db.now(), r["id"])).rowcount:
                from .notify import notify
                notify(conn, config, r["user_id"], f"Заявка #{r['id']} отменена: ссылка Binance Pay истекла "
                                                   "или оплата отменена. Создайте новую.", "/panel/balance")
    return done


# ── Общее ────────────────────────────────────────────────────


def start(conn: sqlite3.Connection, config: Config, payment_id: int, method: dict[str, Any]) -> None:
    """Сразу после создания заявки: запомнить адрес (TRC20) или создать заказ (Binance Pay)."""
    kind = method.get("auto") or ""
    p = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    if kind == "trc20":
        address = tron_address(method.get("details", ""))
        conn.execute("UPDATE payments SET auto_kind = 'trc20', pay_address = ? WHERE id = ?", (address, payment_id))
    elif kind == "bybit":
        from .payments import guess_network
        network = guess_network(method)
        if network:   # адрес пополнения выбранной сети — сразу у Bybit
            address, memo = bybit_address(config, network)
            conn.execute("UPDATE payments SET auto_kind = 'bybit', pay_address = ?, pay_memo = ? WHERE id = ?",
                         (address, memo or None, payment_id))
        else:
            uid = re.search(r"\d{5,12}", method.get("details", ""))
            conn.execute("UPDATE payments SET auto_kind = 'bybit', pay_address = ? WHERE id = ?",
                         (uid.group(0) if uid else method.get("details", "")[:60], payment_id))
    if kind in UNIQUE_KINDS:   # адрес известен — хвост, только если на этот адрес уже ждём такую же сумму
        row = conn.execute("SELECT pay_amount, pay_address FROM payments WHERE id = ?", (payment_id,)).fetchone()
        amount = unique_amount(conn, Decimal(row["pay_amount"]), row["pay_address"] or "", payment_id)
        conn.execute("UPDATE payments SET pay_amount = ? WHERE id = ?", (str(amount), payment_id))
    if kind == "binance":
        order = binance_create(config, payment_id, p["pay_amount"])
        conn.execute("UPDATE payments SET auto_kind = 'binance', ext_id = ?, pay_url = ? WHERE id = ?",
                     (order["trade_no"], order["url"], payment_id))


def check_all(conn: sqlite3.Connection, config: Config, min_interval: float = 20) -> int:
    """Проверить все ждущие автоплатежи (воркер — раз в минуту, страница оплаты — не чаще раза в 20 с)."""
    global _last_check
    if time.monotonic() - _last_check < min_interval or not _lock.acquire(blocking=False):
        return 0
    try:
        _last_check = time.monotonic()
        done = check_trc20(conn, config) + check_bybit(conn, config) + check_binance(conn, config)
        expire(conn)   # сначала проверили поступления — потом закрываем просроченные
        return done
    finally:
        _lock.release()


def reset() -> None:
    global _last_check
    _last_check = 0.0


def _tell_admin(conn: sqlite3.Connection, config: Config, payment_id: int, how: str) -> None:
    from .money import fmt
    from .worker import notify_admin
    p = conn.execute("SELECT p.amount_micro, u.login FROM payments p JOIN users u ON u.id = p.user_id "
                     "WHERE p.id = ?", (payment_id,)).fetchone()
    if p:
        notify_admin(config, f"⚡️ Автоплатёж {how}: заявка #{payment_id}, клиент {p['login']}, "
                             f"зачислено ${fmt(p['amount_micro'])}.")


def _admin_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1").fetchone()
    return int(row["id"]) if row else 0
