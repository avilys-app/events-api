"""Data access for legal documents."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.legal.models import LegalPage

TERMS_SLUG = "terms-and-conditions"


async def get_terms_version(session: AsyncSession, locale: str) -> str | None:
    """Return the published Terms version for a locale."""
    version: str | None = await session.scalar(
        select(LegalPage.version)
        .where(LegalPage.slug == TERMS_SLUG, LegalPage.locale == locale)
        .limit(1)
    )
    return version
