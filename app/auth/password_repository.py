"""Data access for password-reset tokens."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import PasswordResetToken


async def get_for_update(
    session: AsyncSession, token_hash: str
) -> PasswordResetToken | None:
    found: PasswordResetToken | None = await session.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
    )
    return found


async def get_for_user(
    session: AsyncSession, user_id: int
) -> PasswordResetToken | None:
    found: PasswordResetToken | None = await session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
    )
    return found


async def replace(
    session: AsyncSession,
    *,
    user_id: int,
    token_hash: str,
    expires_at: datetime,
) -> PasswordResetToken:
    await delete_for_user(session, user_id)
    token = PasswordResetToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(token)
    await session.flush()
    return token


async def delete_for_user(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
    )
