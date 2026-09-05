"""User request and response models."""

from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.core.schemas import APIModel

MIN_PASSWORD_LENGTH = 8
DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = frozenset({"en", "lt"})


class RegisterRequest(APIModel):
    """Payload for creating an account."""

    email: EmailStr = Field(examples=["user@example.com"])
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    locale: str = Field(default=DEFAULT_LOCALE, examples=["en", "lt"])

    @field_validator("locale", mode="before")
    @classmethod
    def normalize_locale(cls, value: object) -> str:
        """Use English when the client omits or sends an unsupported locale."""
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in SUPPORTED_LOCALES:
                return normalized
        return DEFAULT_LOCALE


class LoginRequest(APIModel):
    """Credentials for exchanging a password for a token."""

    email: EmailStr = Field(examples=["user@example.com"])
    password: str


class ConfirmEmailRequest(APIModel):
    """Opaque token received through the confirmation email."""

    token: str = Field(min_length=1)


class ResendConfirmationRequest(APIModel):
    """Address that should receive a replacement confirmation email."""

    email: EmailStr = Field(examples=["user@example.com"])


class RefreshTokenRequest(APIModel):
    """An opaque refresh token used to rotate a login session."""

    refresh_token: str = Field(min_length=32, repr=False)


class ForgotPasswordRequest(APIModel):
    """Address that should receive password-reset instructions."""

    email: EmailStr = Field(examples=["user@example.com"])


class ResetPasswordRequest(APIModel):
    """A reset token and the replacement password."""

    token: str = Field(min_length=1, repr=False)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, repr=False)


class ChangePasswordRequest(APIModel):
    """The current and replacement passwords for an authenticated user."""

    current_password: str = Field(min_length=1, repr=False)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, repr=False)


class MessageResponse(APIModel):
    """A successful operation represented by a user-facing message."""

    message: str


class UserResponse(APIModel):
    """A user as returned by the API. Never carries the password hash."""

    id: int
    email: EmailStr
    first_name: str
    last_name: str
    favorite_event_ids: list[int]
    created_at: datetime


class AuthResponse(APIModel):
    """Fresh access and refresh credentials and the user they belong to."""

    access_token: str
    refresh_token: str
    user: UserResponse
