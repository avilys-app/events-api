"""Registration and login."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenClaims, create_access_token, hash_password, verify_password
from app.users import repository as users
from app.users.models import User
from app.users.schemas import AuthResponse, RegisterRequest, UserResponse

INVALID_CREDENTIALS = "Invalid email or password"


def issue_token(user: User) -> AuthResponse:
    claims = TokenClaims(sub=user.id, email=user.email)
    return AuthResponse(
        access_token=create_access_token(claims),
        user=UserResponse.model_validate(user),
    )


async def register(session: AsyncSession, payload: RegisterRequest) -> AuthResponse:
    if await users.get_by_email(session, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = await users.create(
        session,
        email=payload.email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    return issue_token(user)


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    """Verify credentials, failing identically whether the email or password is wrong."""
    user = await users.get_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
        )
    return user


async def login(session: AsyncSession, email: str, password: str) -> AuthResponse:
    return issue_token(await authenticate(session, email, password))
