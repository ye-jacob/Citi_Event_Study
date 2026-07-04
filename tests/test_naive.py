"""Naive consensus proxy: consensus = previous, provenance recorded."""

from datetime import date, datetime

import pandas as pd

from src.sources.base import DataSource, Release
from src.sources.naive import NaiveConsensusSource


def _release(ref_period, previous):
    return Release(
        indicator="CPI",
        ref_period=ref_period,
        release_datetime=datetime(2024, 4, 10, 8, 30),
        actual=0.4,
        consensus=None,
        consensus_stdev=None,
        n_estimates=None,
        previous=previous,
        is_first_print=True,
        source="fred_first",
    )


class StubSource(DataSource):
    def __init__(self, releases):
        self._releases = releases

    def get_releases(self, indicator, start, end):
        return self._releases

    def get_curve(self, start, end):
        return pd.DataFrame({"10Y": [4.1]})


def test_consensus_is_previous_value():
    inner = StubSource([_release(date(2024, 3, 1), previous=0.3)])
    out = NaiveConsensusSource(inner).get_releases(
        "CPI", date(2024, 1, 1), date(2024, 12, 31)
    )
    assert out[0].consensus == 0.3
    assert out[0].consensus_stdev is None  # no dispersion from a proxy
    assert out[0].n_estimates is None
    assert out[0].source == "fred_first+naive_prev"
    assert out[0].actual == 0.4  # passthrough untouched


def test_row_without_previous_keeps_none_consensus():
    inner = StubSource([_release(date(2024, 3, 1), previous=None)])
    out = NaiveConsensusSource(inner).get_releases(
        "CPI", date(2024, 1, 1), date(2024, 12, 31)
    )
    assert out[0].consensus is None
    assert out[0].source == "fred_first"  # provenance unchanged


def test_curve_delegates():
    inner = StubSource([])
    df = NaiveConsensusSource(inner).get_curve(date(2024, 1, 1), date(2024, 1, 2))
    assert list(df.columns) == ["10Y"]
