"""Legal page ORM model."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LegalPage(Base):
    """A localized legal document."""

    __tablename__ = "legal_pages"
    __table_args__ = (
        UniqueConstraint("slug", "locale", name="uq_legal_pages_slug_locale"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    slug: Mapped[str] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
