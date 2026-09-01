"""Test doubles shared by API tests."""

from dataclasses import dataclass, field

from app.mailer.base import EmailDeliveryError, EmailMessage


@dataclass
class RecordingEmailSender:
    messages: list[EmailMessage] = field(default_factory=list)
    should_fail: bool = False

    async def send(self, message: EmailMessage) -> None:
        if self.should_fail:
            raise EmailDeliveryError("simulated delivery failure")
        self.messages.append(message)
