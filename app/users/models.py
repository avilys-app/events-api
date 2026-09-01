"""User ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """A registered user."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    first_name: Mapped[str] = mapped_column(Text)
    last_name: Mapped[str] = mapped_column(Text)

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
