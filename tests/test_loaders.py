import json
from decimal import Decimal
from pathlib import Path

import pytest

from portfolio.loaders import MAX_FILE_BYTES, PortfolioInputError, load_portfolio

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample_portfolio.json"


def test_sample_file():
    portfolio = load_portfolio(SAMPLE)
    assert portfolio.currency == "EUR"
    assert [holding.value for holding in portfolio.holdings] == [Decimal(4000), Decimal(3000), Decimal(3000)]


def test_decimal_precision_is_preserved(tmp_path):
    path = tmp_path / "portfolio.json"
    path.write_text('{"currency":"EUR","holdings":[{"isin":"US0378331005","value":0.12345678901234567890123456789}]}')
    assert load_portfolio(path).holdings[0].value == Decimal("0.12345678901234567890123456789")


@pytest.mark.parametrize("payload", [
    b"", b"{", b"\xff", b"[]", b"null",
    b'{"currency":"EUR","currency":"USD"}',
    b'{"currency":"EUR","holdings":[{"isin":"US0378331005","value":NaN}]}',
    b'{"currency":"EUR","holdings":[{"isin":"US0378331005","value":Infinity}]}',
    b'{"currency":"EUR","holdings":[{"isin":"US0378331005","value":"100"}]}',
    b'{"currency":"EUR","holdings":[{"isin":"US0378331005","value":true}]}',
])
def test_invalid_files(tmp_path, payload):
    path = tmp_path / "portfolio.json"
    path.write_bytes(payload)
    with pytest.raises(PortfolioInputError):
        load_portfolio(path)


def test_unknown_but_valid_isin_is_rejected(tmp_path):
    path = tmp_path / "portfolio.json"
    path.write_text(json.dumps({"currency": "EUR", "holdings": [{"isin": "US02079K3059", "value": 100}]}))
    with pytest.raises(PortfolioInputError, match="not in the offline demo catalog"):
        load_portfolio(path)


def test_oversized_file(tmp_path):
    path = tmp_path / "portfolio.json"
    path.write_bytes(b" " * (MAX_FILE_BYTES + 1))
    with pytest.raises(PortfolioInputError, match="1 MB"):
        load_portfolio(path)


def test_exact_size_limit_is_allowed(tmp_path):
    path = tmp_path / "portfolio.json"
    payload = SAMPLE.read_bytes()
    path.write_bytes(payload + b" " * (MAX_FILE_BYTES - len(payload)))
    assert len(load_portfolio(path).holdings) == 3


def test_missing_file(tmp_path):
    with pytest.raises(PortfolioInputError, match="Could not read"):
        load_portfolio(tmp_path / "missing.json")


def test_wrong_extension(tmp_path):
    with pytest.raises(PortfolioInputError, match=".json extension"):
        load_portfolio(tmp_path / "portfolio.csv")


def test_rejected_value_is_not_echoed(tmp_path):
    path = tmp_path / "portfolio.json"
    path.write_text('{"currency":"secret-untrusted-text","holdings":[]}')
    with pytest.raises(PortfolioInputError) as caught:
        load_portfolio(path)
    assert "secret-untrusted-text" not in str(caught.value)
