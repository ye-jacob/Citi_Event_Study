"""FRED/ALFRED data source.

Supports BOTH vintages of "the actual":

- ``vintage="first"``  — the number as it hit the tape, via ALFRED's full
  vintage history (``get_series_all_releases``).
- ``vintage="latest"`` — today's revised values.

WHICH vintage counts as "the actual" for surprise construction is the project's
flagship human-owned decision (CLAUDE.md gotcha #1). This client only makes both
available; it defaults nothing — callers must choose explicitly.

The same-vintage rule (matters — verified against published prints)
--------------------------------------------------------------------
For transformed indicators (NFP = diff of PAYEMS, CPI MoM = pct change) the
published headline is NOT the difference of consecutive first-print levels: it
is (this period's first print) minus (the prior period's level AS REVISED in
the same report). NFP revises prior months every release and re-benchmarks
annually, so diff-of-first-prints can miss the reported headline by >100k
(e.g. Feb 2024: +275k reported vs +108k naive diff). Under vintage="first",
transforms are therefore computed against the prior period's value as of the
release date (ALFRED as-of lookup), which reproduces the as-reported number.

Remaining approximations (documented, human verifies before publishing):

- The release date is ALFRED's ``realtime_start`` of the first vintage — the
  publication date for these series. The release *time* comes from the
  indicator registry (e.g. 08:30 ET); ALFRED has no intraday timestamps.
- SERIES-INCEPTION TRAP: a series' vintages only exist from the day it was
  ADDED to FRED — earlier observations' "first vintage" is that day's revised
  value with a fake release date. Verified cases: A191RL1Q225SBEA (added
  2014-09-26; GDP study rows therefore come from the Atlanta Fed track record
  instead — see gdpnow.py) and PCEPI (vintages start 2000-08, so the first ~6
  months of PCE baseline rows share one date). Check ALFRED vintage coverage
  before trusting early history of any newly added series.
- Published prints are rounded (CPI MoM to 0.1pp); values here carry full
  precision. TODO(human): decide precision policy for surprises.
"""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd

from src import config
from src.sources.base import DataSource, Release

VALID_VINTAGES = {"first", "latest"}


class FredDataSource(DataSource):
    def __init__(
        self,
        api_key: str | None = None,
        vintage: str = "first",
        fred=None,
        registry: list[dict] | None = None,
    ) -> None:
        """``fred`` allows injecting a fake client in tests (no network)."""
        if vintage not in VALID_VINTAGES:
            raise ValueError(f"vintage must be one of {sorted(VALID_VINTAGES)}")
        self.vintage = vintage
        self._registry = {
            row["key"]: row for row in (registry or config.INDICATORS)
        }
        if fred is None:
            from fredapi import Fred  # lazy: tests inject a fake instead

            fred = Fred(api_key=api_key or config.get_fred_api_key())
        self._fred = fred

    # ------------------------------------------------------------------ curve

    def get_curve(
        self, start: date, end: date, tenors: list[str] | None = None
    ) -> pd.DataFrame:
        tenors = tenors or config.CORE_TENORS
        unknown = set(tenors) - set(config.TENOR_FRED_SERIES)
        if unknown:
            raise ValueError(f"Unknown tenors {sorted(unknown)}")
        frame: dict[str, pd.Series] = {}
        for tenor in tenors:
            series_id = config.TENOR_FRED_SERIES[tenor]
            frame[tenor] = self._fred.get_series(
                series_id, observation_start=start, observation_end=end
            )
        df = pd.DataFrame(frame).sort_index()
        df.index.name = "date"
        return df

    # -------------------------------------------------------------- releases

    def get_releases(self, indicator: str, start: date, end: date) -> list[Release]:
        meta = self._registry.get(indicator)
        if meta is None:
            raise ValueError(
                f"Unknown indicator {indicator!r}; known: {sorted(self._registry)}"
            )
        if not meta["fred_series"]:
            raise ValueError(
                f"{indicator} has no FRED series ({meta['notes']})"
            )

        vintages = self._all_releases(meta["fred_series"])
        per_obs = self._per_observation(vintages)
        actuals = self._transformed_actuals(vintages, per_obs, meta["transform"])
        previous = actuals.shift(1)

        releases: list[Release] = []
        for ref_period, actual in actuals.items():
            if pd.isna(actual):
                continue  # first obs under diff/pct_change has no defined change
            if not (pd.Timestamp(start) <= ref_period <= pd.Timestamp(end)):
                continue
            release_date = per_obs.loc[ref_period, "release_date"]
            prev = previous.loc[ref_period]
            releases.append(
                Release(
                    indicator=indicator,
                    ref_period=ref_period.date(),
                    release_datetime=datetime.combine(
                        release_date.date(), meta["release_time"]
                    ),
                    actual=float(actual),
                    consensus=None,  # FRED has none; see naive/consensus providers
                    consensus_stdev=None,
                    n_estimates=None,
                    previous=None if pd.isna(prev) else float(prev),
                    is_first_print=self.vintage == "first",
                    source=f"fred_{self.vintage}",
                )
            )
        releases.sort(key=lambda r: r.ref_period)
        return releases

    # -------------------------------------------------------------- internals

    def _all_releases(self, series_id: str) -> pd.DataFrame:
        """Full ALFRED vintage history: realtime_start / date / value rows."""
        df = self._fred.get_series_all_releases(series_id)
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df["realtime_start"] = pd.to_datetime(df["realtime_start"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])
        return df.sort_values(["date", "realtime_start"])

    def _per_observation(self, vintages: pd.DataFrame) -> pd.DataFrame:
        """Per reference period: first/latest values + the ORIGINAL release date.

        The release date is always the first vintage's realtime_start — even for
        vintage="latest", the *event* happened when the first print hit the tape.

        Pre-inception backfill is dropped: observations published before the
        series was added to FRED all share the series' minimum realtime_start —
        their "first vintage" is a revision with a fake release date, not a
        first print (the series-inception trap in the module docstring). Two or
        more observations at the minimum is that signature; a single one is a
        legitimate first release and is kept. Genuine multi-period release days
        (e.g. shutdown catch-up prints) sit mid-history and are unaffected.
        """
        grouped = vintages.groupby("date")
        out = pd.DataFrame(
            {
                "release_date": grouped["realtime_start"].first(),
                "first_value": grouped["value"].first(),
                "latest_value": grouped["value"].last(),
            }
        )
        backfilled = out["release_date"] == vintages["realtime_start"].min()
        if backfilled.sum() > 1:
            out = out[~backfilled]
        return out.sort_index()

    def _transformed_actuals(
        self, vintages: pd.DataFrame, per_obs: pd.DataFrame, transform: str
    ) -> pd.Series:
        """The as-quoted number per reference period, under the chosen vintage."""
        if transform not in config.VALID_TRANSFORMS:
            raise ValueError(
                f"Unknown transform {transform!r}; expected one of "
                f"{sorted(config.VALID_TRANSFORMS)}"
            )

        if self.vintage == "latest":
            values = per_obs["latest_value"]
            if transform == "none":
                return values
            if transform == "diff":
                return values.diff()
            return values.pct_change() * 100.0

        # vintage == "first"
        if transform == "none":
            return per_obs["first_value"]

        prior = self._prior_value_asof_release(vintages, per_obs)
        if transform == "diff":
            return per_obs["first_value"] - prior
        return (per_obs["first_value"] / prior - 1.0) * 100.0

    @staticmethod
    def _prior_value_asof_release(
        vintages: pd.DataFrame, per_obs: pd.DataFrame
    ) -> pd.Series:
        """Prior period's value AS OF each period's release date (inclusive).

        Same-report revisions share the release's realtime_start, so backward
        as-of matching with an inclusive bound picks up exactly the revised
        prior level the headline change was computed against.
        """
        obs_dates = per_obs.index
        query = pd.DataFrame(
            {
                "obs": obs_dates[1:],  # first obs has no prior
                "date": obs_dates[:-1],  # match vintages of the PRIOR period
                "asof": per_obs["release_date"].to_numpy()[1:],
            }
        )
        merged = pd.merge_asof(
            query.sort_values("asof"),
            vintages[["date", "realtime_start", "value"]].sort_values(
                "realtime_start"
            ),
            left_on="asof",
            right_on="realtime_start",
            by="date",
            direction="backward",  # inclusive: same-day vintages count
        )
        prior = pd.Series(np.nan, index=obs_dates, name="prior_asof")
        prior.loc[merged["obs"].to_numpy()] = merged["value"].to_numpy()
        return prior
