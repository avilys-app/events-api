"""Add terms acceptance and marketing consent to users.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("terms_accepted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("terms_version", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "marketing_consent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("marketing_consent_updated_at", sa.DateTime(), nullable=True),
    )

    # All existing accounts are pre-live test/admin users. Record the deployment
    # as their v1 acceptance time without opting any of them into marketing.
    op.execute(
        "UPDATE users SET terms_accepted_at = CURRENT_TIMESTAMP, terms_version = 'v1'"
    )
    op.alter_column("users", "terms_accepted_at", nullable=False)
    op.alter_column("users", "terms_version", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "marketing_consent_updated_at")
    op.drop_column("users", "marketing_consent")
    op.drop_column("users", "terms_version")
    op.drop_column("users", "terms_accepted_at")
