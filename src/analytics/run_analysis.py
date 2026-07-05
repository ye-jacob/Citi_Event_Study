"""Run the full analysis (Methodology 3.1-3.4) and store results in the DB.

    python -m src.analytics.run_analysis [--db data/event_study.db]

Reads releases + curve, computes standardized surprises and release-window
factor changes, estimates every specification, and writes four tables the app
and writeup read:

    analysis_observations  one row per (release x expectation): surprise_z +
                           delta_<factor> in bps  (the scatter/audit layer)
    analysis_baseline      3.1/3.3 betas per (indicator, expectation, factor)
    analysis_asymmetry     3.2 split betas per (indicator, factor)
    analysis_event_study   3.4 mean CAR paths per (indicator, factor, group)

Numbers only — interpretation belongs to the author in analysis/findings.md.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

from src import config, db
from src.analytics.event_study import (
    event_study_cars,
    fit_asymmetric,
    fit_baseline,
    release_day_changes,
)
from src.analytics.surprise import standardized_surprises

RELEASES_SQL = """
    SELECT i.key AS indicator, r.ref_period, r.release_datetime,
           r.actual, r.consensus, r.source
    FROM releases r JOIN indicators i ON i.id = r.indicator_id
"""


def load_inputs(db_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    with sqlite3.connect(db_path) as con:
        releases = pd.read_sql(
            RELEASES_SQL, con, parse_dates=["ref_period", "release_datetime"]
        )
        curve_long = pd.read_sql(
            "SELECT date, tenor, yield AS y FROM curve", con, parse_dates=["date"]
        )
    curve = curve_long.pivot(index="date", columns="tenor", values="y").sort_index()
    return releases, curve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.analytics.run_analysis",
        description=__doc__.splitlines()[0],
    )
    parser.add_argument("--db", default=config.DB_PATH, type=Path)
    args = parser.parse_args(argv)
    if not args.db.exists():
        parser.error(f"{args.db} not found — run the ingest first.")

    releases, curve = load_inputs(args.db)
    surprises = standardized_surprises(releases)
    obs = release_day_changes(surprises, curve)
    baseline = fit_baseline(obs)
    asymmetry = fit_asymmetric(obs)
    cars = event_study_cars(obs, curve)

    engine = db.get_engine(args.db)
    obs.to_sql("analysis_observations", engine, if_exists="replace", index=False)
    baseline.to_sql("analysis_baseline", engine, if_exists="replace", index=False)
    asymmetry.to_sql("analysis_asymmetry", engine, if_exists="replace", index=False)
    cars.to_sql("analysis_event_study", engine, if_exists="replace", index=False)

    dropped = obs.attrs.get("dropped_no_window", 0)
    print(
        f"observations: {len(obs)} (dropped {dropped} without a clean curve "
        f"window) -> analysis_observations"
    )
    print(f"baseline fits: {len(baseline)} | asymmetry: {len(asymmetry)} | "
          f"event-study rows: {len(cars)}")

    nowcast = baseline[baseline.expectation == "nowcast"]
    print("\nbeta (bps per 1 sigma surprise), nowcast expectation:")
    print(
        nowcast.pivot(index="indicator", columns="factor", values="beta")
        .round(2)
        .to_string()
    )
    print("\nR-squared, nowcast vs naive (matched samples):")
    print(
        baseline.pivot_table(
            index=["indicator", "factor"], columns="expectation", values="r2"
        )
        .round(3)
        .to_string()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
