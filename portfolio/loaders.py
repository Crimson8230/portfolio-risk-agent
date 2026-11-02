"""Bounded local JSON loading; no network access or automatic persistence."""

import json
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from portfolio.models import Asset, Portfolio

MAX_FILE_BYTES = 1_048_576
DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "assets.json"


class PortfolioInputError(ValueError):
    """Safe, user-facing portfolio input rejection."""


def _reject_constant(value: str) -> None:
    raise ValueError("Non-finite JSON numbers are not allowed")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field names are not allowed")
        result[key] = value
    return result


def _read_json(path: Path) -> object:
    if path.suffix.lower() != ".json":
        raise PortfolioInputError("Input file must have a .json extension")
    try:
        with path.open("rb") as source:
            payload = source.read(MAX_FILE_BYTES + 1)
    except OSError:
        raise PortfolioInputError("Could not read the JSON file") from None
    if len(payload) > MAX_FILE_BYTES:
        raise PortfolioInputError("JSON file exceeds the 1 MB limit")
    try:
        return json.loads(
            payload.decode("utf-8"),
            parse_float=Decimal,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise PortfolioInputError("Expected valid UTF-8 JSON without duplicate fields or non-finite numbers") from None


def load_catalog() -> dict[str, Asset]:
    """Read the application's offline catalog, never a model-supplied path."""
    raw = _read_json(DEFAULT_CATALOG_PATH)
    if not isinstance(raw, dict):
        raise PortfolioInputError("The local asset catalog must be a JSON object")
    try:
        return {isin: Asset.model_validate(asset) for isin, asset in raw.items()}
    except ValidationError:
        raise PortfolioInputError("The local asset catalog contains invalid metadata") from None


def load_portfolio(path: str | Path) -> Portfolio:
    """Load a local file and require every holding to exist in the demo catalog."""
    raw = _read_json(Path(path))
    try:
        portfolio = Portfolio.model_validate(raw)
    except ValidationError as error:
        # Omit rejected values, which may contain arbitrary untrusted text.
        details = "; ".join(
            f"{'.'.join(map(str, item['loc'])) or 'portfolio'}: {item['msg']}"
            for item in error.errors(include_input=False, include_url=False)
        )
        raise PortfolioInputError(f"Invalid portfolio: {details}") from None

    catalog = load_catalog()
    unknown = [holding.isin for holding in portfolio.holdings if holding.isin not in catalog]
    if unknown:
        raise PortfolioInputError(
            f"ISIN not in the offline demo catalog: {', '.join(unknown)}. "
            "Use the supported instruments listed in data/assets.json."
        )
    return portfolio
