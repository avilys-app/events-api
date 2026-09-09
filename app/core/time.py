"""Lithuanian event time and presentation of UTC system timestamps."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

LITHUANIAN_TIME_ZONE = ZoneInfo("Europe/Vilnius")


def local_now() -> datetime:
    return datetime.now(LITHUANIAN_TIME_ZONE)


def event_time(value: datetime) -> datetime:
    """Event columns and offset-free query dates are Lithuanian wall-clock times."""
    if value.tzinfo is None:
        first = value.replace(tzinfo=LITHUANIAN_TIME_ZONE, fold=0)
        second = first.replace(fold=1)
        # Naive storage cannot distinguish the repeated autumn hour. Match
        # PostgreSQL AT TIME ZONE: use the standard-time (later) occurrence.
        first_offset, second_offset = first.utcoffset(), second.utcoffset()
        if first_offset is not None and second_offset is not None and second_offset < first_offset:
            return second
        return first
    return value.astimezone(LITHUANIAN_TIME_ZONE)


def format_system_timestamp(value: datetime) -> str:
    """Display a UTC audit/outbox timestamp in Lithuania, regardless of language."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(LITHUANIAN_TIME_ZONE).strftime("%Y-%m-%d %H:%M %Z")
