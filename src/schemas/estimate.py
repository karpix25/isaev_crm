from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class EstimateFactsPayload(BaseModel):
    address: str = ""
    valid_until: str = ""
    discount_rate: Decimal = Decimal("0.20")
    replanning: dict[str, Any] = Field(default_factory=dict)
    walls: dict[str, Any] = Field(default_factory=dict)
    installation: dict[str, Any] = Field(default_factory=dict)
    electrical: dict[str, Any] = Field(default_factory=dict)
    plumbing: dict[str, Any] = Field(default_factory=dict)
    tile: dict[str, Any] = Field(default_factory=dict)
    finishing: dict[str, Any] = Field(default_factory=dict)
    slopes: dict[str, Any] = Field(default_factory=dict)
    floors: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class EstimateTotalsResponse(BaseModel):
    rough_total: Decimal
    clean_total: Decimal
    rough_discounted_total: Decimal
    clean_discounted_total: Decimal
    discounted_total: Decimal
