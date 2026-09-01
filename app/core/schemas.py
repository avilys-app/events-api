"""Shared Pydantic configuration."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class APIModel(BaseModel):
    """Base for every request and response model.

    Field names are snake_case in Python and camelCase in JSON. The wire format
    is part of the public contract, so the alias generator is what defines it --
    renaming a field here renames it for every client.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
