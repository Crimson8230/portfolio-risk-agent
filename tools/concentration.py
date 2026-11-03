"""Position-level concentration, not overall investment risk."""

from decimal import Decimal

from portfolio.models import Portfolio


def analyze_concentration(portfolio: Portfolio) -> dict:
    total = sum((holding.value for holding in portfolio.holdings), Decimal(0))
    largest_value = max(holding.value for holding in portfolio.holdings)
    # Compare unrounded values directly at the heuristic boundaries.
    flag = "HIGH" if largest_value * 100 > total * 40 else (
        "MODERATE" if largest_value * 100 > total * 20 else "LOW"
    )
    largest = [holding.isin for holding in portfolio.holdings if holding.value == largest_value]
    return {
        "largest_position_isin": largest[0],
        "largest_positions_isin": largest,
        "largest_position_pct": float(100 * largest_value / total),
        "hhi": float(sum(((holding.value / total) ** 2 for holding in portfolio.holdings), Decimal(0))),
        "concentration_flag": flag,
        "caveats": [
            "The flag is a simple heuristic, not a validated portfolio risk rating.",
            "HHI measures instrument weights, not underlying ETF diversification or overlap.",
        ],
    }
