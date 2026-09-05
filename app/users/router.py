"""Authenticated user endpoints."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.core.dependencies import CurrentUser, DbSession
from app.events import repository as events
from app.events.schemas import EventFilters, EventResponse, PaginatedEventResponse
from app.users import repository as users
from app.users import service
from app.users.schemas import DeleteAccountRequest, UserResponse

router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid bearer token"}},
)

EventId = Annotated[int, Path(alias="eventId", ge=1, description="Event ID")]


@router.get("/profile", summary="Get the currently authenticated user")
async def get_profile(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.delete(
    "/profile",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete the currently authenticated account",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Current password is incorrect"},
    },
)
async def delete_profile(
    payload: DeleteAccountRequest,
    user: CurrentUser,
    session: DbSession,
) -> None:
    await service.delete_account(session, user, payload.password)


@router.get("/favorites", summary="List the current user's favorite events")
async def list_favorites(
    user: CurrentUser,
    session: DbSession,
    filters: Annotated[EventFilters, Query()],
) -> PaginatedEventResponse:
    total, found = await events.count_and_list(session, filters, user.favorite_event_ids)
    return PaginatedEventResponse(
        data=[EventResponse.model_validate(event) for event in found],
        page=filters.page,
        page_size=filters.page_size,
        total=total,
    )


@router.post(
    "/favorites/{eventId}",
    status_code=status.HTTP_201_CREATED,
    summary="Add an event to the current user's favorites",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Event not found"}},
)
async def add_favorite(user: CurrentUser, session: DbSession, event_id: EventId) -> UserResponse:
    if await events.get(session, event_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} not found",
        )

    updated = await users.add_favorite(session, user, event_id)
    return UserResponse.model_validate(updated)


@router.delete(
    "/favorites/{eventId}",
    summary="Remove an event from the current user's favorites",
)
async def remove_favorite(user: CurrentUser, session: DbSession, event_id: EventId) -> UserResponse:
    updated = await users.remove_favorite(session, user, event_id)
    return UserResponse.model_validate(updated)
