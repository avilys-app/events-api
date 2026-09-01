"""Event ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Numeric, Text, and_, func, or_
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import ColumnElement

from app.core.database import Base

#: Substring in an event description that implies it is ticketed even when no
#: price column was populated. "kaina" is Lithuanian for "price".
PRICE_MENTION = "kaina"


class Event(Base):
    """An event aggregated from an external source.

    Rows are written by the upstream ingest process, not by this API, which
    exposes reads only.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)

    popularity_counter: Mapped[int] = mapped_column(
        Numeric(asdecimal=False), default=0, server_default="0"
    )

    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime)

    venue_name: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)

    lat: Mapped[float | None] = mapped_column(Numeric(asdecimal=False))
    lng: Mapped[float | None] = mapped_column(Numeric(asdecimal=False))

    description: Mapped[str | None] = mapped_column(Text)

    image_url: Mapped[str | None] = mapped_column(Text)
    #: Re-hosted copy of ``image_url``, preferred when present.
    image_url_stored: Mapped[str | None] = mapped_column(Text)

    price_from: Mapped[float | None] = mapped_column(Numeric(asdecimal=False))
    price_to: Mapped[float | None] = mapped_column(Numeric(asdecimal=False))

    organizer_name: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)

    ticket_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    ticket_purchase_note: Mapped[str | None] = mapped_column(Text)

    #: Set by the ingest process to collapse the same event from many sources.
    dedup_key: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    @hybrid_property
    def is_free(self) -> bool:
        """Whether the event carries no evidence of costing money.

        Evaluates in Python against a loaded instance and compiles to SQL for
        filtering and ordering, so the rule has exactly one definition.
        """
        return (
            not self.price_from
            and not self.price_to
            and not self.ticket_url
            and not self.ticket_purchase_note
            and PRICE_MENTION not in (self.description or "").casefold()
        )

    @is_free.inplace.expression
    @classmethod
    def _is_free_expression(cls) -> ColumnElement[bool]:
        return and_(
            or_(cls.price_from.is_(None), cls.price_from == 0),
            or_(cls.price_to.is_(None), cls.price_to == 0),
            cls.ticket_url.is_(None),
            cls.ticket_purchase_note.is_(None),
            or_(cls.description.is_(None), ~cls.description.ilike(f"%{PRICE_MENTION}%")),
        )

    @property
    def display_address(self) -> str | None:
        """Street address, falling back to the venue name."""
        return self.address or self.venue_name

    @property
    def preferred_image_url(self) -> str | None:
        """Re-hosted image if one exists, otherwise the original source URL."""
        return self.image_url_stored or self.image_url
