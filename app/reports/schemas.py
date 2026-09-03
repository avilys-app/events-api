"""Issue report request models."""

from typing import Annotated

from pydantic import AliasChoices, EmailStr, Field, StringConstraints, field_validator

from app.core.schemas import APIModel

ReportMessage = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SubmitReportRequest(APIModel):
    """A problem report submitted from the web or mobile application."""

    email: EmailStr | None = None
    message: ReportMessage = Field(
        max_length=5000,
        validation_alias=AliasChoices("message", "issue"),
    )
    platform: str | None = Field(default=None, max_length=100)
    app_version: str | None = Field(default=None, max_length=100)

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_is_missing(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value
