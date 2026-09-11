"""Date-window overlap and long-term ordering for public and saved events."""

from datetime import datetime, timedelta

import pytest
from app.core.config import Settings
from app.core.time import LITHUANIAN_TIME_ZONE
from app.events import repository
from app.users.models import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_event


@pytest.mark.parametrize("endpoint", ["/api/events", "/api/users/favorites"])
async def test_today_includes_ongoing_events_before_pagination(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    now = datetime(2026, 9, 12, 14, tzinfo=LITHUANIAN_TIME_ZONE)
    monkeypatch.setattr(repository, "local_now", lambda: now)
    records = [
        make_event(
            title="Festival",
            start_time=datetime(2026, 9, 11, 17),
            end_time=datetime(2026, 9, 12, 22),
        ),
        make_event(
            title="Exhibition", start_time=datetime(2026, 9, 7), end_time=datetime(2026, 9, 14)
        ),
        make_event(title="Today without end", start_time=datetime(2026, 9, 12, 10)),
        make_event(title="Unknown", start_time=None),
        make_event(title="Future today", start_time=datetime(2026, 9, 12, 23)),
        make_event(title="Tomorrow", start_time=datetime(2026, 9, 13)),
        make_event(title="Yesterday without end", start_time=datetime(2026, 9, 11, 23)),
        make_event(
            title="Ends at midnight",
            start_time=datetime(2026, 9, 11),
            end_time=datetime(2026, 9, 12),
        ),
        make_event(
            title="Ended today",
            start_time=datetime(2026, 9, 11),
            end_time=datetime(2026, 9, 12, 12),
        ),
    ]
    session.add_all(records)
    await session.flush()
    user.favorite_event_ids = [record.id for record in records]
    if endpoint == "/api/users/favorites":
        session.add(make_event(title="Not saved", start_time=datetime(2026, 9, 12, 18)))
    await session.commit()

    params = {
        "startDate": "2026-09-12",
        "endDate": "2026-09-12",
        "hideExpired": "true",
        "orderBy": "startTime",
        "orderDirection": "ASC",
        "pageSize": "2",
    }
    titles: list[str] = []
    for page in range(1, 4):
        response = await client.get(endpoint, params={**params, "page": page}, headers=auth_headers)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 5
        titles.extend(row["title"] for row in response.json()["data"])
    assert titles == ["Exhibition", "Festival", "Today without end", "Future today", "Unknown"]

    # Historical matches remain available when the caller isn't hiding expired events.
    response = await client.get(
        endpoint, params={**params, "hideExpired": "false", "pageSize": 100}, headers=auth_headers
    )
    assert response.json()["total"] == 6
    assert "Ended today" in {row["title"] for row in response.json()["data"]}


@pytest.mark.parametrize("lower", ["2026-09-12T14:00:00", "2026-09-12T11:00:00Z"])
async def test_overlap_respects_exact_lower_bound_and_null_end_fallback(
    client: AsyncClient, session: AsyncSession, lower: str
) -> None:
    session.add_all(
        [
            make_event(
                title="Ends exactly",
                start_time=datetime(2026, 9, 11),
                end_time=datetime(2026, 9, 12, 14),
            ),
            make_event(
                title="Ends after",
                start_time=datetime(2026, 9, 11),
                end_time=datetime(2026, 9, 12, 14, 0, 1),
            ),
            make_event(title="No end today", start_time=datetime(2026, 9, 12, 8)),
            make_event(title="No end yesterday", start_time=datetime(2026, 9, 11, 23)),
            make_event(title="Starts exactly", start_time=datetime(2026, 9, 12, 14)),
        ]
    )
    await session.commit()
    response = await client.get("/api/events", params={"startDate": lower})
    assert response.status_code == 200, response.text
    assert {row["title"] for row in response.json()["data"]} == {
        "Ends after",
        "No end today",
        "Starts exactly",
    }


@pytest.mark.parametrize("endpoint", ["/api/events", "/api/users/favorites"])
async def test_long_events_follow_regular_events_across_pages(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    monkeypatch.setattr(
        repository, "local_now", lambda: datetime(2026, 9, 12, 14, tzinfo=LITHUANIAN_TIME_ZONE)
    )
    records = [
        make_event(
            title="Old long", start_time=datetime(2025, 5, 1), end_time=datetime(2027, 5, 1)
        ),
        make_event(
            title="New long", start_time=datetime(2026, 5, 1), end_time=datetime(2027, 5, 1)
        ),
        make_event(title="Today A", start_time=datetime(2026, 9, 12, 18)),
        make_event(title="Today B", start_time=datetime(2026, 9, 12, 18)),
        make_event(title="Tomorrow", start_time=datetime(2026, 9, 13)),
        make_event(title="Unknown", start_time=None),
    ]
    session.add_all(records)
    await session.flush()
    user.favorite_event_ids = [record.id for record in records]
    if endpoint == "/api/users/favorites":
        session.add(make_event(title="Not saved", start_time=datetime(2026, 9, 12, 17)))
    await session.commit()

    titles: list[str] = []
    for page in range(1, 4):
        response = await client.get(
            endpoint,
            params={
                "status": "upcoming",
                "startDate": "2026-09-12",
                "endDate": "2026-09-13",
                "pageSize": 2,
                "page": page,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 6
        titles.extend(row["title"] for row in response.json()["data"])
    assert titles == ["Today A", "Today B", "Tomorrow", "Old long", "New long", "Unknown"]


@pytest.mark.parametrize(
    ("days", "start", "threshold_end"),
    [
        (7, datetime(2026, 1, 1, 12), datetime(2026, 1, 8, 12)),
        (3, datetime(2026, 8, 31, 12), datetime(2026, 9, 3, 12)),
        (14, datetime(2024, 2, 29, 12), datetime(2024, 3, 14, 12)),
    ],
)
async def test_long_term_threshold_uses_configured_days(
    client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    days: int,
    start: datetime,
    threshold_end: datetime,
) -> None:
    settings = Settings(_env_file=None, jwt_secret="test-secret", long_event_threshold_days=days)
    monkeypatch.setattr(repository, "get_settings", lambda: settings)
    session.add_all(
        [
            make_event(
                title="Over", start_time=start, end_time=threshold_end + timedelta(microseconds=1)
            ),
            make_event(title="Exactly", start_time=start, end_time=threshold_end),
            make_event(
                title="Shorter",
                start_time=start,
                end_time=threshold_end - timedelta(microseconds=1),
            ),
            make_event(title="No end", start_time=start + timedelta(days=1)),
            make_event(title="Invalid end", start_time=start + timedelta(days=2), end_time=start),
        ]
    )
    await session.commit()
    response = await client.get(
        "/api/events", params={"orderBy": "startTime", "orderDirection": "ASC"}
    )
    assert response.status_code == 200, response.text
    assert [row["title"] for row in response.json()["data"]] == [
        "Exactly",
        "Shorter",
        "No end",
        "Invalid end",
        "Over",
    ]


@pytest.mark.parametrize(
    ("order_by", "direction"),
    [
        ("startTime", "DESC"),
        ("price", "ASC"),
        ("price", "DESC"),
        ("popularityCounter", "ASC"),
        ("popularityCounter", "DESC"),
    ],
)
async def test_other_sorts_do_not_demote_long_events(
    client: AsyncClient, session: AsyncSession, order_by: str, direction: str
) -> None:
    session.add_all(
        [
            make_event(
                title="Long",
                start_time=datetime(2026, 9, 12),
                end_time=datetime(2027, 9, 12),
                price_from=10,
                popularity_counter=1,
            ),
            make_event(
                title="Short",
                start_time=datetime(2026, 9, 11),
                end_time=datetime(2026, 9, 13),
                price_from=20,
                popularity_counter=2,
            ),
        ]
    )
    await session.commit()
    response = await client.get(
        "/api/events", params={"orderBy": order_by, "orderDirection": direction}
    )
    assert response.status_code == 200, response.text
    expected = (
        ["Long", "Short"] if order_by == "startTime" or direction == "ASC" else ["Short", "Long"]
    )
    assert [row["title"] for row in response.json()["data"]] == expected
