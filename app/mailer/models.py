"""Durable email delivery jobs."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmailOutboxJob(Base):
    """An email waiting for provider acceptance."""

    __tablename__ = "email_outbox_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    confirmation_token_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_confirmation_tokens.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        index=True,
    )
    to_address: Mapped[str] = mapped_column(Text)
    reply_to_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str] = mapped_column(Text)
    text_body: Mapped[str] = mapped_column(Text)
    html_body: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True, index=True)
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        index=True,
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lock_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
