"""The price and free filters.

The densest logic in the API and the easiest to break: a free event, an event
priced at zero, and an event whose price is mentioned only in its description
all have to filter and sort predictably.
"""

from app.events.models import Event
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_event


def titles(payload: dict[str, object]) -> set[str]:
    data = payload["data"]
    assert isinstance(data, list)
    return {item["title"] for item in data}


FREE_TITLES = {"No price info", "Explicitly zero"}


async def test_free_filter_returns_only_costless_events(
    client: AsyncClient, price_matrix: dict[str, Event]
) -> None:
    response = await client.get("/api/events", params={"free": "true"})

    assert response.status_code == 200
    assert titles(response.json()) == FREE_TITLES


async def test_free_flag_agrees_with_free_filter(
    client: AsyncClient, price_matrix: dict[str, Event]
) -> None:
    """The computed field and the SQL predicate must not disagree.

    ``Event.is_free`` evaluates in Python for the response field and compiles to
    SQL for the filter -- two code paths over one rule. This pins them together:
    an event reported as free must be one that ``?free=true`` returns, and
    every event that filter returns must report itself as free.
    """
    listed = await client.get("/api/events", params={"pageSize": "100"})
    flagged = {item["title"] for item in listed.json()["data"] if item["free"]}

    filtered = await client.get("/api/events", params={"free": "true", "pageSize": "100"})

    assert flagged == titles(filtered.json())


async def test_ticketed_events_are_not_free(
    client: AsyncClient, price_matrix: dict[str, Event]
) -> None:
    response = await client.get("/api/events", params={"free": "true", "pageSize": "100"})
    found = titles(response.json())

    assert "Ticketed, price unknown" not in found
    assert "Priced in prose" not in found
    assert "Has a purchase note" not in found


async def test_price_to_bounds_the_upper_end(
    client: AsyncClient, price_matrix: dict[str, Event]
) -> None:
    response = await client.get("/api/events", params={"priceTo": "50", "pageSize": "100"})
    found = titles(response.json())

    assert "Cheap" in found
    assert "Mid" in found
    assert "Expensive" not in found


async def test_price_to_alone_still_includes_free_events(
    client: AsyncClient, price_matrix: dict[str, Event]
) -> None:
    """A free event costs 0, which is within any upper bound."""
    response = await client.get("/api/events", params={"priceTo": "50", "pageSize": "100"})

    assert titles(response.json()) >= FREE_TITLES


async def test_price_from_bounds_the_lower_end(
    client: AsyncClient, price_matrix: dict[str, Event]
) -> None:
    response = await client.get("/api/events", params={"priceFrom": "20", "pageSize": "100"})
    found = titles(response.json())

    assert "Mid" in found
    assert "Expensive" in found
    assert "Cheap" not in found
    assert not FREE_TITLES & found


async def test_price_range_combines_both_bounds(
    client: AsyncClient, price_matrix: dict[str, Event]
) -> None:
    response = await client.get(
        "/api/events", params={"priceFrom": "20", "priceTo": "50", "pageSize": "100"}
    )

    assert titles(response.json()) == {"Mid"}


async def test_price_from_zero_includes_everything_priced(
    client: AsyncClient, price_matrix: dict[str, Event]
) -> None:
    response = await client.get("/api/events", params={"priceFrom": "0", "pageSize": "100"})

    assert len(response.json()["data"]) == len(price_matrix)


async def test_inverted_price_range_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/events", params={"priceFrom": "50", "priceTo": "10"})

    assert response.status_code == 400


async def test_filters_combine_without_leaking_rows(
    client: AsyncClient, price_matrix: dict[str, Event]
) -> None:
    """Filters must intersect, never union.

    ``price_from`` contributes an OR-ed predicate. If its grouping were ever
    lost, that OR would escape the surrounding AND chain and admit events from
    every other city, so this asserts the empty result the filters imply.
    """
    response = await client.get(
        "/api/events",
        params={"location": "Kaunas", "priceFrom": "0", "pageSize": "100"},
    )

    assert response.json()["data"] == []


async def test_location_flattens_repeated_and_comma_separated_values(
    client: AsyncClient, session: AsyncSession
) -> None:
    session.add_all(
        [
            make_event(title="Vilnius event", city="Vilnius"),
            make_event(title="Kaunas event", city="Kaunas"),
            make_event(title="Klaipeda event", city="Klaipeda"),
        ]
    )
    await session.commit()

    response = await client.get(
        "/api/events",
        params=[("location", "Vilnius, Kaunas"), ("location", "Klaipeda")],
    )

    assert response.status_code == 200
    assert titles(response.json()) == {"Vilnius event", "Kaunas event", "Klaipeda event"}
