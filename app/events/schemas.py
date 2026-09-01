"""Event request and response models."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import Field, field_serializer, field_validator, model_validator

from app.core.schemas import APIModel
from app.events.models import Event

OrderBy = Literal["startTime", "popularityCounter", "price"]
OrderDirection = Literal["ASC", "DESC"]

MAX_PAGE_SIZE = 100


def _price_as_string(value: float | None) -> str | None:
    """Match node-postgres/TypeORM's JSON representation of numeric prices."""
    if value is None:
        return None
    text = format(Decimal(str(value)), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class EventFilters(APIModel):
    """Query parameters for listing events."""

    category: str | None = Field(default=None, description="Filter by exact category")
    location: list[str] | None = Field(
        default=None,
        description="Cities or addresses to match, as repeated or comma-separated values",
        examples=["Vilnius,Kaunas"],
    )

    start_date: datetime | None = Field(default=None, description="Earliest start time")
    end_date: datetime | None = Field(
        default=None, description="Latest start time, inclusive of the whole day"
    )

    price_from: float | None = Field(default=None, ge=0, description="Minimum price")
    price_to: float | None = Field(default=None, ge=0, description="Maximum price")

    free: bool | None = Field(default=None, description="Restrict to free events")
    search: str | None = Field(default=None, description="Accent-insensitive title search")
    hide_expired: bool | None = Field(default=None, description="Exclude events already started")

    page: int = Field(default=1, ge=1, description="1-based page number")
    page_size: int = Field(default=10, ge=1, le=MAX_PAGE_SIZE, description="Items per page")

    order_by: OrderBy = Field(default="startTime", description="Field to sort by")
    order_direction: OrderDirection = Field(default="DESC", description="Sort direction")

    @field_validator("location", mode="before")
    @classmethod
    def split_comma_separated(cls, value: object) -> object:
        """Accept comma-separated, repeated, or combined location parameters.

        FastAPI supplies a list for list-typed query fields even when the URL
        contains only one ``location`` parameter. Split every string in that
        list so ``?location=Vilnius,Kaunas`` and repeated parameters behave the
        same way.
        """
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list):
            return value

        locations: list[object] = []
        for item in values:
            if not isinstance(item, str):
                locations.append(item)
                continue
            locations.extend(part.strip() for part in item.split(",") if part.strip())
        return locations

    @field_validator("free", "hide_expired", mode="before")
    @classmethod
    def accept_loose_booleans(cls, value: object) -> object:
        """Treat anything other than a truthy token as false, never an error.

        These are opt-in flags, so an unrecognised value means "not enabled"
        rather than a rejected request: ``?free=maybe`` is simply off.
        """
        if isinstance(value, str):
            return value.strip().casefold() in {"true", "1", "yes"}
        return value

    @model_validator(mode="after")
    def check_price_range(self) -> Self:
        if (
            self.price_from is not None
            and self.price_to is not None
            and self.price_from > self.price_to
        ):
            raise ValueError("priceFrom must not exceed priceTo")
        return self

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class EventResponse(APIModel):
    """An event as returned by the API."""

    id: int
    title: str
    popularity_counter: int = Field(description="Number of times the event was viewed")

    start_time: datetime | None = None
    end_time: datetime | None = None

    venue_name: str | None = None
    address: str | None = Field(default=None, description="Address, or the venue name if unset")
    city: str | None = None

    lat: float | None = None
    lng: float | None = None

    description: str | None = None
    image_url: str | None = Field(default=None, description="Re-hosted image if available")

    # PostgreSQL ``numeric`` values were strings in the TypeORM API. Keeping
    # that wire format also preserves JavaScript truthiness for an explicit 0.
    price_from: str | None = None
    price_to: str | None = None

    organizer_name: str | None = None
    category: str | None = None

    ticket_url: str | None = None
    source_url: str | None = None
    ticket_purchase_note: str | None = None

    free: bool = Field(description="Whether the event carries no evidence of costing money")

    @field_serializer("start_time", "end_time", when_used="json")
    def serialize_datetime_as_utc(self, value: datetime | None) -> str | None:
        """Match the previous API's JavaScript ``Date`` JSON representation."""
        if value is None:
            return None
        value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return value.isoformat().replace("+00:00", "Z")

    @model_validator(mode="before")
    @classmethod
    def from_event(cls, data: object) -> object:
        """Project an ORM ``Event`` onto the public response shape.

        Three fields are derived rather than copied: ``address`` and
        ``image_url`` have fallbacks, and ``free`` is computed. Everything not
        listed here stays internal.
        """
        if not isinstance(data, Event):
            return data
        return {
            "id": data.id,
            "title": data.title,
            "popularity_counter": data.popularity_counter,
            "start_time": data.start_time,
            "end_time": data.end_time,
            "venue_name": data.venue_name,
            "address": data.display_address,
            "city": data.city,
            "lat": data.lat,
            "lng": data.lng,
            "description": data.description,
            "image_url": data.preferred_image_url,
            "price_from": _price_as_string(data.price_from),
            "price_to": _price_as_string(data.price_to),
            "organizer_name": data.organizer_name,
            "category": data.category,
            "ticket_url": data.ticket_url,
            "source_url": data.source_url,
            "ticket_purchase_note": data.ticket_purchase_note,
            "free": data.is_free,
        }


class PaginatedEventResponse(APIModel):
    """One page of event results."""

    data: list[EventResponse]
    page: int
    page_size: int
    total: int
