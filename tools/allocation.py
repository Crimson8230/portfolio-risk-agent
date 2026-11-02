"""Deterministic portfolio allocation; no external data or model calls."""

from collections import defaultdict
from decimal import Decimal

from portfolio.models import Asset, Portfolio


def calculate_allocation(portfolio: Portfolio, catalog: dict[str, Asset]) -> dict:
    total = sum((holding.value for holding in portfolio.holdings), Decimal(0))
    by_type = defaultdict(Decimal)
    by_sector = defaultdict(Decimal)
    by_country = defaultdict(Decimal)
    positions = []
    for holding in portfolio.holdings:
        asset = catalog[holding.isin]
        positions.append({
            "isin": holding.isin,
            "value_eur": str(holding.value),
            "weight_pct": float(100 * holding.value / total),
        })
        by_type[asset.asset_type] += holding.value
        sector = asset.sector if asset.asset_type == "stock" else None
        country = asset.country if asset.asset_type == "stock" else None
        by_sector[sector or "Unresolved look-through / unknown"] += holding.value
        by_country[country or "Unresolved look-through / unknown"] += holding.value

    def percentages(groups: dict[str, Decimal]) -> dict[str, float]:
        return {name: float(100 * value / total) for name, value in groups.items()}

    return {
        "currency": "EUR",
        "total_value_eur": str(total),
        "positions": positions,
        "asset_type_pct": percentages(by_type),
        "direct_stock_sector_and_unresolved_pct": percentages(by_sector),
        "direct_stock_country_and_unresolved_pct": percentages(by_country),
        "caveats": [
            "Sector and country groups use total portfolio value as denominator.",
            "ETF look-through is unavailable; direct-stock allocations are not total underlying exposures.",
        ],
    }
