"""Email sender dependency wiring."""

from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.mailer.base import EmailSender
from app.mailer.resend import ResendEmailSender


def create_email_sender(settings: Settings) -> EmailSender:
    return ResendEmailSender(
        api_key=settings.resend_api_key.get_secret_value(),
        from_address=settings.email_from,
    )


def get_email_sender() -> EmailSender:
    return create_email_sender(get_settings())


EmailSenderDependency = Annotated[EmailSender, Depends(get_email_sender)]
