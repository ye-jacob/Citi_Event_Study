"""The DataSource abstraction (CLAUDE.md "Data-source abstraction").

No analytics or UI code calls a vendor directly — Bloomberg, FRED/ALFRED, and
the naive proxy all populate the same normalized shapes defined here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd


@dataclass(frozen=True, slots=True)
class Release:
    """One data release, normalized across vendors.

    ``release_datetime`` is ET-naive. ``source`` encodes provenance as
    "<actual source>+<consensus source>" (e.g. "fred_first+naive_prev").
    """

    indicator: str  # registry key, e.g. "CPI"
    ref_period: date  # the period the data describes
    release_datetime: datetime  # when it hit the tape, ET-naive
    actual: float | None
    consensus: float | None
    consensus_stdev: float | None
    n_estimates: int | None
    previous: float | None
    is_first_print: bool
    source: str


class DataSource(ABC):
    @abstractmethod
    def get_releases(self, indicator: str, start: date, end: date) -> list[Release]:
        """Releases for one indicator with ref_period in [start, end], ascending."""

    @abstractmethod
    def get_curve(self, start: date, end: date) -> pd.DataFrame:
        """Treasury curve: DatetimeIndex ('date') x tenor columns ('2Y', ...), percent."""
