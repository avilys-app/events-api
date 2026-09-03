"""Email messages and sender contract."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmailMessage:
    """An email independent of any delivery provider's request shape."""

    to: str
    subject: str
    text: str
    html: str
    idempotency_key: str | None = None


class EmailDeliveryError(Exception):
    """Raised when an email provider cannot accept a message."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        error_code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.error_code = error_code
        self.status_code = status_code


class EmailSender(Protocol):
    """Delivery boundary implemented by Resend or a future provider."""

    async def send(self, message: EmailMessage) -> None: ...
