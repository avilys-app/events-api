"""Generalize the email outbox for report emails.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "email_outbox_jobs",
        "confirmation_token_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.add_column(
        "email_outbox_jobs",
        sa.Column("reply_to_address", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    # Report jobs have no confirmation token and cannot exist in the old schema.
    jobs = sa.table("email_outbox_jobs", sa.column("confirmation_token_id"))
    op.execute(jobs.delete().where(jobs.c.confirmation_token_id.is_(None)))
    op.drop_column("email_outbox_jobs", "reply_to_address")
    op.alter_column(
        "email_outbox_jobs",
        "confirmation_token_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
