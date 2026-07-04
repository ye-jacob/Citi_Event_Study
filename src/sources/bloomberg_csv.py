"""Offline Bloomberg consensus importer.

The human produces a one-time CSV export from a terminal (``ECO <GO>`` + the
Excel add-in / ``=BDH()``) — the app NEVER calls Bloomberg live. This module
only parses that export into normalized Release rows.

Expected CSV header (one row per release)::

    indicator,ref_period,release_datetime,actual,consensus,consensus_stdev,n_estimates,previous

- ``indicator``       registry key ("CPI", ...) — or a Bloomberg ECO ticker if a
                      ``ticker_map`` {ticker: key} is supplied.
- ``ref_period``      YYYY-MM-DD (period the data describes)
- ``release_datetime``YYYY-MM-DD HH:MM, assumed ET
- ``actual``          the as-released (first) print as shown on ECO
- ``consensus``       survey median; ``consensus_stdev``/``n_estimates`` optional
- ``previous``        prior value as shown at release time

LICENSING: Bloomberg-derived data must not be committed to a public repo. Keep
exports under data/bloomberg/ (gitignored).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from src.sources.base import DataSource, Release

REQUIRED_COLUMNS = [
    "indicator",
    "ref_period",
    "release_datetime",
    "actual",
    "consensus",
]
OPTIONAL_COLUMNS = ["consensus_stdev", "n_estimates", "previous"]


class BloombergCsvSource(DataSource):
    def __init__(
        self, csv_path: str | Path, ticker_map: dict[str, str] | None = None
    ) -> None:
        self._path = Path(csv_path)
        df = pd.read_csv(self._path)
        if ticker_map and "ticker" in df.columns and "indicator" not in df.columns:
            df["indicator"] = df["ticker"].map(ticker_map)
            if df["indicator"].isna().any():
                missing = sorted(df.loc[df["indicator"].isna(), "ticker"].unique())
                raise ValueError(f"ticker_map is missing entries for: {missing}")
        missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing_cols:
            raise ValueError(
                f"{self._path} is missing required columns {missing_cols}; "
                f"expected {REQUIRED_COLUMNS + OPTIONAL_COLUMNS}"
            )
        for col in OPTIONAL_COLUMNS:
            if col not in df.columns:
                df[col] = pd.NA
        df["ref_period"] = pd.to_datetime(df["ref_period"])
        df["release_datetime"] = pd.to_datetime(df["release_datetime"])  # ET assumed
        for col in ["actual", "consensus", "consensus_stdev", "previous"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["n_estimates"] = pd.to_numeric(df["n_estimates"], errors="coerce")
        self._df = df.sort_values(["indicator", "ref_period"])

    def get_releases(self, indicator: str, start: date, end: date) -> list[Release]:
        rows = self._df[
            (self._df["indicator"] == indicator)
            & (self._df["ref_period"] >= pd.Timestamp(start))
            & (self._df["ref_period"] <= pd.Timestamp(end))
        ]
        releases = []
        for row in rows.itertuples(index=False):
            releases.append(
                Release(
                    indicator=indicator,
                    ref_period=row.ref_period.date(),
                    release_datetime=row.release_datetime.to_pydatetime(),
                    actual=_opt_float(row.actual),
                    consensus=_opt_float(row.consensus),
                    consensus_stdev=_opt_float(row.consensus_stdev),
                    n_estimates=_opt_int(row.n_estimates),
                    previous=_opt_float(row.previous),
                    # ECO shows the as-released print, i.e. the first print.
                    is_first_print=True,
                    source="bloomberg_csv",
                )
            )
        return releases

    def get_curve(self, start: date, end: date) -> pd.DataFrame:
        raise NotImplementedError(
            "The Treasury curve comes from FRED (FredDataSource), not Bloomberg."
        )


def _opt_float(x) -> float | None:
    return None if pd.isna(x) else float(x)


def _opt_int(x) -> int | None:
    return None if pd.isna(x) else int(x)
