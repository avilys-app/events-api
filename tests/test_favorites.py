"""Favoriting events."""

from app.users.models import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_event


async def make_stored_event(session: AsyncSession, title: str = "Favorite me") -> int:
    event = make_event(title=title)
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event.id


async def test_add_favorite_records_the_event(
    client: AsyncClient, session: AsyncSession, auth_headers: dict[str, str]
) -> None:
    event_id = await make_stored_event(session)

    response = await client.post(f"/api/users/favorites/{event_id}", headers=auth_headers)

    assert response.status_code == 201
    assert response.json()["favoriteEventIds"] == [event_id]


async def test_add_favorite_is_idempotent(
    client: AsyncClient, session: AsyncSession, auth_headers: dict[str, str]
) -> None:
    event_id = await make_stored_event(session)

    await client.post(f"/api/users/favorites/{event_id}", headers=auth_headers)
    response = await client.post(f"/api/users/favorites/{event_id}", headers=auth_headers)

    assert response.json()["favoriteEventIds"] == [event_id]


async def test_add_favorite_rejects_unknown_event(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.post("/api/users/favorites/999999", headers=auth_headers)

    assert response.status_code == 404


async def test_remove_favorite_drops_the_event(
    client: AsyncClient, session: AsyncSession, auth_headers: dict[str, str]
) -> None:
    event_id = await make_stored_event(session)
    await client.post(f"/api/users/favorites/{event_id}", headers=auth_headers)

    response = await client.delete(f"/api/users/favorites/{event_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["favoriteEventIds"] == []


async def test_remove_favorite_tolerates_absent_event(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.delete("/api/users/favorites/999999", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["favoriteEventIds"] == []


async def test_favorites_listing_is_empty_for_a_new_user(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/users/favorites", headers=auth_headers)

    assert response.json() == {"data": [], "page": 1, "pageSize": 10, "total": 0}


async def test_favorites_listing_returns_only_favorited_events(
    client: AsyncClient, session: AsyncSession, auth_headers: dict[str, str]
) -> None:
    wanted = await make_stored_event(session, "Wanted")
    await make_stored_event(session, "Ignored")
    await client.post(f"/api/users/favorites/{wanted}", headers=auth_headers)

    response = await client.get("/api/users/favorites", headers=auth_headers)

    assert [item["title"] for item in response.json()["data"]] == ["Wanted"]


async def test_favorites_listing_honours_filters(
    client: AsyncClient, session: AsyncSession, auth_headers: dict[str, str]
) -> None:
    first = await make_stored_event(session, "Concert")
    second = await make_stored_event(session, "Workshop")
    for event_id in (first, second):
        await client.post(f"/api/users/favorites/{event_id}", headers=auth_headers)

    response = await client.get(
        "/api/users/favorites", params={"search": "concert"}, headers=auth_headers
    )

    assert [item["title"] for item in response.json()["data"]] == ["Concert"]


async def test_favorites_require_authentication(client: AsyncClient, user: User) -> None:
    assert (await client.get("/api/users/favorites")).status_code == 401
    assert (await client.post("/api/users/favorites/1")).status_code == 401
    assert (await client.delete("/api/users/favorites/1")).status_code == 401
