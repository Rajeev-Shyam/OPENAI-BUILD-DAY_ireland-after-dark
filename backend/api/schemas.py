import math

from pydantic import BaseModel, field_validator


class RouteRequest(BaseModel):
    """Matches frontend/API_CONTRACT_PROPOSED.md: coordinates are [lng, lat]."""

    origin: list[float]
    destination: list[float]
    departure_time: str | None = None
    timezone: str | None = None

    @field_validator("origin", "destination")
    @classmethod
    def validate_point(cls, value: list[float]) -> list[float]:
        if len(value) != 2 or not all(math.isfinite(v) for v in value):
            raise ValueError("must be [lng, lat] with two finite numbers")
        lng, lat = value
        if not (-180 <= lng <= 180) or not (-90 <= lat <= 90):
            raise ValueError("coordinates out of range")
        return value
