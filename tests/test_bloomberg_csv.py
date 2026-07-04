"""Bloomberg ECO export parser."""

from datetime import date, datetime

import pytest

from src.sources.bloomberg_csv import BloombergCsvSource

CSV = """indicator,ref_period,release_datetime,actual,consensus,consensus_stdev,n_estimates,previous
CPI,2024-03-01,2024-04-10 08:30,0.4,0.3,0.1,72,0.3
CPI,2024-04-01,2024-05-15 08:30,0.3,0.4,,,0.4
NFP,2024-03-01,2024-04-05 08:30,303,214,45,77,270
"""


@pytest.fixture()
def csv_path(tmp_path):
    p = tmp_path / "eco.csv"
    p.write_text(CSV)
    return p


def test_parses_releases(csv_path):
    src = BloombergCsvSource(csv_path)
    releases = src.get_releases("CPI", date(2024, 1, 1), date(2024, 12, 31))
    assert len(releases) == 2
    first = releases[0]
    assert first.ref_period == date(2024, 3, 1)
    assert first.release_datetime == datetime(2024, 4, 10, 8, 30)
    assert first.consensus == 0.3
    assert first.consensus_stdev == 0.1
    assert first.n_estimates == 72
    assert first.is_first_print is True  # ECO shows the as-released print
    assert first.source == "bloomberg_csv"


def test_optional_fields_may_be_blank(csv_path):
    src = BloombergCsvSource(csv_path)
    second = src.get_releases("CPI", date(2024, 4, 1), date(2024, 4, 30))[0]
    assert second.consensus_stdev is None
    assert second.n_estimates is None


def test_filters_by_indicator_and_window(csv_path):
    src = BloombergCsvSource(csv_path)
    assert len(src.get_releases("NFP", date(2024, 1, 1), date(2024, 12, 31))) == 1
    assert src.get_releases("NFP", date(2024, 5, 1), date(2024, 12, 31)) == []


def test_missing_columns_rejected(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("indicator,actual\nCPI,0.4\n")
    with pytest.raises(ValueError, match="missing required columns"):
        BloombergCsvSource(p)


def test_ticker_map_translation(tmp_path):
    p = tmp_path / "tickers.csv"
    p.write_text(
        "ticker,ref_period,release_datetime,actual,consensus\n"
        "CPI CHNG Index,2024-03-01,2024-04-10 08:30,0.4,0.3\n"
    )
    src = BloombergCsvSource(p, ticker_map={"CPI CHNG Index": "CPI"})
    assert len(src.get_releases("CPI", date(2024, 1, 1), date(2024, 12, 31))) == 1


def test_no_curve_from_bloomberg(csv_path):
    with pytest.raises(NotImplementedError):
        BloombergCsvSource(csv_path).get_curve(date(2024, 1, 1), date(2024, 1, 2))
