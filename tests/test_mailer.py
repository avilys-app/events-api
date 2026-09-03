"""Provider adapter behavior without external network calls."""

import json
from collections.abc import Callable

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


async def no_sleep(_: float) -> None:
    """Skip retry delays in unit tests."""


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


async def test_resend_adapter_wraps_provider_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    attempts = 0

    def handle(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"name": "service_unavailable"})

    transport = httpx.MockTransport(handle)
    async with httpx.AsyncClient(transport=transport) as client:
        sender = ResendEmailSender(
            api_key="secret-key",
            from_address="sender",
            client=client,
            sleep=no_sleep,
            jitter=lambda: 0.0,
        )

        with pytest.raises(EmailDeliveryError) as raised:
            await sender.send(MESSAGE)

    assert attempts == 3
    assert raised.value.retryable is True
    assert raised.value.error_code == "service_unavailable"
    assert raised.value.status_code == 503
    assert (
        "Resend email request failed: status=503 code=service_unavailable "
        "attempt=3/3 retryable=True"
    ) in caplog.messages


@pytest.mark.parametrize(
    ("failures", "make_response"),
    [
        (
            2,
            lambda request: httpx.Response(
                503,
                request=request,
                json={"name": "service_unavailable"},
            ),
        ),
        (
            1,
            lambda request: httpx.Response(
                409,
                request=request,
                json={"name": "concurrent_idempotent_requests"},
            ),
        ),
    ],
)
async def test_resend_adapter_retries_transient_responses(
    failures: int,
    make_response: Callable[[httpx.Request], httpx.Response],
) -> None:
    attempts = 0
    idempotency_keys: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        idempotency_keys.append(request.headers["Idempotency-Key"])
        if attempts <= failures:
            return make_response(request)
        return httpx.Response(200, json={"id": "email-id"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        sender = ResendEmailSender(
            api_key="secret-key",
            from_address="sender",
            client=client,
            sleep=no_sleep,
            jitter=lambda: 0.0,
        )
        await sender.send(MESSAGE)

    assert attempts == failures + 1
    assert idempotency_keys == ["confirmation/1"] * attempts


async def test_resend_adapter_retries_transport_errors() -> None:
    attempts = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("connection failed", request=request)
        return httpx.Response(200, json={"id": "email-id"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        sender = ResendEmailSender(
            api_key="secret-key",
            from_address="sender",
            client=client,
            sleep=no_sleep,
            jitter=lambda: 0.0,
        )
        await sender.send(MESSAGE)

    assert attempts == 2


async def test_resend_adapter_logs_exhausted_transport_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connection timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        sender = ResendEmailSender(
            api_key="secret-key",
            from_address="sender",
            client=client,
            sleep=no_sleep,
            jitter=lambda: 0.0,
        )

        with pytest.raises(EmailDeliveryError) as raised:
            await sender.send(MESSAGE)

    assert (
        "Resend email request failed: transport_error=ConnectTimeout attempt=3/3"
        in caplog.messages
    )
    assert raised.value.retryable is True
    assert raised.value.error_code == "ConnectTimeout"


async def test_resend_adapter_obeys_rate_limit_retry_after() -> None:
    attempts = 0
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                request=request,
                headers={"retry-after": "2"},
                json={"name": "rate_limit_exceeded"},
            )
        return httpx.Response(200, json={"id": "email-id"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        sender = ResendEmailSender(
            api_key="secret-key",
            from_address="sender",
            client=client,
            sleep=record_sleep,
        )
        await sender.send(MESSAGE)

    assert attempts == 2
    assert delays == [2.0]


@pytest.mark.parametrize(
    ("status_code", "error_code"),
    [
        (401, "missing_api_key"),
        (422, "validation_error"),
        (409, "invalid_idempotent_request"),
        (429, "daily_quota_exceeded"),
        (429, "monthly_quota_exceeded"),
    ],
)
async def test_resend_adapter_does_not_retry_permanent_errors(
    status_code: int,
    error_code: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    attempts = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            status_code,
            request=request,
            json={"name": error_code},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        sender = ResendEmailSender(
            api_key="secret-key",
            from_address="sender",
            client=client,
            sleep=no_sleep,
        )

        with pytest.raises(EmailDeliveryError) as raised:
            await sender.send(MESSAGE)

    assert attempts == 1
    assert raised.value.retryable is False
    assert raised.value.error_code == error_code
    assert raised.value.status_code == status_code
    assert (
        f"Resend email request failed: status={status_code} code={error_code} "
        "attempt=1/3 retryable=False"
    ) in caplog.messages
    assert "secret-key" not in caplog.text
    assert MESSAGE.to not in caplog.text
    assert MESSAGE.text not in caplog.text


async def test_resend_adapter_logs_missing_api_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sender = ResendEmailSender(api_key="", from_address="sender")

    with pytest.raises(EmailDeliveryError) as raised:
        await sender.send(MESSAGE)

    assert raised.value.retryable is False
    assert raised.value.error_code == "missing_api_key"
    assert (
        "Resend email request failed: configuration_error=missing_api_key"
        in caplog.messages
    )
    assert MESSAGE.to not in caplog.text


async def test_resend_adapter_generates_stable_idempotency_key_for_retries() -> None:
    attempts = 0
    idempotency_keys: list[str] = []
    message = EmailMessage(
        to="user@example.com",
        subject="Subject",
        text="Text",
        html="<p>HTML</p>",
    )

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        idempotency_keys.append(request.headers["Idempotency-Key"])
        return httpx.Response(503 if attempts == 1 else 200, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        sender = ResendEmailSender(
            api_key="secret-key",
            from_address="sender",
            client=client,
            sleep=no_sleep,
            jitter=lambda: 0.0,
        )
        await sender.send(message)

    assert attempts == 2
    assert len(set(idempotency_keys)) == 1
    assert idempotency_keys[0].startswith("email/")
