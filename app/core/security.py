"""Password hashing and JWT issuing.

Passwords are bcrypt ``$2b$`` hashes at cost 10. Access tokens are HS256 over
``{sub, email, iat, exp, jti}``, where ``sub`` is the user id and ``jti`` makes
tokens issued within the same second distinct.

Both formats are standard and deliberately unadorned, so a stored hash or an
issued token stays readable by any other service that shares the database and
the signing secret.
"""

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import TypedDict

import bcrypt
import jwt

from app.core.config import get_settings

BCRYPT_ROUNDS = 10
JWT_ALGORITHM = "HS256"
REFRESH_TOKEN_BYTES = 48

_DURATION_PATTERN = re.compile(r"^(\d+)([dhms])$")
_DURATION_UNITS = {"d": "days", "h": "hours", "m": "minutes", "s": "seconds"}


class TokenClaims(TypedDict):
    """The claims this service issues and expects."""

    sub: int
    email: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_refresh_token() -> str:
    """Create a high-entropy opaque token suitable for client-side storage."""
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """Return the irreversible value persisted for a refresh token."""
    return hashlib.sha256(token.encode()).hexdigest()


def parse_duration(value: str) -> timedelta:
    """Parse the ``7d`` / ``30m`` format used by ``JWT_EXPIRES_IN``."""
    match = _DURATION_PATTERN.match(value.strip())
    if match is None:
        raise ValueError(f"expected a duration like '7d' or '30m', got {value!r}")
    amount, unit = match.groups()
    return timedelta(**{_DURATION_UNITS[unit]: int(amount)})


def create_access_token(claims: TokenClaims) -> str:
    settings = get_settings()
    issued_at = datetime.now(UTC)
    return jwt.encode(
        {
            **claims,
            "iat": issued_at,
            "exp": issued_at + parse_duration(settings.jwt_expires_in),
            "jti": secrets.token_urlsafe(16),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> TokenClaims:
    """Decode and verify a token, raising ``jwt.PyJWTError`` if invalid.

    ``verify_sub`` is disabled because ``sub`` carries the user id as a JSON
    number; PyJWT would otherwise reject it for not being a string.
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[JWT_ALGORITHM],
        options={"verify_sub": False},
    )
    return TokenClaims(sub=int(payload["sub"]), email=payload["email"])
