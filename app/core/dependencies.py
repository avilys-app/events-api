"""Shared FastAPI dependencies."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import decode_access_token
from app.users.models import User

DbSession = Annotated[AsyncSession, Depends(get_db_session)]

_bearer_scheme = HTTPBearer(auto_error=False, description="JWT from /api/auth/login")


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> User:
    """Resolve the bearer token to a user, or reject the request."""
    if credentials is None:
        raise _unauthorized()

    try:
        claims = decode_access_token(credentials.credentials)
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise _unauthorized() from exc

    user = await session.get(User, claims["sub"])
    if user is None or user.email_verified_at is None:
        raise _unauthorized()

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
