import math
from datetime import datetime, timezone as utc

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RouteRequest(BaseModel):
    """Matches frontend/API_CONTRACT_PROPOSED.md: coordinates are [lng, lat]."""

    model_config = ConfigDict(extra='forbid')
    origin: list[float]
    destination: list[float]
    departure_time: datetime = Field(default_factory=lambda: datetime.now(utc.utc))
    timezone: str = 'Europe/Dublin'

    @field_validator('departure_time')
    @classmethod
    def validate_departure(cls, value):
        if value.utcoffset() is None:
            raise ValueError('departure_time must include an explicit timezone offset')
        return value

    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, value):
        if value != 'Europe/Dublin':
            raise ValueError('timezone must be Europe/Dublin')
        return value

    @field_validator("origin", "destination")
    @classmethod
    def validate_point(cls, value: list[float]) -> list[float]:
        if len(value) != 2 or not all(math.isfinite(v) for v in value):
            raise ValueError("must be [lng, lat] with two finite numbers")
        lng, lat = value
        if not (-180 <= lng <= 180) or not (-90 <= lat <= 90):
            raise ValueError("coordinates out of range")
        return value
