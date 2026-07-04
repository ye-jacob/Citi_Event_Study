"""Generic offline consensus importer (manual CSV).

The universal fallback when no programmatic public source exists: consensus
figures hand-collected from publicly displayed sources (news wire recaps,
calendar pages, SPF tables) into a CSV, imported offline. This replaces the
former Bloomberg importer — same contract, vendor-neutral.

Expected CSV header (one row per release)::

    indicator,ref_period,release_datetime,actual,consensus,consensus_stdev,n_estimates,previous

- ``indicator``        registry key ("CPI", "NFP", ...)
- ``ref_period``       YYYY-MM-DD (period the data describes)
- ``release_datetime`` YYYY-MM-DD HH:MM, assumed ET
- ``actual``           the as-released (first) print
- ``consensus``        survey median / published expectation;
                       ``consensus_stdev`` / ``n_estimates`` / ``previous`` optional

Keep provenance honest: pass a ``source_label`` naming where the numbers came
from (e.g. "csv_reuters_recaps"); it lands in releases.source. If the data's
license does not allow committing it, keep the file under data/private/
(gitignored).
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


class ConsensusCsvSource(DataSource):
    def __init__(
        self,
        csv_path: str | Path,
        source_label: str = "manual_csv",
        is_first_print: bool = True,
    ) -> None:
        self._path = Path(csv_path)
        self._source_label = source_label
        self._is_first_print = is_first_print
        df = pd.read_csv(self._path)
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
                    is_first_print=self._is_first_print,
                    source=self._source_label,
                )
            )
        return releases

    def get_curve(self, start: date, end: date) -> pd.DataFrame:
        raise NotImplementedError(
            "The Treasury curve comes from FRED (FredDataSource), not a "
            "consensus CSV."
        )


def _opt_float(x) -> float | None:
    return None if pd.isna(x) else float(x)


def _opt_int(x) -> int | None:
    return None if pd.isna(x) else int(x)
