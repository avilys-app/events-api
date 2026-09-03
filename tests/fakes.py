"""Test doubles shared by API tests."""

from dataclasses import dataclass, field

from app.mailer.base import EmailDeliveryError, EmailMessage


@dataclass
class RecordingEmailSender:
    messages: list[EmailMessage] = field(default_factory=list)
    should_fail: bool = False
    failure_retryable: bool = True
    failure_code: str = "simulated_failure"

    async def send(self, message: EmailMessage) -> None:
        if self.should_fail:
            raise EmailDeliveryError(
                "simulated delivery failure",
                retryable=self.failure_retryable,
                error_code=self.failure_code,
            )
        self.messages.append(message)
