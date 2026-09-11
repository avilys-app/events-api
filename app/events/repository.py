"""Data access for events.

Query composition lives here so the router stays thin and the filter logic is
testable without HTTP.
"""

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import ColumnElement, Select, and_, case, func, literal_column, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import UnaryExpression

from app.core.config import get_settings
from app.core.time import LITHUANIAN_TIME_ZONE, local_now
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


def _is_past(now: datetime) -> ColumnElement[bool]:
    """Use the recorded end instant, falling back to the end of the local start day."""
    today = now.astimezone(LITHUANIAN_TIME_ZONE).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    return case(
        (
            Event.end_time.is_not(None),
            func.timezone(LITHUANIAN_TIME_ZONE.key, Event.end_time) <= now.astimezone(UTC),
        ),
        else_=and_(Event.start_time.is_not(None), Event.start_time < today),
    )


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

    # Match events whose active period overlaps the requested window. An absent
    # end time lasts until the next local midnight, as in the expiry rules.
    # Events with an unknown start time are never excluded by a date bound.
    if filters.start_date is not None:
        effective_end = func.coalesce(
            Event.end_time,
            func.date_trunc("day", Event.start_time) + literal_column("INTERVAL '1 day'"),
        )
        clauses.append(
            or_(
                Event.start_time >= filters.start_date,
                effective_end > filters.start_date,
                Event.start_time.is_(None),
            )
        )

    if filters.end_date is not None:
        end_of_day = filters.end_date.replace(hour=23, minute=59, second=59, microsecond=999_999)
        clauses.append(or_(Event.start_time <= end_of_day, Event.start_time.is_(None)))

    if filters.search:
        clauses.append(func.unaccent(Event.title).ilike(func.unaccent(f"%{filters.search}%")))

    if filters.status is not None or filters.hide_expired:
        past = _is_past(local_now())
        clauses.append(past if filters.status == "past" else ~past)

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
    """Order results with duration groups for dates and price groups for prices."""
    if filters.order_by != "price":
        if filters.order_by == "startTime" and filters.sort_direction == "ASC":
            # Unknown durations stay in the regular group; the threshold is
            # strictly greater-than.
            duration_limit = func.make_interval(0, 0, 0, get_settings().long_event_threshold_days)
            statement = statement.order_by(
                Event.start_time.is_(None).asc(),
                case(
                    (Event.end_time > Event.start_time + duration_limit, 1),
                    else_=0,
                ).asc()
            )
        order = _directed(_SORTABLE[filters.order_by], filters.sort_direction)
        if filters.status is not None:
            order = order.nulls_last()
        return statement.order_by(
            order,
            Event.id.asc(),
        )

    has_price_bound = filters.price_from is not None or filters.price_to is not None

    # Free events sink to the bottom whenever a price bound is active, and
    # otherwise follow the sort direction.
    sink_free = has_price_bound or filters.sort_direction == "DESC"
    free_last: OrderDirection = "ASC" if sink_free else "DESC"

    return statement.order_by(
        _directed(case((cast(ColumnElement[bool], Event.is_free), 1), else_=0), free_last),
        # Priced-but-unknown events always trail the ones with a real price.
        case(
            (Event.price_from.is_(None) & ~cast(ColumnElement[bool], Event.is_free), 1),
            else_=0,
        ).asc(),
        _directed(_SORTABLE["price"], filters.sort_direction),
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
