import json
from decimal import Decimal
from pathlib import Path

import pytest

from portfolio.loaders import load_catalog, load_portfolio
from portfolio.models import Portfolio
from tools.allocation import calculate_allocation
from tools.asset_lookup import get_asset_data
from tools.concentration import analyze_concentration

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_portfolio.json"


def test_sample_allocation_and_metadata():
    portfolio, catalog = load_portfolio(SAMPLE), load_catalog()
    result = calculate_allocation(portfolio, catalog)
    assert Decimal(result["total_value_eur"]) == 10000
    assert [position["weight_pct"] for position in result["positions"]] == [40, 30, 30]
    assert result["asset_type_pct"] == {"stock": 70, "etf": 30}
    assert result["direct_stock_sector_and_unresolved_pct"] == {"Technology": 70, "Unresolved look-through / unknown": 30}
    assert result["direct_stock_country_and_unresolved_pct"] == {"US": 70, "Unresolved look-through / unknown": 30}
    metadata = get_asset_data(portfolio, catalog)
    assert metadata["assets"][0]["name"] == "Apple Inc."
    assert metadata["assets"][2]["sector"] is None
    assert metadata["assets"][2]["country"] is None
    json.dumps(result, allow_nan=False)
    json.dumps(metadata, allow_nan=False)


def test_sample_concentration():
    result = analyze_concentration(load_portfolio(SAMPLE))
    assert result["hhi"] == pytest.approx(0.34)
    assert result["largest_position_pct"] == 40
    assert result["largest_position_isin"] == "US0378331005"
    assert result["concentration_flag"] == "MODERATE"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("values, expected", [
    ([20, 20, 20, 20, 20], "LOW"),
    ([Decimal("20.01"), 20, 20, 20, Decimal("19.99")], "MODERATE"),
    ([40, 30, 30], "MODERATE"),
    ([Decimal("40.01"), 30, Decimal("29.99")], "HIGH"),
    ([100], "HIGH"),
])
def test_thresholds(values, expected):
    # Concentration depends only on validated positions, not catalog metadata.
    identifiers = ["US0378331005", "US5949181045", "IE00B4L5Y983", "US02079K3059", "US0231351067"]
    portfolio = Portfolio(currency="EUR", holdings=[
        {"isin": isin, "value": value} for isin, value in zip(identifiers, values)
    ])
    assert analyze_concentration(portfolio)["concentration_flag"] == expected


def test_ties_preserve_input_order_and_single_position_hhi():
    portfolio = Portfolio(currency="EUR", holdings=[
        {"isin": "US5949181045", "value": 1},
        {"isin": "US0378331005", "value": 1},
    ])
    result = analyze_concentration(portfolio)
    assert result["largest_positions_isin"] == ["US5949181045", "US0378331005"]
    assert result["hhi"] == 0.5
    single = Portfolio(currency="EUR", holdings=[{"isin": "US0378331005", "value": 1}])
    assert analyze_concentration(single)["hhi"] == 1


def test_unrounded_weights_sum_to_100_and_tools_do_not_mutate_input():
    portfolio = Portfolio(currency="EUR", holdings=[
        {"isin": isin, "value": 1} for isin in load_catalog()
    ])
    before = portfolio.model_dump()
    allocation = calculate_allocation(portfolio, load_catalog())
    assert sum(item["weight_pct"] for item in allocation["positions"]) == pytest.approx(100)
    assert allocation["positions"][0]["weight_pct"] == pytest.approx(100 / 3)
    analyze_concentration(portfolio)
    get_asset_data(portfolio, load_catalog())
    assert portfolio.model_dump() == before
