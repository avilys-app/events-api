"""Add the durable email outbox.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_outbox_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "confirmation_token_id",
            sa.Integer(),
            sa.ForeignKey("email_confirmation_tokens.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("to_address", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("lock_token", sa.Text(), nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_email_outbox_jobs_confirmation_token_id",
        "email_outbox_jobs",
        ["confirmation_token_id"],
        unique=True,
    )
    op.create_index(
        "ix_email_outbox_jobs_idempotency_key",
        "email_outbox_jobs",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_email_outbox_jobs_next_attempt_at",
        "email_outbox_jobs",
        ["next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_email_outbox_jobs_next_attempt_at", table_name="email_outbox_jobs")
    op.drop_index("ix_email_outbox_jobs_idempotency_key", table_name="email_outbox_jobs")
    op.drop_index(
        "ix_email_outbox_jobs_confirmation_token_id",
        table_name="email_outbox_jobs",
    )
    op.drop_table("email_outbox_jobs")
