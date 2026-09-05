"""Authenticated user profile lifecycle."""

from datetime import timedelta

from app.auth.models import PasswordResetToken, RefreshTokenSession
from app.core.security import hash_password
from app.mailer.models import EmailOutboxJob
from app.users.models import EmailConfirmationToken, User
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import NOW


async def test_delete_account_requires_authentication(client: AsyncClient) -> None:
    response = await client.request(
        "DELETE",
        "/api/users/profile",
        json={"password": "correct-horse"},
    )

    assert response.status_code == 401


async def test_delete_account_rejects_incorrect_password(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    response = await client.request(
        "DELETE",
        "/api/users/profile",
        headers=auth_headers,
        json={"password": "wrong-password"},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Current password is incorrect"
    assert await session.get(User, user.id) is not None
    refresh_session = await session.scalar(select(RefreshTokenSession))
    assert refresh_session is not None
    assert refresh_session.revoked_at is None


async def test_delete_account_removes_user_authentication_data_and_sessions(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    second_login = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "correct-horse"},
    )
    refresh_token = second_login.json()["refreshToken"]
    await client.post("/api/auth/forgot-password", json={"email": user.email})
    session.add(
        EmailConfirmationToken(
            user_id=user.id,
            token_hash="confirmation-token-hash",
            expires_at=NOW + timedelta(days=1),
        )
    )
    other = User(
        email="other@example.com",
        password_hash=hash_password("other-password"),
        first_name="Other",
        last_name="User",
        email_verified_at=NOW,
        favorite_event_ids=[],
    )
    session.add(other)
    await session.commit()
    await session.refresh(other)

    response = await client.request(
        "DELETE",
        "/api/users/profile",
        headers=auth_headers,
        json={"password": "correct-horse"},
    )

    assert response.status_code == 204
    assert response.content == b""
    assert await session.get(User, user.id) is None
    assert await session.get(User, other.id) is not None
    assert await session.scalar(
        select(EmailConfirmationToken).where(EmailConfirmationToken.user_id == user.id)
    ) is None
    assert await session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    ) is None
    assert await session.scalar(
        select(RefreshTokenSession).where(RefreshTokenSession.user_id == user.id)
    ) is None
    assert await session.scalar(select(EmailOutboxJob)) is None

    assert (
        await client.get("/api/users/profile", headers=auth_headers)
    ).status_code == 401
    assert (
        await client.post(
            "/api/auth/refresh",
            json={"refreshToken": refresh_token},
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "correct-horse"},
        )
    ).status_code == 401
