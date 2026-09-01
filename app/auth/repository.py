"""Data access for email confirmation tokens."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import EmailConfirmationToken


async def get_for_update(
    session: AsyncSession, token_hash: str
) -> EmailConfirmationToken | None:
    found: EmailConfirmationToken | None = await session.scalar(
        select(EmailConfirmationToken)
        .where(EmailConfirmationToken.token_hash == token_hash)
        .with_for_update()
    )
    return found


async def get_for_user(
    session: AsyncSession, user_id: int
) -> EmailConfirmationToken | None:
    found: EmailConfirmationToken | None = await session.scalar(
        select(EmailConfirmationToken).where(EmailConfirmationToken.user_id == user_id)
    )
    return found


async def replace(
    session: AsyncSession,
    *,
    user_id: int,
    token_hash: str,
    expires_at: datetime,
) -> EmailConfirmationToken:
    await delete_for_user(session, user_id)
    token = EmailConfirmationToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(token)
    await session.flush()
    return token


async def delete_for_user(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        delete(EmailConfirmationToken).where(EmailConfirmationToken.user_id == user_id)
    )
