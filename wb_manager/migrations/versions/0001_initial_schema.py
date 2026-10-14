"""Начальная схема: пользователи, магазины, себестоимость, анализы и их результаты.

Revision ID: 0001
Revises:
Create Date: 2026-10-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Типы как в wbm.db.base: BIGINT (INTEGER в SQLite для автоинкремента),
# время в UTC с микросекундами, длинный текст отчёта.
BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
DATETIME_UTC = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
LONG_TEXT = sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql")


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", BIGINT, autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("created_at", DATETIME_UTC, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_attempts")),
    )
    op.create_index(
        op.f("ix_login_attempts_email_created_at"),
        "login_attempts",
        ["email", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_login_attempts_ip_created_at"),
        "login_attempts",
        ["ip", "created_at"],
        unique=False,
    )
    op.create_table(
        "users",
        sa.Column("id", BIGINT, autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", DATETIME_UTC, nullable=False),
        sa.Column("telegram_chat_id", BIGINT, nullable=True),
        sa.Column("telegram_link_code", sa.String(length=64), nullable=True),
        sa.Column("telegram_link_expires_at", DATETIME_UTC, nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("telegram_chat_id", name=op.f("uq_users_telegram_chat_id")),
        sa.UniqueConstraint("telegram_link_code", name=op.f("uq_users_telegram_link_code")),
    )
    op.create_table(
        "shops",
        sa.Column("id", BIGINT, autoincrement=True, nullable=False),
        sa.Column("user_id", BIGINT, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("seller_id", sa.String(length=64), nullable=True),
        sa.Column("token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_fingerprint", sa.String(length=16), nullable=False),
        sa.Column("token_kind", sa.SmallInteger(), nullable=True),
        sa.Column("token_expires_at", DATETIME_UTC, nullable=True),
        sa.Column("token_categories", sa.JSON(), nullable=False),
        sa.Column("token_checked_at", DATETIME_UTC, nullable=True),
        sa.Column("sandbox", sa.Boolean(), nullable=False),
        sa.Column("created_at", DATETIME_UTC, nullable=False),
        sa.Column("updated_at", DATETIME_UTC, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_shops_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shops")),
        sa.UniqueConstraint("user_id", "seller_id", name=op.f("uq_shops_user_id_seller_id")),
    )
    op.create_index(op.f("ix_shops_user_id"), "shops", ["user_id"], unique=False)
    op.create_table(
        "analysis_runs",
        sa.Column("id", BIGINT, autoincrement=True, nullable=False),
        sa.Column("shop_id", BIGINT, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("period_days", sa.SmallInteger(), nullable=False),
        sa.Column("progress", sa.SmallInteger(), nullable=False),
        sa.Column("stage", sa.String(length=255), nullable=True),
        sa.Column("created_at", DATETIME_UTC, nullable=False),
        sa.Column("started_at", DATETIME_UTC, nullable=True),
        sa.Column("finished_at", DATETIME_UTC, nullable=True),
        sa.Column("heartbeat_at", DATETIME_UTC, nullable=True),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column("report_text", LONG_TEXT, nullable=True),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name=op.f("fk_analysis_runs_shop_id_shops"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_runs")),
    )
    op.create_index(op.f("ix_analysis_runs_shop_id"), "analysis_runs", ["shop_id"], unique=False)
    op.create_index(
        op.f("ix_analysis_runs_status_created_at"),
        "analysis_runs",
        ["status", "created_at"],
        unique=False,
    )
    op.create_table(
        "cost_prices",
        sa.Column("id", BIGINT, autoincrement=True, nullable=False),
        sa.Column("shop_id", BIGINT, nullable=False),
        sa.Column("vendor_code", sa.String(length=100), nullable=False),
        sa.Column("cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("uploaded_at", DATETIME_UTC, nullable=False),
        sa.ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name=op.f("fk_cost_prices_shop_id_shops"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cost_prices")),
        sa.UniqueConstraint(
            "shop_id", "vendor_code", name=op.f("uq_cost_prices_shop_id_vendor_code")
        ),
    )
    op.create_table(
        "check_results",
        sa.Column("id", BIGINT, autoincrement=True, nullable=False),
        sa.Column("run_id", BIGINT, nullable=False),
        sa.Column("check_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_check_results_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_check_results")),
        sa.UniqueConstraint("run_id", "check_id", name=op.f("uq_check_results_run_id_check_id")),
    )
    op.create_table(
        "run_datasets",
        sa.Column("id", BIGINT, autoincrement=True, nullable=False),
        sa.Column("run_id", BIGINT, nullable=False),
        sa.Column("dataset", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_run_datasets_run_id_analysis_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run_datasets")),
        sa.UniqueConstraint("run_id", "dataset", name=op.f("uq_run_datasets_run_id_dataset")),
    )
    op.create_table(
        "findings",
        sa.Column("id", BIGINT, autoincrement=True, nullable=False),
        sa.Column("check_result_id", BIGINT, nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("products", sa.JSON(), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("caveat", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["check_result_id"],
            ["check_results.id"],
            name=op.f("fk_findings_check_result_id_check_results"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_findings")),
    )
    op.create_index(
        op.f("ix_findings_check_result_id"), "findings", ["check_result_id"], unique=False
    )


def downgrade() -> None:
    # Индексы удаляются вместе с таблицами (в MySQL индекс внешнего ключа отдельно не удалить).
    op.drop_table("findings")
    op.drop_table("run_datasets")
    op.drop_table("check_results")
    op.drop_table("cost_prices")
    op.drop_table("analysis_runs")
    op.drop_table("shops")
    op.drop_table("users")
    op.drop_table("login_attempts")
