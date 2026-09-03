"""Issue report endpoints."""

from fastapi import APIRouter, status

from app.core.dependencies import DbSession
from app.reports import service
from app.reports.schemas import SubmitReportRequest
from app.users.schemas import MessageResponse

router = APIRouter(prefix="/api", tags=["Reports"])


@router.post(
    "/submit-report",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit an issue report",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Report destination is not configured"
        }
    },
)
async def submit_report(
    payload: SubmitReportRequest,
    session: DbSession,
) -> MessageResponse:
    return await service.submit_report(session, payload)
