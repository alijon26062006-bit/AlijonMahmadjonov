"""Запросы к базе. Всё, что принадлежит продавцу, ищется только вместе с его user_id:
чужой магазин или анализ для него просто «не найден».

Функции делают flush, но не commit — транзакцией управляет вызывающий код
(`async with sessionmaker.begin() as session: ...`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wbm.db.base import utcnow
from wbm.db.models import (
    ACTIVE_RUN_STATUSES,
    AnalysisRun,
    CheckResult,
    CostPrice,
    LoginAttempt,
    RunDataset,
    RunSource,
    RunStatus,
    Shop,
    User,
)


class EmailTakenError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


# ── пользователи ──────────────────────────────────────────────────────────────


async def create_user(session: AsyncSession, email: str, password_hash: str) -> User:
    user = User(email=normalize_email(email), password_hash=password_hash)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        raise EmailTakenError("Пользователь с таким email уже есть") from None
    return user


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == normalize_email(email)))
    return result.scalar_one_or_none()


async def get_user_by_telegram(session: AsyncSession, chat_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_chat_id == chat_id))
    return result.scalar_one_or_none()


# ── попытки входа ─────────────────────────────────────────────────────────────


async def record_login_attempt(
    session: AsyncSession, *, email: str, ip: str, success: bool
) -> None:
    session.add(LoginAttempt(email=normalize_email(email), ip=ip, success=success))
    await session.flush()


async def count_failed_logins(
    session: AsyncSession, *, since: datetime, email: str | None = None, ip: str | None = None
) -> int:
    if email is None and ip is None:
        raise ValueError("Нужен email или ip")
    stmt = select(func.count()).where(
        LoginAttempt.success.is_(False), LoginAttempt.created_at >= since
    )
    if email is not None:
        stmt = stmt.where(LoginAttempt.email == normalize_email(email))
    if ip is not None:
        stmt = stmt.where(LoginAttempt.ip == ip)
    return int((await session.execute(stmt)).scalar_one())


# ── магазины ──────────────────────────────────────────────────────────────────


async def create_shop(
    session: AsyncSession,
    *,
    user_id: int,
    name: str,
    token_encrypted: str,
    token_fingerprint: str,
    seller_id: str | None = None,
    token_kind: int | None = None,
    token_expires_at: datetime | None = None,
    token_categories: Sequence[str] = (),
    sandbox: bool = False,
) -> Shop:
    shop = Shop(
        user_id=user_id,
        name=name,
        seller_id=seller_id,
        token_encrypted=token_encrypted,
        token_fingerprint=token_fingerprint,
        token_kind=token_kind,
        token_expires_at=token_expires_at,
        token_categories=list(token_categories),
        token_checked_at=utcnow(),
        sandbox=sandbox,
    )
    session.add(shop)
    await session.flush()
    return shop


async def list_shops(session: AsyncSession, user_id: int) -> list[Shop]:
    result = await session.execute(select(Shop).where(Shop.user_id == user_id).order_by(Shop.id))
    return list(result.scalars())


async def get_shop(session: AsyncSession, user_id: int, shop_id: int) -> Shop | None:
    result = await session.execute(select(Shop).where(Shop.id == shop_id, Shop.user_id == user_id))
    return result.scalar_one_or_none()


async def delete_shop(session: AsyncSession, user_id: int, shop_id: int) -> bool:
    shop = await get_shop(session, user_id, shop_id)
    if shop is None:
        return False
    await session.delete(shop)
    await session.flush()
    return True


# ── себестоимость ─────────────────────────────────────────────────────────────


async def replace_cost_prices(
    session: AsyncSession, shop_id: int, prices: Mapping[str, Decimal]
) -> int:
    """Заменяет всю себестоимость магазина данными нового файла."""
    await session.execute(delete(CostPrice).where(CostPrice.shop_id == shop_id))
    session.add_all(
        CostPrice(shop_id=shop_id, vendor_code=code, cost=cost) for code, cost in prices.items()
    )
    await session.flush()
    return len(prices)


async def get_cost_prices(session: AsyncSession, shop_id: int) -> dict[str, Decimal]:
    result = await session.execute(
        select(CostPrice.vendor_code, CostPrice.cost).where(CostPrice.shop_id == shop_id)
    )
    return dict(result.tuples().all())


# ── анализы ───────────────────────────────────────────────────────────────────


async def enqueue_run(
    session: AsyncSession,
    *,
    user_id: int,
    shop_id: int,
    source: RunSource = RunSource.WEB,
    period_days: int = 30,
) -> AnalysisRun | None:
    """Ставит анализ в очередь. Если по магазину анализ уже идёт — возвращает его.

    None — магазин не найден у этого пользователя.
    """
    if await get_shop(session, user_id, shop_id) is None:
        return None
    active = await session.execute(
        select(AnalysisRun)
        .where(AnalysisRun.shop_id == shop_id, AnalysisRun.status.in_(ACTIVE_RUN_STATUSES))
        .order_by(AnalysisRun.id)
        .limit(1)
    )
    existing = active.scalar_one_or_none()
    if existing is not None:
        return existing
    run = AnalysisRun(
        shop_id=shop_id,
        source=source,
        period_days=period_days,
        status=RunStatus.QUEUED,
        progress=0,
        attempts=0,
    )
    session.add(run)
    await session.flush()
    return run


async def get_run(session: AsyncSession, user_id: int, run_id: int) -> AnalysisRun | None:
    """Анализ вместе с результатами — только если магазин принадлежит пользователю."""
    result = await session.execute(
        select(AnalysisRun)
        .join(Shop, Shop.id == AnalysisRun.shop_id)
        .where(AnalysisRun.id == run_id, Shop.user_id == user_id)
        .options(
            selectinload(AnalysisRun.datasets),
            selectinload(AnalysisRun.checks).selectinload(CheckResult.findings),
        )
    )
    return result.scalar_one_or_none()


async def list_runs(
    session: AsyncSession, user_id: int, shop_id: int, *, limit: int = 20
) -> list[AnalysisRun]:
    result = await session.execute(
        select(AnalysisRun)
        .join(Shop, Shop.id == AnalysisRun.shop_id)
        .where(AnalysisRun.shop_id == shop_id, Shop.user_id == user_id)
        .order_by(AnalysisRun.id.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def claim_next_run(
    session: AsyncSession, worker_id: str, *, now: datetime | None = None
) -> AnalysisRun | None:
    """Забирает самый старый анализ из очереди (в MySQL — SKIP LOCKED для нескольких воркеров)."""
    now = now or utcnow()
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.status == RunStatus.QUEUED)
        .order_by(AnalysisRun.created_at, AnalysisRun.id)
        .limit(1)
    )
    connection = await session.connection()
    if connection.dialect.name == "mysql":
        stmt = stmt.with_for_update(skip_locked=True)
    run = (await session.execute(stmt)).scalar_one_or_none()
    if run is None:
        return None
    run.status = RunStatus.RUNNING
    run.worker_id = worker_id
    run.started_at = now
    run.heartbeat_at = now
    run.attempts += 1
    run.progress = 0
    run.error = None
    await session.flush()
    return run


async def _own_running_run(
    session: AsyncSession, run_id: int, worker_id: str
) -> AnalysisRun | None:
    run = await session.get(AnalysisRun, run_id)
    if run is None or run.status != RunStatus.RUNNING or run.worker_id != worker_id:
        return None
    return run


async def report_progress(
    session: AsyncSession,
    run_id: int,
    worker_id: str,
    *,
    progress: int,
    stage: str,
    now: datetime | None = None,
) -> bool:
    """Обновляет прогресс. False — анализ уже не наш (его перезапустили или завершили)."""
    run = await _own_running_run(session, run_id, worker_id)
    if run is None:
        return False
    run.progress = max(0, min(100, progress))
    run.stage = stage[:255]
    run.heartbeat_at = now or utcnow()
    await session.flush()
    return True


async def finish_run(
    session: AsyncSession,
    run_id: int,
    worker_id: str,
    *,
    datasets: Sequence[RunDataset],
    checks: Sequence[CheckResult],
    summary: dict[str, object] | None = None,
    report_text: str | None = None,
    now: datetime | None = None,
) -> bool:
    """Сохраняет результаты и отмечает анализ завершённым."""
    run = await _own_running_run(session, run_id, worker_id)
    if run is None:
        return False
    await session.refresh(run, ["datasets", "checks"])
    run.datasets = list(datasets)
    run.checks = list(checks)
    run.summary = summary
    run.report_text = report_text
    run.status = RunStatus.DONE
    run.progress = 100
    run.stage = None
    run.finished_at = now or utcnow()
    await session.flush()
    return True


async def fail_run(
    session: AsyncSession,
    run_id: int,
    worker_id: str,
    *,
    error: str,
    now: datetime | None = None,
) -> bool:
    run = await _own_running_run(session, run_id, worker_id)
    if run is None:
        return False
    run.status = RunStatus.FAILED
    run.error = error[:2000]
    run.finished_at = now or utcnow()
    await session.flush()
    return True


async def requeue_stale_runs(
    session: AsyncSession, *, stale_before: datetime, max_attempts: int = 3
) -> int:
    """Анализы, чей воркер пропал (нет heartbeat), — снова в очередь или в ошибку."""
    result = await session.execute(
        select(AnalysisRun).where(
            AnalysisRun.status == RunStatus.RUNNING, AnalysisRun.heartbeat_at < stale_before
        )
    )
    stale = list(result.scalars())
    for run in stale:
        run.worker_id = None
        if run.attempts >= max_attempts:
            run.status = RunStatus.FAILED
            run.error = "Анализ прервался несколько раз подряд"
            run.finished_at = utcnow()
        else:
            run.status = RunStatus.QUEUED
            run.stage = "Перезапуск после сбоя"
    await session.flush()
    return len(stale)
