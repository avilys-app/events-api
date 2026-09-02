"""Resend email provider adapter."""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from uuid import uuid4

import httpx

from app.mailer.base import EmailDeliveryError, EmailMessage

RESEND_EMAILS_URL = "https://api.resend.com/emails"
MAX_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 0.25
MAX_RETRY_DELAY_SECONDS = 5.0

_RETRYABLE_SERVER_STATUSES = frozenset({500, 502, 503, 504})
_RETRYABLE_CONFLICT_CODES = frozenset(
    {"concurrent_idempotent_requests", "resource_locked"}
)

Sleep = Callable[[float], Awaitable[None]]
Jitter = Callable[[], float]

logger = logging.getLogger(__name__)


class ResendEmailSender:
    """Send provider-neutral messages through Resend's HTTP API."""

    def __init__(
        self,
        *,
        api_key: str,
        from_address: str,
        client: httpx.AsyncClient | None = None,
        sleep: Sleep = asyncio.sleep,
        jitter: Jitter = random.random,
    ) -> None:
        self._api_key = api_key
        self._from_address = from_address
        self._client = client
        self._sleep = sleep
        self._jitter = jitter

    async def send(self, message: EmailMessage) -> None:
        if not self._api_key:
            logger.error(
                "Resend email request failed: configuration_error=missing_api_key"
            )
            raise EmailDeliveryError("RESEND_API_KEY is not configured")

        idempotency_key = message.idempotency_key or f"email/{uuid4()}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Idempotency-Key": idempotency_key,
        }

        try:
            if self._client is not None:
                await self._send_with_retry(self._client, message, headers)
            else:
                async with httpx.AsyncClient(timeout=10) as client:
                    await self._send_with_retry(client, message, headers)
        except httpx.HTTPError as exc:
            raise EmailDeliveryError("Resend rejected the email") from exc

    async def _send_with_retry(
        self,
        client: httpx.AsyncClient,
        message: EmailMessage,
        headers: dict[str, str],
    ) -> None:
        payload = {
            "from": self._from_address,
            "to": [message.to],
            "subject": message.subject,
            "text": message.text,
            "html": message.html,
        }

        for attempt in range(MAX_ATTEMPTS):
            response: httpx.Response | None = None
            try:
                response = await client.post(
                    RESEND_EMAILS_URL,
                    headers=headers,
                    json=payload,
                )
            except httpx.TransportError as exc:
                if attempt == MAX_ATTEMPTS - 1:
                    logger.error(
                        "Resend email request failed: transport_error=%s attempt=%s/%s",
                        type(exc).__name__,
                        attempt + 1,
                        MAX_ATTEMPTS,
                    )
                    raise
            else:
                if response.is_success:
                    return
                retryable = self._is_retryable_response(response)
                if not retryable or attempt == MAX_ATTEMPTS - 1:
                    logger.error(
                        "Resend email request failed: status=%s code=%s "
                        "attempt=%s/%s retryable=%s",
                        response.status_code,
                        self._error_code(response) or "unknown",
                        attempt + 1,
                        MAX_ATTEMPTS,
                        retryable,
                    )
                    response.raise_for_status()

            delay = self._retry_delay(attempt, response)
            reason = response.status_code if response is not None else "transport error"
            logger.warning(
                "Retrying Resend email request after %s (attempt %s/%s) in %.2fs",
                reason,
                attempt + 2,
                MAX_ATTEMPTS,
                delay,
            )
            await self._sleep(delay)

    @staticmethod
    def _error_code(response: httpx.Response) -> str | None:
        try:
            payload: object = response.json()
        except ValueError:
            return None
        if not isinstance(payload, dict):
            return None
        for key in ("name", "code"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        return None

    @classmethod
    def _is_retryable_response(cls, response: httpx.Response) -> bool:
        if response.status_code in _RETRYABLE_SERVER_STATUSES:
            return True

        error_code = cls._error_code(response)
        if response.status_code == 409:
            return error_code in _RETRYABLE_CONFLICT_CODES
        if response.status_code == 429:
            # Daily/monthly quota errors also use 429, but cannot be fixed by a short retry.
            return error_code == "rate_limit_exceeded"
        return False

    def _retry_delay(self, attempt: int, response: httpx.Response | None) -> float:
        if response is not None and response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            rate_limit_reset = response.headers.get("ratelimit-reset")
            for value in (retry_after, rate_limit_reset):
                if value is None:
                    continue
                try:
                    return min(MAX_RETRY_DELAY_SECONDS, max(0.0, float(value)))
                except ValueError:
                    continue

        base_delay = BASE_RETRY_DELAY_SECONDS * (2.0**attempt)
        return min(MAX_RETRY_DELAY_SECONDS, base_delay + self._jitter() * base_delay)
