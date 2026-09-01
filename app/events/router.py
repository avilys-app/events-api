"""Public event browsing endpoints."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.core.dependencies import DbSession
from app.events import repository
from app.events.schemas import EventFilters, EventResponse, PaginatedEventResponse

router = APIRouter(prefix="/api/events", tags=["Events"])

EventId = Annotated[int, Path(alias="id", ge=1, description="Event ID")]


@router.get("", summary="List events with optional filters")
async def list_events(
    session: DbSession,
    filters: Annotated[EventFilters, Query()],
) -> PaginatedEventResponse:
    total, events = await repository.count_and_list(session, filters)
    return PaginatedEventResponse(
        data=[EventResponse.model_validate(event) for event in events],
        page=filters.page,
        page_size=filters.page_size,
        total=total,
    )


@router.get(
    "/{id}",
    summary="Get a single event by ID",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Event not found"}},
)
async def get_event(session: DbSession, event_id: EventId) -> EventResponse:
    event = await repository.get(session, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} not found",
        )

    response = EventResponse.model_validate(event)

    # Counted after the response is built, so the value a caller receives
    # excludes the view that requested it.
    await repository.increment_popularity(session, event_id)

    return response
