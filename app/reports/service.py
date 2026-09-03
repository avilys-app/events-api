"""Queue issue reports for delivery to the configured support inbox."""

from datetime import UTC, datetime
from html import escape
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.mailer import repository as email_outbox
from app.mailer.base import EmailMessage
from app.reports.schemas import SubmitReportRequest
from app.users.schemas import MessageResponse

REPORT_SUBMITTED_MESSAGE = "Report submitted successfully"


def _utc_now() -> datetime:
    """Return naive UTC, matching the application's database timestamps."""
    return datetime.now(UTC).replace(tzinfo=None)


def _display(value: str | None) -> str:
    return value or "Not provided"


def _report_email(
    payload: SubmitReportRequest,
    *,
    to_address: str,
    submitted_at: datetime,
) -> EmailMessage:
    reporter = str(payload.email) if payload.email is not None else None
    submitted_at_text = submitted_at.strftime("%Y-%m-%d %H:%M UTC")
    platform = _display(payload.platform)
    app_version = _display(payload.app_version)

    return EmailMessage(
        to=to_address,
        reply_to=reporter,
        subject="New Avilys issue report",
        text=(
            "New Avilys issue report\n\n"
            f"From: {_display(reporter)}\n"
            f"Platform: {platform}\n"
            f"App version: {app_version}\n"
            f"Submitted at: {submitted_at_text}\n\n"
            f"{payload.message}"
        ),
        html=(
            "<h2>New Avilys issue report</h2>"
            f"<p><strong>From:</strong> {escape(_display(reporter))}</p>"
            f"<p><strong>Platform:</strong> {escape(platform)}</p>"
            f"<p><strong>App version:</strong> {escape(app_version)}</p>"
            f"<p><strong>Submitted at:</strong> {submitted_at_text}</p>"
            "<hr>"
            f'<div style="white-space:pre-wrap">{escape(payload.message)}</div>'
        ),
        idempotency_key=f"issue-report/{uuid4()}",
    )


async def submit_report(
    session: AsyncSession,
    payload: SubmitReportRequest,
) -> MessageResponse:
    settings = get_settings()
    if settings.report_to_email is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Report submission is unavailable",
        )

    now = _utc_now()
    await email_outbox.enqueue(
        session,
        message=_report_email(
            payload,
            to_address=str(settings.report_to_email),
            submitted_at=now,
        ),
        now=now,
    )
    await session.commit()
    return MessageResponse(message=REPORT_SUBMITTED_MESSAGE)
