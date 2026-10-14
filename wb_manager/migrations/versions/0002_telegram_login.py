"""Вход через Telegram: id и телефон пользователя, email и пароль необязательны;
чат и сообщение для прогресса анализа.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


BIGINT = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
DATETIME_UTC = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    # batch_alter_table: в MySQL — обычные ALTER, в SQLite — пересоздание таблицы.
    with op.batch_alter_table("analysis_runs") as batch:
        batch.add_column(sa.Column("notify_chat_id", BIGINT, nullable=True))
        batch.add_column(sa.Column("notify_message_id", BIGINT, nullable=True))

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("telegram_user_id", BIGINT, nullable=True))
        batch.add_column(sa.Column("phone", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("name", sa.String(length=255), nullable=True))
        batch.alter_column("email", existing_type=sa.String(length=254), nullable=True)
        batch.alter_column("password_hash", existing_type=sa.String(length=255), nullable=True)
        batch.drop_constraint("uq_users_telegram_link_code", type_="unique")
        batch.drop_column("telegram_link_expires_at")
        batch.drop_column("telegram_link_code")
        batch.create_unique_constraint("uq_users_telegram_user_id", ["telegram_user_id"])


def downgrade() -> None:
    # Откат возможен, только если у всех пользователей есть email и пароль.
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_telegram_user_id", type_="unique")
        batch.add_column(sa.Column("telegram_link_code", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("telegram_link_expires_at", DATETIME_UTC, nullable=True))
        batch.create_unique_constraint("uq_users_telegram_link_code", ["telegram_link_code"])
        batch.alter_column("password_hash", existing_type=sa.String(length=255), nullable=False)
        batch.alter_column("email", existing_type=sa.String(length=254), nullable=False)
        batch.drop_column("name")
        batch.drop_column("phone")
        batch.drop_column("telegram_user_id")

    with op.batch_alter_table("analysis_runs") as batch:
        batch.drop_column("notify_message_id")
        batch.drop_column("notify_chat_id")
