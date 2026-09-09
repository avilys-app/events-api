"""End-time-aware event groups, Lithuanian dates, and pagination over real SQL."""

from datetime import UTC, datetime, timedelta

import pytest
from app.core.time import LITHUANIAN_TIME_ZONE
from app.events import repository
from app.users.models import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_event


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 1, 15, 0, 30, tzinfo=LITHUANIAN_TIME_ZONE),
        datetime(2026, 6, 15, 0, 30, tzinfo=LITHUANIAN_TIME_ZONE),
        datetime(2026, 3, 29, 4, 30, tzinfo=LITHUANIAN_TIME_ZONE),
        datetime(2026, 10, 25, 4, 30, tzinfo=LITHUANIAN_TIME_ZONE),
    ],
)
async def test_favorites_partition_by_end_time_and_local_start_day(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    now: datetime,
) -> None:
    monkeypatch.setattr(repository, "local_now", lambda: now)
    clock = now.replace(tzinfo=None)
    today = clock.replace(hour=0, minute=0)
    records = [
        make_event(title="Future", start_time=clock + timedelta(days=2)),
        make_event(title="Today without end", start_time=today),
        make_event(title="Yesterday without end", start_time=today - timedelta(microseconds=1)),
        make_event(
            title="Ongoing across days",
            start_time=clock - timedelta(days=2),
            end_time=clock + timedelta(days=1),
        ),
        make_event(
            title="Ended earlier today", start_time=today, end_time=clock - timedelta(minutes=1)
        ),
        make_event(title="Ends now", start_time=today, end_time=clock),
        make_event(title="Ends next", start_time=today, end_time=clock + timedelta(seconds=1)),
        make_event(title="Undated", start_time=None),
        make_event(title="Only past end", start_time=None, end_time=clock - timedelta(seconds=1)),
        make_event(title="Only future end", start_time=None, end_time=clock + timedelta(days=1)),
    ]
    session.add_all(records)
    await session.flush()
    user.favorite_event_ids = [event.id for event in records]
    # These must not leak into either the favorites data or its total.
    session.add_all(
        [
            make_event(title="Unsaved future", start_time=clock + timedelta(days=1)),
            make_event(title="Unsaved past", start_time=clock - timedelta(days=1)),
        ]
    )
    await session.commit()

    expected_upcoming = {
        "Future",
        "Today without end",
        "Ongoing across days",
        "Ends next",
        "Undated",
        "Only future end",
    }
    expected_past = {"Yesterday without end", "Ended earlier today", "Ends now", "Only past end"}
    for status, expected in [("upcoming", expected_upcoming), ("past", expected_past)]:
        response = await client.get(
            "/api/users/favorites", params={"status": status, "pageSize": 100}, headers=auth_headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["total"] == len(expected)
        assert {row["title"] for row in response.json()["data"]} == expected

    unfiltered = await client.get("/api/users/favorites", headers=auth_headers)
    assert unfiltered.json()["total"] == len(records)

    hidden = await client.get(
        "/api/users/favorites", params={"hideExpired": "true"}, headers=auth_headers
    )
    assert {row["title"] for row in hidden.json()["data"]} == expected_upcoming


@pytest.mark.parametrize("status", ["upcoming", "past"])
async def test_favorites_sort_before_pagination(
    client: AsyncClient,
    session: AsyncSession,
    user: User,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    now = datetime(2026, 6, 1, 12, tzinfo=LITHUANIAN_TIME_ZONE)
    monkeypatch.setattr(repository, "local_now", lambda: now)
    day = timedelta(days=1 if status == "upcoming" else -1)
    records = [
        make_event(title=f"Saved {i}", start_time=now.replace(tzinfo=None) + day * i)
        for i in [3, 1, 2, 2]
    ]
    records.append(
        make_event(title="Unknown start", start_time=None, end_time=now.replace(tzinfo=None) + day)
    )
    session.add_all(records)
    await session.flush()
    user.favorite_event_ids = [event.id for event in records]
    await session.commit()

    # Ties use ascending ID; unknown starts belong at the end of either group.
    expected = [records[i].id for i in [1, 2, 3, 0, 4]]
    actual = []
    for page in range(1, 4):
        response = await client.get(
            "/api/users/favorites",
            params={"status": status, "page": page, "pageSize": 2},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 5
        actual.extend(row["id"] for row in response.json()["data"])
    assert actual == expected

    reverse = await client.get(
        "/api/users/favorites",
        params={"status": status, "orderDirection": "DESC" if status == "upcoming" else "ASC"},
        headers=auth_headers,
    )
    assert [row["id"] for row in reverse.json()["data"]] == [records[i].id for i in [0, 2, 3, 1, 4]]


@pytest.mark.parametrize("date", ["2026-01-15", "2026-06-15", "2026-03-30", "2026-10-26"])
async def test_missing_end_expires_exactly_at_lithuanian_midnight(
    client: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch, date: str
) -> None:
    midnight = datetime.fromisoformat(date).replace(tzinfo=LITHUANIAN_TIME_ZONE)
    session.add(make_event(start_time=midnight.replace(tzinfo=None) - timedelta(hours=1)))
    await session.commit()

    for instant, total in [(midnight - timedelta(microseconds=1), 1), (midnight, 0)]:
        monkeypatch.setattr(repository, "local_now", lambda instant=instant: instant)
        response = await client.get("/api/events", params={"status": "upcoming"})
        assert response.json()["total"] == total
        past = await client.get("/api/events", params={"status": "past"})
        assert past.json()["total"] == 1 - total


@pytest.mark.parametrize(
    "params",
    [{"status": "invalid"}, {"status": "past", "hideExpired": "true"}],
)
async def test_invalid_favorites_status_is_rejected(
    client: AsyncClient, auth_headers: dict[str, str], params: dict[str, str]
) -> None:
    response = await client.get("/api/users/favorites", params=params, headers=auth_headers)
    assert response.status_code == 400


async def test_event_date_bounds_convert_offsets_to_lithuanian_wall_time(
    client: AsyncClient, session: AsyncSession
) -> None:
    session.add_all(
        [
            make_event(title="Before", start_time=datetime(2026, 6, 1, 23, 59)),
            make_event(title="First", start_time=datetime(2026, 6, 2, 0)),
            make_event(title="Last", start_time=datetime(2026, 6, 2, 23, 59, 59, 999999)),
            make_event(title="After", start_time=datetime(2026, 6, 3, 0)),
        ]
    )
    await session.commit()
    for value in ["2026-06-02", "2026-06-01T21:00:00Z", "2026-06-02T00:00:00+03:00"]:
        response = await client.get("/api/events", params={"startDate": value, "endDate": value})
        assert response.status_code == 200, response.text
        assert {row["title"] for row in response.json()["data"]} == {"First", "Last"}


@pytest.mark.parametrize(
    ("start", "end", "offset"),
    [
        (datetime(2026, 1, 1, 20), datetime(2026, 1, 1, 22), "+02:00"),
        (datetime(2026, 6, 1, 20), datetime(2026, 6, 1, 22), "+03:00"),
    ],
)
async def test_event_response_preserves_local_clock_and_seasonal_offset(
    client: AsyncClient, session: AsyncSession, start: datetime, end: datetime, offset: str
) -> None:
    record = make_event(start_time=start, end_time=end)
    session.add(record)
    await session.commit()
    response = await client.get(f"/api/events/{record.id}")
    assert response.json()["startTime"] == start.isoformat() + offset
    assert response.json()["endTime"] == end.isoformat() + offset


async def test_ongoing_event_survives_spring_clock_change(
    client: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 02:30 EET -> 04:30 EEST is one elapsed hour, despite the clock jumping two.
    session.add(
        make_event(start_time=datetime(2026, 3, 29, 2, 30), end_time=datetime(2026, 3, 29, 4, 30))
    )
    await session.commit()
    for utc_now, total in [
        (datetime(2026, 3, 29, 1, 29, 59, tzinfo=UTC), 1),
        (datetime(2026, 3, 29, 1, 30, tzinfo=UTC), 0),
    ]:
        monkeypatch.setattr(
            repository,
            "local_now",
            lambda utc_now=utc_now: utc_now.astimezone(LITHUANIAN_TIME_ZONE),
        )
        response = await client.get("/api/events", params={"status": "upcoming"})
        assert response.json()["total"] == total


async def test_repeated_autumn_hour_uses_same_instant_in_filter_and_response(
    client: AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = make_event(
        start_time=datetime(2026, 10, 25, 2), end_time=datetime(2026, 10, 25, 3, 30)
    )
    session.add(record)
    await session.commit()
    body = (await client.get(f"/api/events/{record.id}")).json()
    assert body["startTime"] == "2026-10-25T02:00:00+03:00"
    assert body["endTime"] == "2026-10-25T03:30:00+02:00"

    # The first 03:30 is not the recorded end; it means the later 03:30 EET.
    for instant, total in [
        (datetime(2026, 10, 25, 0, 30, tzinfo=UTC), 1),
        (datetime(2026, 10, 25, 1, 29, 59, tzinfo=UTC), 1),
        (datetime(2026, 10, 25, 1, 30, tzinfo=UTC), 0),
    ]:
        monkeypatch.setattr(repository, "local_now", lambda instant=instant: instant)
        response = await client.get("/api/events", params={"status": "upcoming"})
        assert response.json()["total"] == total
