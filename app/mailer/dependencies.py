"""Email sender dependency wiring."""

from typing import Annotated

from fastapi import Depends

from app.core.config import get_settings
from app.mailer.base import EmailSender
from app.mailer.resend import ResendEmailSender


def get_email_sender() -> EmailSender:
    settings = get_settings()
    return ResendEmailSender(
        api_key=settings.resend_api_key.get_secret_value(),
        from_address=settings.email_from,
    )


EmailSenderDependency = Annotated[EmailSender, Depends(get_email_sender)]
