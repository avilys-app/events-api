"""User account lifecycle operations."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.users import repository as users
from app.users.models import User

INVALID_CURRENT_PASSWORD = "Current password is incorrect"


async def delete_account(
    session: AsyncSession,
    user: User,
    password: str,
) -> None:
    """Permanently delete an account after confirming its current password."""
    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_CURRENT_PASSWORD,
        )

    await users.delete_user(session, user)
