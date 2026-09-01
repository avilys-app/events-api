"""Resend email provider adapter."""

import httpx

from app.mailer.base import EmailDeliveryError, EmailMessage

RESEND_EMAILS_URL = "https://api.resend.com/emails"


class ResendEmailSender:
    """Send provider-neutral messages through Resend's HTTP API."""

    def __init__(
        self,
        *,
        api_key: str,
        from_address: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._from_address = from_address
        self._client = client

    async def send(self, message: EmailMessage) -> None:
        if not self._api_key:
            raise EmailDeliveryError("RESEND_API_KEY is not configured")

        headers = {"Authorization": f"Bearer {self._api_key}"}
        if message.idempotency_key is not None:
            headers["Idempotency-Key"] = message.idempotency_key

        try:
            if self._client is not None:
                await self._post(self._client, message, headers)
            else:
                async with httpx.AsyncClient(timeout=10) as client:
                    await self._post(client, message, headers)
        except httpx.HTTPError as exc:
            raise EmailDeliveryError("Resend rejected the email") from exc

    async def _post(
        self,
        client: httpx.AsyncClient,
        message: EmailMessage,
        headers: dict[str, str],
    ) -> None:
        response = await client.post(
            RESEND_EMAILS_URL,
            headers=headers,
            json={
                "from": self._from_address,
                "to": [message.to],
                "subject": message.subject,
                "text": message.text,
                "html": message.html,
            },
        )
        response.raise_for_status()
