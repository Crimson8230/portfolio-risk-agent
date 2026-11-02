"""Local catalog metadata lookup for validated holdings."""

from portfolio.models import Asset, Portfolio


def get_asset_data(portfolio: Portfolio, catalog: dict[str, Asset]) -> dict:
    return {
        "source": "Offline demonstration catalog",
        "assets": [
            {"isin": holding.isin, **catalog[holding.isin].model_dump()}
            for holding in portfolio.holdings
        ],
        "caveats": ["ETF underlying sector and country exposures are unavailable."],
    }
