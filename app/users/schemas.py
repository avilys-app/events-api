"""User request and response models."""

from datetime import datetime

from pydantic import EmailStr, Field

from app.core.schemas import APIModel

MIN_PASSWORD_LENGTH = 8


class RegisterRequest(APIModel):
    """Payload for creating an account."""

    email: EmailStr = Field(examples=["user@example.com"])
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)


class LoginRequest(APIModel):
    """Credentials for exchanging a password for a token."""

    email: EmailStr = Field(examples=["user@example.com"])
    password: str


class UserResponse(APIModel):
    """A user as returned by the API. Never carries the password hash."""

    id: int
    email: EmailStr
    first_name: str
    last_name: str
    favorite_event_ids: list[int]
    created_at: datetime


class AuthResponse(APIModel):
    """A freshly issued token and the user it belongs to."""

    access_token: str
    user: UserResponse
