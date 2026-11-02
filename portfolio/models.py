"""Input contracts shared by loaders and deterministic tools."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from portfolio.isin import is_valid_isin


class Asset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    asset_type: Literal["stock", "etf"]
    sector: str | None
    country: str | None


class Holding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    isin: str
    value: Decimal = Field(gt=0, le=Decimal("10000000"), allow_inf_nan=False)

    @field_validator("isin")
    @classmethod
    def validate_isin(cls, value: str) -> str:
        if not is_valid_isin(value):
            raise ValueError("ISIN must have uppercase format and a valid checksum")
        return value

    @field_validator("value", mode="before")
    @classmethod
    def require_number(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError("Position value must be a number, not text or a boolean")
        return value


class Portfolio(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    currency: Literal["EUR"]
    holdings: tuple[Holding, ...] = Field(min_length=1, max_length=100)

    @field_validator("holdings")
    @classmethod
    def reject_duplicates(cls, holdings: tuple[Holding, ...]) -> tuple[Holding, ...]:
        identifiers = [holding.isin for holding in holdings]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Duplicate ISINs are not allowed")
        return holdings
