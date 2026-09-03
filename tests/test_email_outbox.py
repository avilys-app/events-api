"""Durable email outbox processing."""

from datetime import timedelta

from app.mailer import repository
from app.mailer.models import EmailOutboxJob
from app.mailer.outbox import DEFAULT_LEASE_DURATION, RETRY_DELAYS, process_next_email
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.fakes import RecordingEmailSender
from tests.test_auth import REGISTRATION


def test_retry_schedule() -> None:
    assert (
        timedelta(seconds=30),
        timedelta(minutes=1),
        timedelta(minutes=2),
        timedelta(minutes=10),
        timedelta(hours=1),
        timedelta(hours=2),
        timedelta(hours=4),
    ) == RETRY_DELAYS


async def get_job(session: AsyncSession) -> EmailOutboxJob:
    job = await session.scalar(select(EmailOutboxJob))
    assert job is not None
    return job


async def test_worker_delivers_and_removes_queued_email(
    client: AsyncClient,
    session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    email_sender: RecordingEmailSender,
) -> None:
    assert (await client.post("/api/auth/register", json=REGISTRATION)).status_code == 201
    queued_at = (await get_job(session)).next_attempt_at

    assert await process_next_email(
        db_session_factory,
        email_sender,
        now=lambda: queued_at,
    )

    assert len(email_sender.messages) == 1
    session.expire_all()
    assert await session.scalar(select(EmailOutboxJob)) is None


async def test_worker_schedules_transient_failure_then_succeeds(
    client: AsyncClient,
    session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    email_sender: RecordingEmailSender,
) -> None:
    await client.post("/api/auth/register", json=REGISTRATION)
    queued_at = (await get_job(session)).next_attempt_at
    email_sender.should_fail = True

    assert await process_next_email(
        db_session_factory,
        email_sender,
        now=lambda: queued_at,
    )

    session.expire_all()
    failed = await get_job(session)
    assert failed.attempts == 1
    assert failed.last_error_code == "simulated_failure"
    assert failed.next_attempt_at == queued_at + timedelta(seconds=30)
    assert failed.locked_until is None
    assert failed.failed_at is None

    email_sender.should_fail = False
    assert not await process_next_email(
        db_session_factory,
        email_sender,
        now=lambda: failed.next_attempt_at - timedelta(seconds=1),
    )
    assert await process_next_email(
        db_session_factory,
        email_sender,
        now=lambda: failed.next_attempt_at,
    )
    assert len(email_sender.messages) == 1


async def test_worker_stops_and_erases_content_after_permanent_failure(
    client: AsyncClient,
    session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    email_sender: RecordingEmailSender,
) -> None:
    await client.post("/api/auth/register", json=REGISTRATION)
    queued_at = (await get_job(session)).next_attempt_at
    email_sender.should_fail = True
    email_sender.failure_retryable = False
    email_sender.failure_code = "validation_error"

    assert await process_next_email(
        db_session_factory,
        email_sender,
        now=lambda: queued_at,
    )

    session.expire_all()
    failed = await get_job(session)
    assert failed.attempts == 1
    assert failed.last_error_code == "validation_error"
    assert failed.failed_at == queued_at
    assert failed.text_body == ""
    assert failed.html_body == ""
    assert not await process_next_email(
        db_session_factory,
        email_sender,
        now=lambda: queued_at + timedelta(days=1),
    )


async def test_worker_reclaims_job_after_expired_lease(
    client: AsyncClient,
    session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    email_sender: RecordingEmailSender,
) -> None:
    await client.post("/api/auth/register", json=REGISTRATION)
    queued_at = (await get_job(session)).next_attempt_at
    async with db_session_factory() as claiming_session:
        claimed = await repository.claim_next(
            claiming_session,
            now=queued_at,
            lease_duration=DEFAULT_LEASE_DURATION,
        )
        await claiming_session.commit()
    assert claimed is not None

    assert not await process_next_email(
        db_session_factory,
        email_sender,
        now=lambda: queued_at + timedelta(seconds=1),
    )
    assert await process_next_email(
        db_session_factory,
        email_sender,
        now=lambda: queued_at + DEFAULT_LEASE_DURATION,
    )
    assert len(email_sender.messages) == 1
