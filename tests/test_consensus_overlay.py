"""ProviderConsensusSource: emits only matched periods, tags provenance."""

from datetime import date, datetime

import pandas as pd

from src.sources.base import DataSource, Release
from src.sources.consensus import ConsensusProvider, ProviderConsensusSource


def _release(ref_period):
    return Release(
        indicator="CPI",
        ref_period=ref_period,
        release_datetime=datetime(2024, 4, 10, 8, 30),
        actual=0.38,
        consensus=None,
        consensus_stdev=None,
        n_estimates=None,
        previous=0.44,
        is_first_print=True,
        source="fred_first",
    )


class StubSource(DataSource):
    def get_releases(self, indicator, start, end):
        return [_release(date(2024, 3, 1)), _release(date(2024, 4, 1))]

    def get_curve(self, start, end):
        return pd.DataFrame({"10Y": [4.1]})


class StubProvider(ConsensusProvider):
    source_label = "stub"

    def get_consensus(self, indicator):
        # Covers March only; includes a dispersion column to prove pass-through.
        return pd.DataFrame(
            {"consensus": [0.35], "consensus_stdev": [0.05]},
            index=[pd.Timestamp(2024, 3, 1)],
        )


def test_only_matched_periods_emitted_with_tagged_source():
    out = ProviderConsensusSource(StubSource(), StubProvider()).get_releases(
        "CPI", date(2024, 1, 1), date(2024, 12, 31)
    )
    assert len(out) == 1  # April has no provider value -> dropped, not nulled
    row = out[0]
    assert row.ref_period == date(2024, 3, 1)
    assert row.consensus == 0.35
    assert row.consensus_stdev == 0.05
    assert row.n_estimates is None
    assert row.source == "fred_first+stub"
    assert row.actual == 0.38  # passthrough untouched


def test_curve_delegates():
    df = ProviderConsensusSource(StubSource(), StubProvider()).get_curve(
        date(2024, 1, 1), date(2024, 1, 2)
    )
    assert list(df.columns) == ["10Y"]
