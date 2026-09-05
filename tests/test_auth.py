"""Registration, login, and token handling."""

import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from app.auth.models import PasswordResetToken, RefreshTokenSession
from app.auth.service import _confirmation_timestamp
from app.core.security import TokenClaims, create_access_token, hash_refresh_token
from app.mailer.models import EmailOutboxJob
from app.users.models import EmailConfirmationToken, User
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import NOW
from tests.fakes import RecordingEmailSender

REGISTRATION = {
    "email": "new@example.com",
    "password": "long-enough-password",
    "firstName": "New",
    "lastName": "Person",
}


def test_confirmation_timestamp_uses_locale_time_zone() -> None:
    requested_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

    assert _confirmation_timestamp(requested_at, "en") == "2026-06-01 12:00 UTC"
    assert _confirmation_timestamp(requested_at, "lt") == "2026-06-01 15:00 EEST"


def confirmation_token(text: str) -> str:
    url = next(line for line in text.splitlines() if "token=" in line)
    return parse_qs(urlsplit(url).query)["token"][0]


async def queued_email(session: AsyncSession) -> EmailOutboxJob:
    job = await session.scalar(select(EmailOutboxJob))
    assert job is not None
    return job


async def test_register_creates_unverified_user_and_queues_confirmation(
    client: AsyncClient,
    session: AsyncSession,
    email_sender: RecordingEmailSender,
) -> None:
    response = await client.post("/api/auth/register", json=REGISTRATION)

    assert response.status_code == 201
    assert response.json() == {
        "message": "Registration successful. Check your email to confirm your account."
    }
    user = await session.scalar(select(User).where(User.email == REGISTRATION["email"]))
    assert user is not None
    assert user.email_verified_at is None
    assert user.preferred_locale == "en"
    assert email_sender.messages == []
    message = await queued_email(session)
    assert message.to_address == REGISTRATION["email"]
    assert message.subject == "Confirm your email address"
    assert "Link requested at:" in message.text_body
    assert "Link requested at:" in message.html_body
    assert confirmation_token(message.text_body)


async def test_register_sends_lithuanian_confirmation_email(
    client: AsyncClient,
    session: AsyncSession,
    email_sender: RecordingEmailSender,
) -> None:
    response = await client.post(
        "/api/auth/register", json={**REGISTRATION, "locale": "lt"}
    )

    assert response.status_code == 201
    user = await session.scalar(select(User).where(User.email == REGISTRATION["email"]))
    assert user is not None
    assert user.preferred_locale == "lt"
    message = await queued_email(session)
    assert message.subject == "Patvirtinkite el. pašto adresą"
    assert "Patvirtinkite savo el. pašto adresą" in message.text_body
    assert "Nuorodos užklausa pateikta:" in message.text_body
    assert "Patvirtinti el. pašto adresą" in message.html_body
    assert "Nuorodos užklausa pateikta:" in message.html_body


async def test_register_falls_back_to_english_for_unsupported_locale(
    client: AsyncClient,
    session: AsyncSession,
    email_sender: RecordingEmailSender,
) -> None:
    response = await client.post(
        "/api/auth/register", json={**REGISTRATION, "locale": "de"}
    )

    assert response.status_code == 201
    user = await session.scalar(select(User).where(User.email == REGISTRATION["email"]))
    assert user is not None
    assert user.preferred_locale == "en"
    assert (await queued_email(session)).subject == "Confirm your email address"


async def test_register_rejects_duplicate_email(client: AsyncClient) -> None:
    await client.post("/api/auth/register", json=REGISTRATION)
    response = await client.post("/api/auth/register", json=REGISTRATION)

    assert response.status_code == 409
    assert response.json() == {
        "statusCode": 409,
        "message": "A user with this email already exists",
        "error": "Conflict",
    }


async def test_register_rejects_short_password(client: AsyncClient) -> None:
    response = await client.post("/api/auth/register", json={**REGISTRATION, "password": "short"})

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "Bad Request"
    assert isinstance(body["message"], list)


async def test_register_does_not_call_email_provider_during_request(
    client: AsyncClient,
    session: AsyncSession,
    email_sender: RecordingEmailSender,
) -> None:
    email_sender.should_fail = True

    response = await client.post("/api/auth/register", json=REGISTRATION)

    assert response.status_code == 201
    assert await session.scalar(select(User).where(User.email == REGISTRATION["email"]))
    assert await session.scalar(select(EmailOutboxJob))
    assert email_sender.messages == []


async def test_unconfirmed_user_cannot_login(
    client: AsyncClient, email_sender: RecordingEmailSender
) -> None:
    await client.post("/api/auth/register", json=REGISTRATION)

    response = await client.post(
        "/api/auth/login",
        json={"email": REGISTRATION["email"], "password": REGISTRATION["password"]},
    )

    assert response.status_code == 403
    assert response.json() == {
        "statusCode": 403,
        "message": "Email address has not been confirmed",
        "error": "Forbidden",
    }


async def test_confirm_email_enables_login(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await client.post("/api/auth/register", json=REGISTRATION)

    token = confirmation_token((await queued_email(session)).text_body)
    confirmation = await client.post("/api/auth/confirm-email", json={"token": token})
    login = await client.post(
        "/api/auth/login",
        json={"email": REGISTRATION["email"], "password": REGISTRATION["password"]},
    )

    assert confirmation.status_code == 204
    assert login.status_code == 200
    assert login.json()["accessToken"]


async def test_confirmation_token_is_single_use(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    await client.post("/api/auth/register", json=REGISTRATION)
    token = confirmation_token((await queued_email(session)).text_body)
    assert (await client.post("/api/auth/confirm-email", json={"token": token})).status_code == 204

    reused = await client.post("/api/auth/confirm-email", json={"token": token})

    assert reused.status_code == 400
    assert reused.json()["message"] == "Invalid or expired confirmation token"


async def test_expired_confirmation_token_is_rejected(
    client: AsyncClient,
    session: AsyncSession,
    email_sender: RecordingEmailSender,
) -> None:
    await client.post("/api/auth/register", json=REGISTRATION)
    stored = await session.scalar(select(EmailConfirmationToken))
    assert stored is not None
    stored.expires_at = NOW - timedelta(seconds=1)
    await session.commit()

    response = await client.post(
        "/api/auth/confirm-email",
        json={"token": confirmation_token((await queued_email(session)).text_body)},
    )

    assert response.status_code == 400


async def test_resend_replaces_previous_confirmation_token(
    client: AsyncClient,
    session: AsyncSession,
    email_sender: RecordingEmailSender,
) -> None:
    await client.post("/api/auth/register", json={**REGISTRATION, "locale": "lt"})
    old_token = confirmation_token((await queued_email(session)).text_body)
    stored = await session.scalar(select(EmailConfirmationToken))
    assert stored is not None
    stored.created_at = NOW - timedelta(minutes=2)
    await session.commit()

    response = await client.post(
        "/api/auth/resend-confirmation", json={"email": REGISTRATION["email"]}
    )

    assert response.status_code == 202
    assert email_sender.messages == []
    replacement = await queued_email(session)
    assert replacement.subject == "Patvirtinkite el. pašto adresą"
    assert confirmation_token(replacement.text_body) != old_token
    assert (
        await client.post("/api/auth/confirm-email", json={"token": old_token})
    ).status_code == 400


async def test_resend_does_not_reveal_account_status(
    client: AsyncClient, user: User
) -> None:
    unknown = await client.post(
        "/api/auth/resend-confirmation", json={"email": "nobody@example.com"}
    )
    verified = await client.post(
        "/api/auth/resend-confirmation", json={"email": user.email}
    )

    assert unknown.status_code == verified.status_code == 202
    assert unknown.json() == verified.json()


async def test_forgot_password_queues_reset_email_and_stores_only_token_hash(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
) -> None:
    response = await client.post(
        "/api/auth/forgot-password", json={"email": user.email}
    )

    assert response.status_code == 202
    assert response.json() == {
        "message": "If the account exists, a password reset email has been sent."
    }
    stored = await session.scalar(select(PasswordResetToken))
    message = await queued_email(session)
    assert stored is not None
    assert message.password_reset_token_id == stored.id
    assert message.confirmation_token_id is None
    assert message.subject == "Reset your password"
    raw_token = confirmation_token(message.text_body)
    assert stored.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()
    assert raw_token not in stored.token_hash


async def test_forgot_password_uses_saved_lithuanian_locale(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
) -> None:
    user.preferred_locale = "lt"
    await session.commit()

    response = await client.post(
        "/api/auth/forgot-password", json={"email": user.email}
    )

    assert response.status_code == 202
    message = await queued_email(session)
    assert message.subject == "Atkurkite savo slaptažodį"
    assert "pasirinkite naują slaptažodį" in message.text_body
    assert "Jei to neprašėte" in message.text_body
    assert "Nuorodos užklausa pateikta:" in message.text_body


async def test_forgot_password_does_not_reveal_account_or_confirmation_status(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
) -> None:
    unknown = await client.post(
        "/api/auth/forgot-password", json={"email": "nobody@example.com"}
    )
    user.email_verified_at = None
    await session.commit()
    unconfirmed = await client.post(
        "/api/auth/forgot-password", json={"email": user.email}
    )

    assert unknown.status_code == unconfirmed.status_code == 202
    assert unknown.json() == unconfirmed.json()
    assert await session.scalar(select(PasswordResetToken)) is None
    assert await session.scalar(select(EmailOutboxJob)) is None


async def test_forgot_password_observes_cooldown(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
) -> None:
    await client.post("/api/auth/forgot-password", json={"email": user.email})
    original = await session.scalar(select(PasswordResetToken))
    assert original is not None

    response = await client.post(
        "/api/auth/forgot-password", json={"email": user.email}
    )

    assert response.status_code == 202
    assert (await session.scalars(select(PasswordResetToken))).all() == [original]
    assert len((await session.scalars(select(EmailOutboxJob))).all()) == 1


async def test_forgot_password_replaces_old_token_and_pending_email_after_cooldown(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
) -> None:
    await client.post("/api/auth/forgot-password", json={"email": user.email})
    old_raw_token = confirmation_token((await queued_email(session)).text_body)
    old = await session.scalar(select(PasswordResetToken))
    assert old is not None
    old.created_at = NOW - timedelta(minutes=2)
    await session.commit()

    await client.post("/api/auth/forgot-password", json={"email": user.email})

    replacement = await session.scalar(select(PasswordResetToken))
    jobs = (await session.scalars(select(EmailOutboxJob))).all()
    assert replacement is not None
    assert replacement.id != old.id
    assert len(jobs) == 1
    assert jobs[0].password_reset_token_id == replacement.id
    rejected = await client.post(
        "/api/auth/reset-password",
        json={"token": old_raw_token, "newPassword": "new-password"},
    )
    assert rejected.status_code == 400


async def test_reset_password_changes_password_consumes_token_and_revokes_sessions(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
) -> None:
    first_login = await client.post(
        "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
    )
    second_login = await client.post(
        "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
    )
    await client.post("/api/auth/forgot-password", json={"email": user.email})
    raw_token = confirmation_token((await queued_email(session)).text_body)

    response = await client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "newPassword": "brand-new-password"},
    )

    assert response.status_code == 204
    assert response.content == b""
    assert await session.scalar(select(PasswordResetToken)) is None
    assert await session.scalar(select(EmailOutboxJob)) is None
    refresh_sessions = (await session.scalars(select(RefreshTokenSession))).all()
    assert len(refresh_sessions) == 2
    assert all(item.revoked_at is not None for item in refresh_sessions)
    assert (
        await client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "correct-horse"},
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "brand-new-password"},
        )
    ).status_code == 200
    for login in (first_login, second_login):
        assert (
            await client.post(
                "/api/auth/refresh",
                json={"refreshToken": login.json()["refreshToken"]},
            )
        ).status_code == 401
    assert (
        await client.post(
            "/api/auth/reset-password",
            json={"token": raw_token, "newPassword": "another-password"},
        )
    ).status_code == 400


async def test_expired_password_reset_token_is_rejected(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
) -> None:
    await client.post("/api/auth/forgot-password", json={"email": user.email})
    raw_token = confirmation_token((await queued_email(session)).text_body)
    stored = await session.scalar(select(PasswordResetToken))
    assert stored is not None
    stored.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
    await session.commit()

    response = await client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "newPassword": "brand-new-password"},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Invalid or expired password reset token"
    assert (
        await client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "correct-horse"},
        )
    ).status_code == 200


async def test_reset_password_rejects_short_new_password(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
) -> None:
    await client.post("/api/auth/forgot-password", json={"email": user.email})
    raw_token = confirmation_token((await queued_email(session)).text_body)

    response = await client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "newPassword": "short"},
    )

    assert response.status_code == 400
    assert await session.scalar(select(PasswordResetToken)) is not None


async def test_change_password_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/change-password",
        json={"currentPassword": "correct-horse", "newPassword": "brand-new-password"},
    )

    assert response.status_code == 401


async def test_change_password_rejects_incorrect_current_password(
    client: AsyncClient,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/auth/change-password",
        headers=auth_headers,
        json={"currentPassword": "wrong-password", "newPassword": "brand-new-password"},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Current password is incorrect"
    assert (
        await client.post(
            "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
        )
    ).status_code == 200


async def test_change_password_rejects_current_password_as_replacement(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/auth/change-password",
        headers=auth_headers,
        json={"currentPassword": "correct-horse", "newPassword": "correct-horse"},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "New password must be different from the current password"


async def test_change_password_updates_password_and_revokes_sessions_and_reset_token(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    await client.post("/api/auth/forgot-password", json={"email": user.email})

    response = await client.post(
        "/api/auth/change-password",
        headers=auth_headers,
        json={"currentPassword": "correct-horse", "newPassword": "brand-new-password"},
    )

    assert response.status_code == 204
    assert response.content == b""
    assert await session.scalar(select(PasswordResetToken)) is None
    assert await session.scalar(select(EmailOutboxJob)) is None
    refresh_sessions = (await session.scalars(select(RefreshTokenSession))).all()
    assert refresh_sessions
    assert all(item.revoked_at is not None for item in refresh_sessions)
    assert (
        await client.post(
            "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "brand-new-password"},
        )
    ).status_code == 200


async def test_login_succeeds_with_correct_password(client: AsyncClient, user: User) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
    )

    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.id
    assert response.json()["accessToken"]
    assert response.json()["refreshToken"]


async def test_login_stores_only_refresh_token_hash(
    client: AsyncClient, session: AsyncSession, user: User
) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
    )
    raw_token = response.json()["refreshToken"]
    stored = await session.scalar(select(RefreshTokenSession))

    assert stored is not None
    assert stored.user_id == user.id
    assert stored.token_hash == hash_refresh_token(raw_token)
    assert stored.token_hash != raw_token
    assert stored.revoked_at is None
    assert stored.expires_at > datetime.now(UTC).replace(tzinfo=None) + timedelta(days=179)


async def test_refresh_rotates_both_tokens_and_extends_sliding_expiry(
    client: AsyncClient, session: AsyncSession, user: User
) -> None:
    login = await client.post(
        "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
    )
    old_access = login.json()["accessToken"]
    old_refresh = login.json()["refreshToken"]
    stored = await session.scalar(select(RefreshTokenSession))
    assert stored is not None
    stored.expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
    await session.commit()
    previous_expiry = stored.expires_at

    response = await client.post(
        "/api/auth/refresh", json={"refreshToken": old_refresh}
    )

    assert response.status_code == 200
    assert response.json()["accessToken"] != old_access
    assert response.json()["refreshToken"] != old_refresh
    assert response.json()["user"]["id"] == user.id
    await session.refresh(stored)
    assert stored.token_hash == hash_refresh_token(response.json()["refreshToken"])
    assert stored.expires_at > previous_expiry


async def test_rotated_refresh_token_cannot_be_reused(
    client: AsyncClient, user: User
) -> None:
    login = await client.post(
        "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
    )
    old_token = login.json()["refreshToken"]
    rotated = await client.post(
        "/api/auth/refresh", json={"refreshToken": old_token}
    )

    reused = await client.post(
        "/api/auth/refresh", json={"refreshToken": old_token}
    )
    current = await client.post(
        "/api/auth/refresh",
        json={"refreshToken": rotated.json()["refreshToken"]},
    )

    assert reused.status_code == 401
    assert reused.json()["message"] == "Invalid or expired refresh token"
    assert current.status_code == 200


async def test_expired_refresh_token_is_rejected(
    client: AsyncClient, session: AsyncSession, user: User
) -> None:
    login = await client.post(
        "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
    )
    stored = await session.scalar(select(RefreshTokenSession))
    assert stored is not None
    stored.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
    await session.commit()

    response = await client.post(
        "/api/auth/refresh", json={"refreshToken": login.json()["refreshToken"]}
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid or expired refresh token"


async def test_logout_revokes_current_refresh_session(
    client: AsyncClient, session: AsyncSession, user: User
) -> None:
    login = await client.post(
        "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
    )
    token = login.json()["refreshToken"]

    logout = await client.post("/api/auth/logout", json={"refreshToken": token})
    refresh = await client.post("/api/auth/refresh", json={"refreshToken": token})
    stored = await session.scalar(select(RefreshTokenSession))

    assert logout.status_code == 204
    assert logout.content == b""
    assert refresh.status_code == 401
    assert stored is not None
    assert stored.revoked_at is not None


async def test_logout_is_idempotent_and_only_revokes_supplied_session(
    client: AsyncClient, user: User
) -> None:
    first = await client.post(
        "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
    )
    second = await client.post(
        "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
    )
    first_token = first.json()["refreshToken"]
    second_token = second.json()["refreshToken"]

    assert (
        await client.post("/api/auth/logout", json={"refreshToken": first_token})
    ).status_code == 204
    assert (
        await client.post("/api/auth/logout", json={"refreshToken": first_token})
    ).status_code == 204
    assert (
        await client.post("/api/auth/refresh", json={"refreshToken": second_token})
    ).status_code == 200


async def test_login_rejects_wrong_password(client: AsyncClient, user: User) -> None:
    response = await client.post("/api/auth/login", json={"email": user.email, "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password"


async def test_login_hides_whether_email_exists(client: AsyncClient, user: User) -> None:
    known = await client.post("/api/auth/login", json={"email": user.email, "password": "wrong"})
    unknown = await client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
    )

    assert known.status_code == unknown.status_code == 401
    assert known.json() == unknown.json()


async def test_password_is_hashed_not_stored(client: AsyncClient, session: AsyncSession) -> None:
    await client.post("/api/auth/register", json=REGISTRATION)

    stored = await session.scalar(
        User.__table__.select().where(User.email == "new@example.com")  # type: ignore[arg-type]
    )
    assert stored is not None
    assert REGISTRATION["password"] not in str(stored)


async def test_protected_route_rejects_missing_token(client: AsyncClient) -> None:
    response = await client.get("/api/users/profile")

    assert response.status_code == 401
    assert response.json() == {"statusCode": 401, "message": "Unauthorized"}


async def test_protected_route_rejects_garbage_token(client: AsyncClient) -> None:
    response = await client.get("/api/users/profile", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401


async def test_protected_route_rejects_token_for_unconfirmed_user(
    client: AsyncClient,
    session: AsyncSession,
    email_sender: RecordingEmailSender,
) -> None:
    await client.post("/api/auth/register", json=REGISTRATION)
    user = await session.scalar(select(User).where(User.email == REGISTRATION["email"]))
    assert user is not None
    token = create_access_token(TokenClaims(sub=user.id, email=user.email))

    response = await client.get(
        "/api/users/profile", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


async def test_profile_returns_authenticated_user(
    client: AsyncClient, user: User, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/users/profile", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["email"] == user.email
