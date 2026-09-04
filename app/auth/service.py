"""Registration, email confirmation, and login."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import repository as confirmations
from app.auth import session_repository as refresh_sessions
from app.core.config import get_settings
from app.core.security import (
    TokenClaims,
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    parse_duration,
    verify_password,
)
from app.mailer import repository as email_outbox
from app.mailer.base import EmailMessage
from app.users import repository as users
from app.users.models import User
from app.users.schemas import AuthResponse, MessageResponse, RegisterRequest, UserResponse

INVALID_CREDENTIALS = "Invalid email or password"
UNCONFIRMED_EMAIL = "Email address has not been confirmed"
REGISTRATION_MESSAGE = "Registration successful. Check your email to confirm your account."
RESEND_MESSAGE = "If the account exists and is unconfirmed, a confirmation email has been sent."
INVALID_CONFIRMATION_TOKEN = "Invalid or expired confirmation token"
INVALID_REFRESH_TOKEN = "Invalid or expired refresh token"

@dataclass(frozen=True, slots=True)
class ConfirmationEmailCopy:
    subject: str
    greeting: str
    instruction: str
    action: str
    requested_at: str


_ENGLISH_CONFIRMATION = ConfirmationEmailCopy(
    subject="Confirm your email address",
    greeting="Hi",
    instruction="Confirm your email address to finish creating your account.",
    action="Confirm email address",
    requested_at="Link requested at",
)
_CONFIRMATION_EMAIL_COPY = {
    "en": _ENGLISH_CONFIRMATION,
    "lt": ConfirmationEmailCopy(
        subject="Patvirtinkite el. pašto adresą",
        greeting="Sveiki",
        instruction=(
            "Patvirtinkite savo el. pašto adresą, kad užbaigtumėte paskyros kūrimą."
        ),
        action="Patvirtinti el. pašto adresą",
        requested_at="Nuorodos užklausa pateikta",
    ),
}

_LITHUANIAN_TIME_ZONE = ZoneInfo("Europe/Vilnius")


def _utc_now() -> datetime:
    """Return naive UTC, matching the application's existing database timestamps."""
    return datetime.now(UTC).replace(tzinfo=None)


def _hash_confirmation_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _confirmation_url(base_url: str, token: str) -> str:
    parts = urlsplit(base_url)
    query = [*parse_qsl(parts.query, keep_blank_values=True), ("token", token)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _confirmation_timestamp(requested_at: datetime, locale: str) -> str:
    requested_at_utc = (
        requested_at.replace(tzinfo=UTC)
        if requested_at.tzinfo is None
        else requested_at.astimezone(UTC)
    )
    time_zone = _LITHUANIAN_TIME_ZONE if locale == "lt" else UTC
    return requested_at_utc.astimezone(time_zone).strftime("%Y-%m-%d %H:%M %Z")


def _confirmation_email(
    *,
    user: User,
    raw_token: str,
    token_id: int,
    requested_at: datetime,
) -> EmailMessage:
    url = _confirmation_url(get_settings().email_confirmation_url, raw_token)
    copy = _CONFIRMATION_EMAIL_COPY.get(user.preferred_locale, _ENGLISH_CONFIRMATION)
    safe_name = escape(user.first_name)
    safe_url = escape(url, quote=True)
    requested_at_text = _confirmation_timestamp(requested_at, user.preferred_locale)
    return EmailMessage(
        to=user.email,
        subject=copy.subject,
        text=(
            f"{copy.greeting} {user.first_name},\n\n"
            f"{copy.instruction}\n\n"
            f"{url}\n\n"
            f"{copy.requested_at}: {requested_at_text}"
        ),
        html=(
            f"<p>{copy.greeting} {safe_name},</p>"
            f"<p>{copy.instruction}</p>"
            f'<p><a href="{safe_url}">{copy.action}</a></p>'
            f"<p>{copy.requested_at}: {requested_at_text}</p>"
        ),
        idempotency_key=f"email-confirmation/{token_id}",
    )


async def _enqueue_confirmation_email(
    session: AsyncSession,
    *,
    user: User,
    raw_token: str,
    token_id: int,
    now: datetime,
) -> None:
    await email_outbox.enqueue(
        session,
        confirmation_token_id=token_id,
        message=_confirmation_email(
            user=user,
            raw_token=raw_token,
            token_id=token_id,
            requested_at=now,
        ),
        now=now,
    )


def _duplicate_email() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A user with this email already exists",
    )


def _invalid_confirmation_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=INVALID_CONFIRMATION_TOKEN,
    )


def _auth_response(user: User, refresh_token: str) -> AuthResponse:
    claims = TokenClaims(sub=user.id, email=user.email)
    return AuthResponse(
        access_token=create_access_token(claims),
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


def _invalid_refresh_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=INVALID_REFRESH_TOKEN,
    )


async def _create_refresh_session(session: AsyncSession, user: User) -> str:
    raw_token = create_refresh_token()
    now = _utc_now()
    await refresh_sessions.create(
        session,
        user_id=user.id,
        token_hash=hash_refresh_token(raw_token),
        expires_at=now + parse_duration(get_settings().refresh_token_expires_in),
    )
    return raw_token


async def register(session: AsyncSession, payload: RegisterRequest) -> MessageResponse:
    if await users.get_by_email(session, payload.email) is not None:
        raise _duplicate_email()

    settings = get_settings()
    raw_token = secrets.token_urlsafe(32)
    now = _utc_now()
    try:
        user = await users.create(
            session,
            email=payload.email,
            password_hash=hash_password(payload.password),
            first_name=payload.first_name,
            last_name=payload.last_name,
            preferred_locale=payload.locale,
        )
        confirmation = await confirmations.replace(
            session,
            user_id=user.id,
            token_hash=_hash_confirmation_token(raw_token),
            expires_at=now + parse_duration(settings.email_confirmation_expires_in),
        )
        await _enqueue_confirmation_email(
            session,
            user=user,
            raw_token=raw_token,
            token_id=confirmation.id,
            now=now,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise _duplicate_email() from exc

    return MessageResponse(message=REGISTRATION_MESSAGE)


async def confirm_email(session: AsyncSession, raw_token: str) -> None:
    confirmation = await confirmations.get_for_update(
        session, _hash_confirmation_token(raw_token)
    )
    now = _utc_now()
    if confirmation is None or confirmation.expires_at <= now:
        raise _invalid_confirmation_token()

    user = await users.get(session, confirmation.user_id)
    if user is None:
        raise _invalid_confirmation_token()

    user.email_verified_at = now
    await confirmations.delete_for_user(session, user.id)
    await session.commit()


async def resend_confirmation(session: AsyncSession, email: str) -> MessageResponse:
    user = await users.get_by_email(session, email)
    if user is None or user.email_verified_at is not None:
        return MessageResponse(message=RESEND_MESSAGE)

    settings = get_settings()
    now = _utc_now()
    existing = await confirmations.get_for_user(session, user.id)
    cooldown = parse_duration(settings.email_resend_cooldown)
    if existing is not None and existing.created_at + cooldown > now:
        return MessageResponse(message=RESEND_MESSAGE)

    raw_token = secrets.token_urlsafe(32)
    confirmation = await confirmations.replace(
        session,
        user_id=user.id,
        token_hash=_hash_confirmation_token(raw_token),
        expires_at=now + parse_duration(settings.email_confirmation_expires_in),
    )
    await _enqueue_confirmation_email(
        session,
        user=user,
        raw_token=raw_token,
        token_id=confirmation.id,
        now=now,
    )
    await session.commit()

    return MessageResponse(message=RESEND_MESSAGE)


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    """Verify credentials, failing identically whether the email or password is wrong."""
    user = await users.get_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
        )
    if user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=UNCONFIRMED_EMAIL,
        )
    return user


async def login(session: AsyncSession, email: str, password: str) -> AuthResponse:
    user = await authenticate(session, email, password)
    raw_refresh_token = await _create_refresh_session(session, user)
    await session.commit()
    return _auth_response(user, raw_refresh_token)


async def refresh(session: AsyncSession, raw_token: str) -> AuthResponse:
    """Rotate a valid refresh token and extend its inactivity window."""
    stored = await refresh_sessions.get_for_update(session, hash_refresh_token(raw_token))
    now = _utc_now()
    if stored is None or stored.revoked_at is not None or stored.expires_at <= now:
        raise _invalid_refresh_token()

    user = await users.get(session, stored.user_id)
    if user is None or user.email_verified_at is None:
        raise _invalid_refresh_token()

    replacement = create_refresh_token()
    refresh_sessions.rotate(
        stored,
        token_hash=hash_refresh_token(replacement),
        expires_at=now + parse_duration(get_settings().refresh_token_expires_in),
        now=now,
    )
    await session.commit()
    return _auth_response(user, replacement)


async def logout(session: AsyncSession, raw_token: str) -> None:
    """Revoke one refresh-token session, without revealing whether it existed."""
    stored = await refresh_sessions.get_for_update(session, hash_refresh_token(raw_token))
    if stored is not None and stored.revoked_at is None:
        refresh_sessions.revoke(stored, now=_utc_now())
    await session.commit()
