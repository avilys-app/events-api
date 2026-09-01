"""Add email confirmation state and tokens.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "preferred_locale",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'en'"),
        ),
    )
    op.create_check_constraint(
        "ck_users_preferred_locale",
        "users",
        "preferred_locale IN ('en', 'lt')",
    )
    op.execute("UPDATE users SET email_verified_at = created_at")

    op.create_table(
        "email_confirmation_tokens",
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
        "ix_email_confirmation_tokens_user_id",
        "email_confirmation_tokens",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "ix_email_confirmation_tokens_token_hash",
        "email_confirmation_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_confirmation_tokens_token_hash", table_name="email_confirmation_tokens"
    )
    op.drop_index(
        "ix_email_confirmation_tokens_user_id", table_name="email_confirmation_tokens"
    )
    op.drop_table("email_confirmation_tokens")
    op.drop_constraint("ck_users_preferred_locale", "users", type_="check")
    op.drop_column("users", "preferred_locale")
    op.drop_column("users", "email_verified_at")
