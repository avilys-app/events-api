"""Provider adapter behavior without external network calls."""

import json

import httpx
import pytest
from app.mailer.base import EmailDeliveryError, EmailMessage
from app.mailer.resend import RESEND_EMAILS_URL, ResendEmailSender

MESSAGE = EmailMessage(
    to="user@example.com",
    subject="Confirm your email",
    text="Confirmation text",
    html="<p>Confirmation HTML</p>",
    idempotency_key="confirmation/1",
)


async def test_resend_adapter_maps_provider_independent_message() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == RESEND_EMAILS_URL
        assert request.headers["Authorization"] == "Bearer secret-key"
        assert request.headers["Idempotency-Key"] == "confirmation/1"
        assert json.loads(request.content) == {
            "from": "Events <accounts@example.com>",
            "to": ["user@example.com"],
            "subject": "Confirm your email",
            "text": "Confirmation text",
            "html": "<p>Confirmation HTML</p>",
        }
        return httpx.Response(200, json={"id": "email-id"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        sender = ResendEmailSender(
            api_key="secret-key",
            from_address="Events <accounts@example.com>",
            client=client,
        )
        await sender.send(MESSAGE)


async def test_resend_adapter_wraps_provider_errors() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(503))
    async with httpx.AsyncClient(transport=transport) as client:
        sender = ResendEmailSender(api_key="secret-key", from_address="sender", client=client)

        with pytest.raises(EmailDeliveryError):
            await sender.send(MESSAGE)
