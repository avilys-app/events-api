"""Data access for users."""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import User


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    found: User | None = await session.scalar(select(User).where(User.email == email))
    return found


async def get(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def create(
    session: AsyncSession,
    *,
    email: str,
    password_hash: str,
    first_name: str,
    last_name: str,
    preferred_locale: str,
) -> User:
    user = User(
        email=email,
        password_hash=password_hash,
        first_name=first_name,
        last_name=last_name,
        preferred_locale=preferred_locale,
        favorite_event_ids=[],
    )
    session.add(user)
    await session.flush()
    return user


async def add_favorite(session: AsyncSession, user: User, event_id: int) -> User:
    """Append an event to the user's favorites, ignoring duplicates.

    Uses Postgres array functions so two concurrent requests cannot overwrite
    each other, which a read-modify-write in Python would allow.
    """
    await session.execute(
        update(User)
        .where(User.id == user.id)
        .where(~User.favorite_event_ids.contains([event_id]))
        # SQL array concatenation, not a Python list -- RUF005 does not apply.
        .values(favorite_event_ids=User.favorite_event_ids + [event_id])  # noqa: RUF005
    )
    await session.commit()
    await session.refresh(user)
    return user


async def remove_favorite(session: AsyncSession, user: User, event_id: int) -> User:
    """Remove an event from the user's favorites, ignoring absences."""
    await session.execute(
        update(User)
        .where(User.id == user.id)
        .values(favorite_event_ids=func.array_remove(User.favorite_event_ids, event_id))
    )
    await session.commit()
    await session.refresh(user)
    return user
