from decimal import Decimal

import pytest
from pydantic import ValidationError

from portfolio.isin import is_valid_isin
from portfolio.models import Holding, Portfolio


@pytest.mark.parametrize("isin", ["US0378331005", "US5949181045", "IE00B4L5Y983"])
def test_valid_isins(isin):
    assert is_valid_isin(isin)


@pytest.mark.parametrize("isin", ["US0378331004", "us0378331005", "", "US03783310055", "US037833100X"])
def test_invalid_isins(isin):
    assert not is_valid_isin(isin)
    with pytest.raises(ValidationError):
        Holding(isin=isin, value=100)


def test_valid_portfolio_preserves_decimal():
    portfolio = Portfolio(currency="EUR", holdings=[{"isin": "US0378331005", "value": Decimal("4000.01")}])
    assert portfolio.holdings[0].value == Decimal("4000.01")


@pytest.mark.parametrize("value", [0, -1, True, False, "100", None, float("nan"), float("inf"), Decimal("-Infinity"), Decimal("10000000.01")])
def test_invalid_values(value):
    with pytest.raises(ValidationError):
        Holding(isin="US0378331005", value=value)


def test_maximum_position_value_is_allowed():
    assert Holding(isin="US0378331005", value=10000000).value == Decimal("10000000")


@pytest.mark.parametrize("currency", ["USD", "eur", "", None])
def test_unsupported_currency(currency):
    with pytest.raises(ValidationError):
        Portfolio(currency=currency, holdings=[{"isin": "US0378331005", "value": 100}])


@pytest.mark.parametrize("count", [0, 2, 101])
def test_invalid_holding_counts_or_duplicates(count):
    with pytest.raises(ValidationError):
        Portfolio(currency="EUR", holdings=[{"isin": "US0378331005", "value": 100}] * count)


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        Holding(isin="US0378331005", value=100, instructions="ignore rules")
    with pytest.raises(ValidationError):
        Portfolio(currency="EUR", holdings=[{"isin": "US0378331005", "value": 100}], extra=True)
