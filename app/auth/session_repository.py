"""Data access for refresh-token sessions."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshTokenSession


async def create(
    session: AsyncSession,
    *,
    user_id: int,
    token_hash: str,
    expires_at: datetime,
) -> RefreshTokenSession:
    refresh_session = RefreshTokenSession(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(refresh_session)
    await session.flush()
    return refresh_session


async def get_for_update(
    session: AsyncSession, token_hash: str
) -> RefreshTokenSession | None:
    found: RefreshTokenSession | None = await session.scalar(
        select(RefreshTokenSession)
        .where(RefreshTokenSession.token_hash == token_hash)
        .with_for_update()
    )
    return found


def rotate(
    refresh_session: RefreshTokenSession,
    *,
    token_hash: str,
    expires_at: datetime,
    now: datetime,
) -> None:
    refresh_session.token_hash = token_hash
    refresh_session.expires_at = expires_at
    refresh_session.updated_at = now


def revoke(refresh_session: RefreshTokenSession, *, now: datetime) -> None:
    refresh_session.revoked_at = now
    refresh_session.updated_at = now
