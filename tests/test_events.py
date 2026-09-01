"""Listing, ordering, pagination, and the single-event endpoint."""

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import NOW, make_event


async def test_list_paginates(client: AsyncClient, session: AsyncSession) -> None:
    session.add_all(make_event(title=f"Event {index:02d}") for index in range(25))
    await session.commit()

    first = await client.get("/api/events", params={"page": "1", "pageSize": "10"})
    second = await client.get("/api/events", params={"page": "3", "pageSize": "10"})

    assert first.json()["total"] == 25
    assert len(first.json()["data"]) == 10
    assert len(second.json()["data"]) == 5


async def test_page_size_is_capped(client: AsyncClient) -> None:
    response = await client.get("/api/events", params={"pageSize": "100000"})

    assert response.status_code == 400


async def test_search_ignores_accents(client: AsyncClient, session: AsyncSession) -> None:
    session.add(make_event(title="Kaunas Šventė"))
    await session.commit()

    response = await client.get("/api/events", params={"search": "svente"})

    assert len(response.json()["data"]) == 1


async def test_location_matches_city_or_address(client: AsyncClient, session: AsyncSession) -> None:
    session.add_all(
        [
            make_event(title="In city", city="Klaipeda"),
            make_event(title="In address", city=None, address="Klaipeda, Main St 1"),
            make_event(title="Elsewhere", city="Vilnius"),
        ]
    )
    await session.commit()

    response = await client.get("/api/events", params={"location": "Klaipeda"})

    assert {item["title"] for item in response.json()["data"]} == {"In city", "In address"}


async def test_location_accepts_comma_separated_values(
    client: AsyncClient, session: AsyncSession
) -> None:
    session.add_all(
        [
            make_event(title="A", city="Vilnius"),
            make_event(title="B", city="Kaunas"),
            make_event(title="C", city="Klaipeda"),
        ]
    )
    await session.commit()

    response = await client.get("/api/events", params={"location": "Vilnius,Kaunas"})

    assert {item["title"] for item in response.json()["data"]} == {"A", "B"}


async def test_hide_expired_drops_past_events(client: AsyncClient, session: AsyncSession) -> None:
    session.add_all(
        [
            make_event(title="Past", start_time=NOW - timedelta(days=400)),
            make_event(title="Future", start_time=NOW + timedelta(days=400)),
        ]
    )
    await session.commit()

    response = await client.get("/api/events", params={"hideExpired": "true"})

    assert {item["title"] for item in response.json()["data"]} == {"Future"}


async def test_date_bounds_keep_events_with_unknown_start(
    client: AsyncClient, session: AsyncSession
) -> None:
    session.add_all(
        [
            make_event(title="Undated", start_time=None),
            make_event(title="In range", start_time=NOW + timedelta(days=2)),
            make_event(title="Out of range", start_time=NOW + timedelta(days=90)),
        ]
    )
    await session.commit()

    response = await client.get(
        "/api/events",
        params={
            "startDate": (NOW + timedelta(days=1)).date().isoformat(),
            "endDate": (NOW + timedelta(days=3)).date().isoformat(),
        },
    )

    assert {item["title"] for item in response.json()["data"]} == {"Undated", "In range"}


async def test_malformed_date_is_a_client_error(client: AsyncClient) -> None:
    response = await client.get("/api/events", params={"startDate": "not-a-date"})

    assert response.status_code == 400


async def test_order_by_price_ascending_puts_cheapest_first(
    client: AsyncClient, session: AsyncSession
) -> None:
    session.add_all(
        [
            make_event(title="Mid", price_from=25),
            make_event(title="Cheap", price_from=5),
            make_event(title="Free"),
        ]
    )
    await session.commit()

    response = await client.get("/api/events", params={"orderBy": "price", "orderDirection": "ASC"})
    ordered = [item["title"] for item in response.json()["data"]]

    # Without a price bound, ASC floats free events to the top.
    assert ordered == ["Free", "Cheap", "Mid"]


async def test_order_by_price_with_bound_sinks_free_events(
    client: AsyncClient, session: AsyncSession
) -> None:
    session.add_all(
        [
            make_event(title="Cheap", price_from=5),
            make_event(title="Free"),
        ]
    )
    await session.commit()

    response = await client.get(
        "/api/events",
        params={"orderBy": "price", "orderDirection": "ASC", "priceTo": "50"},
    )
    ordered = [item["title"] for item in response.json()["data"]]

    assert ordered == ["Cheap", "Free"]


async def test_get_event_returns_derived_fields(client: AsyncClient, session: AsyncSession) -> None:
    event = make_event(
        title="Derived",
        address=None,
        venue_name="The Venue",
        image_url="https://origin.example/a.jpg",
        image_url_stored="https://cdn.example/a.jpg",
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)

    response = await client.get(f"/api/events/{event.id}")
    body = response.json()

    assert body["address"] == "The Venue"
    assert body["imageUrl"] == "https://cdn.example/a.jpg"
    assert body["free"] is True
    assert "imageUrlStored" not in body
    assert "dedupKey" not in body


async def test_get_event_serializes_dates_as_utc(
    client: AsyncClient, session: AsyncSession
) -> None:
    event = make_event(
        title="UTC dates",
        start_time=NOW,
        end_time=NOW + timedelta(hours=2),
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)

    body = (await client.get(f"/api/events/{event.id}")).json()

    assert body["startTime"] == "2026-06-01T12:00:00Z"
    assert body["endTime"] == "2026-06-01T14:00:00Z"


async def test_get_missing_event_is_404(client: AsyncClient) -> None:
    response = await client.get("/api/events/424242")

    assert response.status_code == 404
    assert response.json()["error"] == "Not Found"


async def test_get_event_rejects_non_integer_id(client: AsyncClient) -> None:
    response = await client.get("/api/events/abc")

    assert response.status_code == 400


async def test_viewing_an_event_increments_its_counter(
    client: AsyncClient, session: AsyncSession
) -> None:
    event = make_event(title="Counted")
    session.add(event)
    await session.commit()
    await session.refresh(event)

    first = await client.get(f"/api/events/{event.id}")
    second = await client.get(f"/api/events/{event.id}")

    # The response carries the count from before the view that produced it.
    assert first.json()["popularityCounter"] == 0
    assert second.json()["popularityCounter"] == 1


async def test_numeric_response_types_match_the_previous_api(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Counters stay numeric while prices retain TypeORM's string wire format."""
    event = make_event(title="Typed", price_from=12.5)
    session.add(event)
    await session.commit()
    await session.refresh(event)

    body = (await client.get(f"/api/events/{event.id}")).json()

    assert isinstance(body["popularityCounter"], int)
    assert body["priceFrom"] == "12.5"


async def test_explicit_zero_price_is_a_truthy_compatible_string(
    client: AsyncClient, session: AsyncSession
) -> None:
    event = make_event(title="Zero", price_from=0, price_to=10)
    session.add(event)
    await session.commit()
    await session.refresh(event)

    body = (await client.get(f"/api/events/{event.id}")).json()

    assert body["priceFrom"] == "0"
    assert body["priceTo"] == "10"
