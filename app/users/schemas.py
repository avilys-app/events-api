"""User request and response models."""

from datetime import datetime
from typing import Literal

from pydantic import EmailStr, Field, field_validator, model_validator

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
    accepted_terms: Literal[True] = Field(description="Must be true to create an account")
    marketing_email_consent: bool = Field(default=False)
    marketing_push_consent: bool = Field(default=False)

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


class DeleteAccountRequest(APIModel):
    """Password confirmation for permanent account deletion."""

    password: str = Field(min_length=1, repr=False)


class MarketingConsentsUpdateRequest(APIModel):
    """One or both channel-specific marketing preferences."""

    marketing_email_consent: bool | None = None
    marketing_push_consent: bool | None = None

    @model_validator(mode="after")
    def require_preference(self) -> MarketingConsentsUpdateRequest:
        if (
            self.marketing_email_consent is None
            and self.marketing_push_consent is None
        ):
            raise ValueError("at least one marketing consent must be provided")
        return self


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
    terms_accepted_at: datetime
    terms_version: str
    marketing_email_consent: bool
    marketing_email_consent_updated_at: datetime | None
    marketing_push_consent: bool
    marketing_push_consent_updated_at: datetime | None
    created_at: datetime


class MarketingConsentsResponse(APIModel):
    """The current channel-specific marketing preferences."""

    marketing_email_consent: bool
    marketing_email_consent_updated_at: datetime | None
    marketing_push_consent: bool
    marketing_push_consent_updated_at: datetime | None


class AuthResponse(APIModel):
    """Fresh access and refresh credentials and the user they belong to."""

    access_token: str
    refresh_token: str
    user: UserResponse
