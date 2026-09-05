"""Add password reset tokens and outbox linkage.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_password_reset_tokens_user_id",
        "password_reset_tokens",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "ix_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )

    op.add_column(
        "email_outbox_jobs",
        sa.Column("password_reset_token_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_email_outbox_jobs_password_reset_token_id",
        "email_outbox_jobs",
        "password_reset_tokens",
        ["password_reset_token_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_email_outbox_jobs_password_reset_token_id",
        "email_outbox_jobs",
        ["password_reset_token_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_outbox_jobs_password_reset_token_id",
        table_name="email_outbox_jobs",
    )
    op.drop_constraint(
        "fk_email_outbox_jobs_password_reset_token_id",
        "email_outbox_jobs",
        type_="foreignkey",
    )
    op.drop_column("email_outbox_jobs", "password_reset_token_id")
    op.drop_index(
        "ix_password_reset_tokens_token_hash",
        table_name="password_reset_tokens",
    )
    op.drop_index(
        "ix_password_reset_tokens_user_id",
        table_name="password_reset_tokens",
    )
    op.drop_table("password_reset_tokens")
