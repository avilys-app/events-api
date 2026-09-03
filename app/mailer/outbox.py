"""Durable background delivery for queued email messages."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.mailer import repository
from app.mailer.base import EmailDeliveryError, EmailSender

logger = logging.getLogger(__name__)

RETRY_DELAYS = (
    timedelta(seconds=30),
    timedelta(minutes=1),
    timedelta(minutes=2),
    timedelta(minutes=10),
    timedelta(hours=1),
    timedelta(hours=2),
    timedelta(hours=4),
)
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1
DEFAULT_LEASE_DURATION = timedelta(minutes=2)

Now = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]
SessionFactory = async_sessionmaker[AsyncSession]


def utc_now() -> datetime:
    """Return naive UTC, matching the application's database timestamps."""
    return datetime.now(UTC).replace(tzinfo=None)


async def process_next_email(
    session_factory: SessionFactory,
    sender: EmailSender,
    *,
    now: Now = utc_now,
    lease_duration: timedelta = DEFAULT_LEASE_DURATION,
) -> bool:
    """Process one due email, returning whether a job was claimed."""
    claimed_at = now()
    async with session_factory() as session:
        claimed = await repository.claim_next(
            session,
            now=claimed_at,
            lease_duration=lease_duration,
        )
        await session.commit()

    if claimed is None:
        return False

    try:
        await sender.send(claimed.message)
    except EmailDeliveryError as exc:
        error_code = exc.error_code or type(exc).__name__
        failed_at = now()
        should_retry = exc.retryable and claimed.attempts < MAX_ATTEMPTS
        async with session_factory() as session:
            if should_retry:
                delay = RETRY_DELAYS[claimed.attempts - 1]
                updated = await repository.retry_later(
                    session,
                    claimed,
                    next_attempt_at=failed_at + delay,
                    error_code=error_code,
                )
            else:
                updated = await repository.fail(
                    session,
                    claimed,
                    failed_at=failed_at,
                    error_code=error_code,
                )
            await session.commit()

        if updated and should_retry:
            logger.warning(
                "Email outbox delivery failed: job_id=%s code=%s attempt=%s/%s; retry queued",
                claimed.id,
                error_code,
                claimed.attempts,
                MAX_ATTEMPTS,
            )
        elif updated:
            logger.error(
                "Email outbox delivery permanently failed: "
                "job_id=%s code=%s attempt=%s/%s retryable=%s",
                claimed.id,
                error_code,
                claimed.attempts,
                MAX_ATTEMPTS,
                exc.retryable,
            )
        return True

    async with session_factory() as session:
        deleted = await repository.complete(session, claimed)
        await session.commit()
    if deleted:
        logger.info(
            "Email outbox delivery completed: job_id=%s attempt=%s",
            claimed.id,
            claimed.attempts,
        )
    return True


async def run_email_worker(
    session_factory: SessionFactory,
    sender: EmailSender,
    *,
    poll_interval: float,
    sleep: Sleep = asyncio.sleep,
) -> None:
    """Continuously drain due email jobs until the application shuts down."""
    logger.info("Email outbox worker started")
    while True:
        try:
            processed = await process_next_email(session_factory, sender)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Email outbox worker iteration failed")
            processed = False

        if not processed:
            await sleep(poll_interval)
