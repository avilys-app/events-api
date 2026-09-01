"""Test fixtures.

These exercise real SQL, so they need a Postgres with the `unaccent` and
`pg_trgm` extensions available. Point TEST_DATABASE_URL at a throwaway database
(`docker compose up -d db` provides one); the whole suite skips if it is
unreachable.
"""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from app.core.database import Base, get_db_session
from app.core.security import hash_password
from app.events.models import Event
from app.main import create_app
from app.users.models import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/events_test",
)

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC).replace(tzinfo=None)


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[object]:
    candidate = create_async_engine(TEST_DATABASE_URL)
    try:
        async with candidate.begin() as connection:
            from sqlalchemy import text

            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
    except Exception as exc:  # pragma: no cover - environment dependent
        await candidate.dispose()
        pytest.skip(f"no test database at {TEST_DATABASE_URL}: {exc}")

    async with candidate.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    yield candidate
    await candidate.dispose()


@pytest.fixture
async def session(engine: object) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False)  # type: ignore[arg-type]
    async with factory() as active:
        yield active
        await active.rollback()


@pytest.fixture(autouse=True)
async def clean_tables(session: AsyncSession) -> AsyncIterator[None]:
    from sqlalchemy import text

    await session.execute(text("TRUNCATE events, users RESTART IDENTITY CASCADE"))
    await session.commit()
    yield


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as active:
        yield active

    app.dependency_overrides.clear()


@pytest.fixture
async def user(session: AsyncSession) -> User:
    record = User(
        email="someone@example.com",
        password_hash=hash_password("correct-horse"),
        first_name="Some",
        last_name="One",
        favorite_event_ids=[],
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


@pytest.fixture
async def auth_headers(client: AsyncClient, user: User) -> dict[str, str]:
    response = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "correct-horse"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def make_event(**overrides: object) -> Event:
    """An event with no price information -- free by default."""
    defaults: dict[str, object] = {
        "title": "Some Event",
        "start_time": NOW + timedelta(days=7),
        "city": "Vilnius",
        "popularity_counter": 0,
    }
    return Event(**{**defaults, **overrides})  # type: ignore[arg-type]


@pytest.fixture
async def price_matrix(session: AsyncSession) -> dict[str, Event]:
    """One event per distinct pricing shape, for exercising the price filters."""
    events = {
        "no_info": make_event(title="No price info"),
        "explicit_zero": make_event(title="Explicitly zero", price_from=0, price_to=0),
        "cheap": make_event(title="Cheap", price_from=5, price_to=10),
        "mid": make_event(title="Mid", price_from=25, price_to=40),
        "expensive": make_event(title="Expensive", price_from=80, price_to=120),
        "ticketed_no_price": make_event(
            title="Ticketed, price unknown", ticket_url="https://tickets.example/1"
        ),
        "kaina_in_description": make_event(
            title="Priced in prose", description="Bilietu kaina 15 EUR"
        ),
        "purchase_note": make_event(
            title="Has a purchase note", ticket_purchase_note="Pay at the door"
        ),
    }
    session.add_all(events.values())
    await session.commit()
    for event in events.values():
        await session.refresh(event)
    return events
