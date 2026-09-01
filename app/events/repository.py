"""Data access for events.

Query composition lives here so the router stays thin and the filter logic is
testable without HTTP.
"""

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import ColumnElement, Select, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import UnaryExpression

from app.events.models import Event
from app.events.schemas import EventFilters, OrderDirection

#: Sortable fields, keyed by the value the API accepts. Typed loosely because
#: SQLAlchemy's column generics are invariant across the mix of kinds here.
_SORTABLE: dict[str, Any] = {
    "startTime": Event.start_time,
    "popularityCounter": Event.popularity_counter,
    "price": func.coalesce(Event.price_from, 0),
}


def _directed(column: Any, direction: OrderDirection) -> UnaryExpression[Any]:
    directed: UnaryExpression[Any] = column.asc() if direction == "ASC" else column.desc()
    return directed


def _build_filters(
    filters: EventFilters, restrict_to_ids: list[int] | None
) -> list[ColumnElement[bool]]:
    """Translate the query parameters into SQL predicates."""
    clauses: list[ColumnElement[bool]] = []

    if restrict_to_ids is not None:
        clauses.append(Event.id.in_(restrict_to_ids))

    if filters.category:
        clauses.append(Event.category == filters.category)

    if filters.location:
        clauses.append(
            or_(
                *(
                    or_(Event.city.ilike(f"%{name}%"), Event.address.ilike(f"%{name}%"))
                    for name in filters.location
                )
            )
        )

    # Events with an unknown start time are never excluded by a date bound.
    if filters.start_date is not None:
        clauses.append(or_(Event.start_time >= filters.start_date, Event.start_time.is_(None)))

    if filters.end_date is not None:
        end_of_day = filters.end_date.replace(hour=23, minute=59, second=59, microsecond=999_999)
        clauses.append(or_(Event.start_time <= end_of_day, Event.start_time.is_(None)))

    if filters.search:
        clauses.append(func.unaccent(Event.title).ilike(func.unaccent(f"%{filters.search}%")))

    if filters.hide_expired:
        clauses.append(Event.start_time >= datetime.now(UTC).date())

    # An event with no recorded price coalesces to 0, which already satisfies
    # any non-negative bound -- so free events need no special case here.
    if filters.price_from is not None:
        clauses.append(func.coalesce(Event.price_from, 0) >= filters.price_from)

    if filters.price_to is not None:
        clauses.append(func.coalesce(Event.price_from, 0) <= filters.price_to)

    if filters.free:
        # Hybrid properties surface as an accessor at class level; the cast tells
        # the type checker what SQLAlchemy already builds at runtime.
        clauses.append(cast(ColumnElement[bool], Event.is_free))

    return clauses


def _apply_ordering(statement: Select[tuple[Event]], filters: EventFilters) -> Select[tuple[Event]]:
    """Order results, grouping priceless events into predictable blocks."""
    if filters.order_by != "price":
        return statement.order_by(
            _directed(_SORTABLE[filters.order_by], filters.order_direction),
            Event.id.asc(),
        )

    has_price_bound = filters.price_from is not None or filters.price_to is not None

    # Free events sink to the bottom whenever a price bound is active, and
    # otherwise follow the sort direction.
    sink_free = has_price_bound or filters.order_direction == "DESC"
    free_last: OrderDirection = "ASC" if sink_free else "DESC"

    return statement.order_by(
        _directed(case((cast(ColumnElement[bool], Event.is_free), 1), else_=0), free_last),
        # Priced-but-unknown events always trail the ones with a real price.
        case(
            (Event.price_from.is_(None) & ~cast(ColumnElement[bool], Event.is_free), 1),
            else_=0,
        ).asc(),
        _directed(_SORTABLE["price"], filters.order_direction),
        Event.id.asc(),
    )


async def count_and_list(
    session: AsyncSession,
    filters: EventFilters,
    restrict_to_ids: list[int] | None = None,
) -> tuple[int, list[Event]]:
    """Return the total number of matches and the requested page of them."""
    if restrict_to_ids is not None and not restrict_to_ids:
        return 0, []

    clauses = _build_filters(filters, restrict_to_ids)

    total = await session.scalar(select(func.count(Event.id)).where(*clauses)) or 0

    statement = _apply_ordering(select(Event).where(*clauses), filters)
    rows = await session.scalars(statement.offset(filters.offset).limit(filters.page_size))

    return total, list(rows)


async def get(session: AsyncSession, event_id: int) -> Event | None:
    return await session.get(Event, event_id)


async def increment_popularity(session: AsyncSession, event_id: int) -> None:
    """Bump the view counter in a single statement, avoiding a read-modify-write."""
    await session.execute(
        update(Event)
        .where(Event.id == event_id)
        .values(popularity_counter=Event.popularity_counter + 1)
    )
    await session.commit()
