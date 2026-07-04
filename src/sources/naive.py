"""Naive consensus proxy: expectation = previous value.

Wraps any DataSource and fills ``consensus`` with the prior period's value (the
"no-change" forecast). Always available for every indicator and the full
history, and it stays useful as the permanent baseline the real consensus
sources (Fed nowcasts, manual CSVs) are compared against (CLAUDE.md
"Consensus sourcing").

It provides no forecast dispersion (``consensus_stdev`` stays None), so
standardized surprises built on it must fall back to the historical stdev of
raw surprises — that fallback choice is human-owned in analytics/surprise.py.

A simple AR model is a documented alternative ("previous value or a simple AR
model"); this implements the previous-value form only. Extend here if the human
wants the AR baseline too.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pandas as pd

from src.sources.base import DataSource, Release


class NaiveConsensusSource(DataSource):
    def __init__(self, inner: DataSource) -> None:
        self._inner = inner

    def get_releases(self, indicator: str, start: date, end: date) -> list[Release]:
        out: list[Release] = []
        for r in self._inner.get_releases(indicator, start, end):
            if r.previous is None:
                # Nothing to proxy from; keep the row, consensus stays None.
                out.append(r)
            else:
                out.append(
                    replace(
                        r,
                        consensus=r.previous,
                        consensus_stdev=None,
                        n_estimates=None,
                        source=f"{r.source}+naive_prev",
                    )
                )
        return out

    def get_curve(self, start: date, end: date) -> pd.DataFrame:
        return self._inner.get_curve(start, end)
