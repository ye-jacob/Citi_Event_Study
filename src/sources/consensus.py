"""Consensus providers and the overlay that attaches them to releases.

A ConsensusProvider knows one thing: the pre-release expectation per reference
period for the indicators it covers. ProviderConsensusSource overlays that on
any DataSource's releases, emitting rows ONLY where the provider has a value —
so provider-backed rows coexist in the DB with the naive baseline rows
(distinguished by ``source``) and analysis can compare them.

Free, ToS-clean providers implemented:

- ClevelandFedNowcast (src/sources/cleveland_fed.py): CPI & PCE MoM, 2013-07+
- GdpNowNowcast      (src/sources/gdpnow.py):        advance GDP, ~2011+

Both are MODEL nowcasts, not survey medians — a documented substitute now that
Bloomberg consensus is unavailable. Neither carries forecast dispersion, so
standardized surprises fall back to the historical stdev of raw surprises
(human-owned choice in analytics/surprise.py).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from datetime import date

import pandas as pd

from src.sources.base import DataSource, Release


class ConsensusProvider(ABC):
    """Pre-release expectations for one or more indicators."""

    #: short provenance tag appended to Release.source (e.g. "cleveland_fed")
    source_label: str

    @abstractmethod
    def get_consensus(self, indicator: str) -> pd.DataFrame:
        """Expectations for one indicator.

        Returns a DataFrame indexed by ref_period (Timestamp) with a
        ``consensus`` column; ``consensus_stdev`` / ``n_estimates`` columns are
        optional. Raises ValueError for indicators the provider doesn't cover.
        """


class ProviderConsensusSource(DataSource):
    """Overlay a ConsensusProvider's expectations onto another source's releases."""

    def __init__(self, inner: DataSource, provider: ConsensusProvider) -> None:
        self._inner = inner
        self._provider = provider

    def get_releases(self, indicator: str, start: date, end: date) -> list[Release]:
        table = self._provider.get_consensus(indicator)
        out: list[Release] = []
        for r in self._inner.get_releases(indicator, start, end):
            key = pd.Timestamp(r.ref_period)
            if key not in table.index:
                continue  # provider has no expectation for this period
            row = table.loc[key]
            out.append(
                replace(
                    r,
                    consensus=float(row["consensus"]),
                    consensus_stdev=_opt(row, "consensus_stdev"),
                    n_estimates=(
                        None
                        if _opt(row, "n_estimates") is None
                        else int(row["n_estimates"])
                    ),
                    source=f"{r.source}+{self._provider.source_label}",
                )
            )
        return out

    def get_curve(self, start: date, end: date) -> pd.DataFrame:
        return self._inner.get_curve(start, end)


def _opt(row: pd.Series, col: str) -> float | None:
    if col not in row.index or pd.isna(row[col]):
        return None
    return float(row[col])
