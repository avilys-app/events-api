"""User ORM model."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """A registered user."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "preferred_locale IN ('en', 'lt')",
            name="ck_users_preferred_locale",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    first_name: Mapped[str] = mapped_column(Text)
    last_name: Mapped[str] = mapped_column(Text)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    preferred_locale: Mapped[str] = mapped_column(Text, server_default=text("'en'"))

    #: Denormalised list of favorited event ids. Kept as an array because the
    #: favorites endpoints only ever read the whole set; a join table would add
    #: referential integrity, which this cannot enforce.
    favorite_event_ids: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), server_default=text("'{}'::int[]")
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class EmailConfirmationToken(Base):
    """A short-lived, single-use token for confirming a user's email address."""

    __tablename__ = "email_confirmation_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
