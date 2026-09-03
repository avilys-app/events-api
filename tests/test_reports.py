"""Issue report submission and durable delivery."""

from app.core.config import Settings
from app.mailer.models import EmailOutboxJob
from app.mailer.outbox import process_next_email
from app.reports import service
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.fakes import RecordingEmailSender


def report_settings(*, report_to_email: str | None = "reports@example.com") -> Settings:
    return Settings(
        jwt_secret="test-secret-that-is-long-enough-for-tests",
        report_to_email=report_to_email,
    )


async def test_submit_report_queues_legacy_frontend_payload(
    client: AsyncClient,
    session: AsyncSession,
    monkeypatch,
) -> None:
    monkeypatch.setattr(service, "get_settings", report_settings)

    response = await client.post(
        "/api/submit-report",
        json={
            "email": "reporter@example.com",
            "issue": "The <search> button is broken.",
        },
    )

    assert response.status_code == 202
    assert response.json() == {"message": "Report submitted successfully"}
    job = await session.scalar(select(EmailOutboxJob))
    assert job is not None
    assert job.confirmation_token_id is None
    assert job.to_address == "reports@example.com"
    assert job.reply_to_address == "reporter@example.com"
    assert job.idempotency_key.startswith("issue-report/")
    assert "The &lt;search&gt; button is broken." in job.html_body
    assert "The <search> button is broken." in job.text_body


async def test_submit_report_accepts_new_payload_and_delivers_from_outbox(
    client: AsyncClient,
    session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    email_sender: RecordingEmailSender,
    monkeypatch,
) -> None:
    monkeypatch.setattr(service, "get_settings", report_settings)
    response = await client.post(
        "/api/submit-report",
        json={
            "message": "Map does not load",
            "platform": "web",
            "appVersion": "1.2.3",
        },
    )
    assert response.status_code == 202
    job = await session.scalar(select(EmailOutboxJob))
    assert job is not None

    assert await process_next_email(
        db_session_factory,
        email_sender,
        now=lambda: job.next_attempt_at,
    )

    assert len(email_sender.messages) == 1
    message = email_sender.messages[0]
    assert message.to == "reports@example.com"
    assert message.reply_to is None
    assert "Platform: web" in message.text
    assert "App version: 1.2.3" in message.text


async def test_submit_report_validates_input(
    client: AsyncClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(service, "get_settings", report_settings)

    missing_message = await client.post(
        "/api/submit-report",
        json={"email": "reporter@example.com"},
    )
    invalid_email = await client.post(
        "/api/submit-report",
        json={"email": "invalid", "issue": "Something failed"},
    )
    long_message = await client.post(
        "/api/submit-report",
        json={"message": "x" * 5001},
    )

    assert missing_message.status_code == 400
    assert invalid_email.status_code == 400
    assert long_message.status_code == 400


async def test_submit_report_requires_configured_destination(
    client: AsyncClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: report_settings(report_to_email=None),
    )

    response = await client.post(
        "/api/submit-report",
        json={"message": "Something failed"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "statusCode": 503,
        "message": "Report submission is unavailable",
        "error": "Service Unavailable",
    }


async def test_submit_report_allows_web_cors_preflight(client: AsyncClient) -> None:
    response = await client.options(
        "/api/submit-report",
        headers={
            "Origin": "https://avilys.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "POST" in response.headers["access-control-allow-methods"]
