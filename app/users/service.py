"""User account lifecycle operations."""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.users import repository as users
from app.users.models import User
from app.users.schemas import (
    MarketingConsentsResponse,
    MarketingConsentsUpdateRequest,
)

INVALID_CURRENT_PASSWORD = "Current password is incorrect"


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def update_marketing_consents(
    session: AsyncSession,
    user: User,
    payload: MarketingConsentsUpdateRequest,
) -> MarketingConsentsResponse:
    """Update only the marketing channels supplied by the user."""
    updated = await users.update_marketing_consents(
        session,
        user,
        marketing_email_consent=payload.marketing_email_consent,
        marketing_push_consent=payload.marketing_push_consent,
        updated_at=_utc_now(),
    )
    return MarketingConsentsResponse.model_validate(updated)


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
