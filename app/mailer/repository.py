"""Database operations for the durable email outbox."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.mailer.base import EmailMessage
from app.mailer.models import EmailOutboxJob


@dataclass(frozen=True, slots=True)
class ClaimedEmailJob:
    """Provider payload plus the lease that owns its current attempt."""

    id: int
    attempts: int
    lock_token: str
    message: EmailMessage


async def enqueue(
    session: AsyncSession,
    *,
    message: EmailMessage,
    now: datetime,
    confirmation_token_id: int | None = None,
) -> EmailOutboxJob:
    if message.idempotency_key is None:
        raise ValueError("outbox messages require an idempotency key")

    job = EmailOutboxJob(
        confirmation_token_id=confirmation_token_id,
        to_address=message.to,
        reply_to_address=message.reply_to,
        subject=message.subject,
        text_body=message.text,
        html_body=message.html,
        idempotency_key=message.idempotency_key,
        next_attempt_at=now,
    )
    session.add(job)
    await session.flush()
    return job


async def claim_next(
    session: AsyncSession,
    *,
    now: datetime,
    lease_duration: timedelta,
) -> ClaimedEmailJob | None:
    job = await session.scalar(
        select(EmailOutboxJob)
        .where(
            EmailOutboxJob.failed_at.is_(None),
            EmailOutboxJob.next_attempt_at <= now,
            or_(
                EmailOutboxJob.locked_until.is_(None),
                EmailOutboxJob.locked_until <= now,
            ),
        )
        .order_by(EmailOutboxJob.next_attempt_at, EmailOutboxJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None

    lock_token = str(uuid4())
    job.attempts += 1
    job.lock_token = lock_token
    job.locked_until = now + lease_duration
    await session.flush()
    return ClaimedEmailJob(
        id=job.id,
        attempts=job.attempts,
        lock_token=lock_token,
        message=EmailMessage(
            to=job.to_address,
            reply_to=job.reply_to_address,
            subject=job.subject,
            text=job.text_body,
            html=job.html_body,
            idempotency_key=job.idempotency_key,
        ),
    )


async def complete(session: AsyncSession, claimed: ClaimedEmailJob) -> bool:
    result = await session.execute(
        delete(EmailOutboxJob).where(
            EmailOutboxJob.id == claimed.id,
            EmailOutboxJob.lock_token == claimed.lock_token,
        ).returning(EmailOutboxJob.id)
    )
    return result.scalar_one_or_none() is not None


async def retry_later(
    session: AsyncSession,
    claimed: ClaimedEmailJob,
    *,
    next_attempt_at: datetime,
    error_code: str,
) -> bool:
    result = await session.execute(
        update(EmailOutboxJob)
        .where(
            EmailOutboxJob.id == claimed.id,
            EmailOutboxJob.lock_token == claimed.lock_token,
        )
        .values(
            next_attempt_at=next_attempt_at,
            locked_until=None,
            lock_token=None,
            last_error_code=error_code,
        )
        .returning(EmailOutboxJob.id)
    )
    return result.scalar_one_or_none() is not None


async def fail(
    session: AsyncSession,
    claimed: ClaimedEmailJob,
    *,
    failed_at: datetime,
    error_code: str,
) -> bool:
    result = await session.execute(
        update(EmailOutboxJob)
        .where(
            EmailOutboxJob.id == claimed.id,
            EmailOutboxJob.lock_token == claimed.lock_token,
        )
        .values(
            locked_until=None,
            lock_token=None,
            last_error_code=error_code,
            failed_at=failed_at,
            # Message content is no longer needed once retries stop.
            text_body="",
            html_body="",
        )
        .returning(EmailOutboxJob.id)
    )
    return result.scalar_one_or_none() is not None
