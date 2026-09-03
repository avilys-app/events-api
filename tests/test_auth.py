"""Registration, login, and token handling."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from app.auth.service import _confirmation_timestamp
from app.core.security import TokenClaims, create_access_token
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


async def test_login_succeeds_with_correct_password(client: AsyncClient, user: User) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": user.email, "password": "correct-horse"}
    )

    assert response.status_code == 200
    assert response.json()["user"]["id"] == user.id


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
