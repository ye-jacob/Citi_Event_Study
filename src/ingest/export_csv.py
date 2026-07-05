"""Export the DB to CSVs for manual verification / audit.

    python -m src.ingest.export_csv [--db data/event_study.db] [--out data/exports]

Writes releases.csv (one row per release x provenance) and curve.csv (wide,
one column per tenor). Column-by-column provenance, with links, lives in
data/exports/DATA_DICTIONARY.md — keep it next to the CSVs.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

from src import config

RELEASES_SQL = """
    SELECT i.key AS indicator, i.units, r.ref_period, r.release_datetime,
           r.actual, r.consensus, r.consensus_stdev, r.n_estimates, r.previous,
           r.is_first_print, r.source
    FROM releases r JOIN indicators i ON i.id = r.indicator_id
    ORDER BY i.key, r.ref_period, r.source
"""

CURVE_SQL = "SELECT date, tenor, yield AS yield_pct FROM curve ORDER BY date"


def export(db_path: Path, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        releases = pd.read_sql(
            RELEASES_SQL, con, parse_dates=["ref_period", "release_datetime"]
        )
        curve_long = pd.read_sql(CURVE_SQL, con)

    # Explicit date formats, no microseconds: fractional seconds make Excel
    # display datetimes as "mm:ss.0", and a save from Excel then destroys the
    # column. These forms survive both pandas parse_dates and a spreadsheet
    # round trip legibly.
    releases["ref_period"] = releases["ref_period"].dt.strftime("%Y-%m-%d")
    releases["release_datetime"] = releases["release_datetime"].dt.strftime(
        "%Y-%m-%d %H:%M"
    )

    releases_path = out_dir / "releases.csv"
    releases.to_csv(releases_path, index=False)

    curve = curve_long.pivot(index="date", columns="tenor", values="yield_pct")
    ordered = [t for t in config.TENOR_FRED_SERIES if t in curve.columns]
    curve_path = out_dir / "curve.csv"
    curve[ordered].to_csv(curve_path)

    return {"releases": releases_path, "curve": curve_path}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.ingest.export_csv",
        description=__doc__.splitlines()[0],
    )
    parser.add_argument("--db", default=config.DB_PATH, type=Path)
    parser.add_argument("--out", default=config.DATA_DIR / "exports", type=Path)
    args = parser.parse_args(argv)

    if not Path(args.db).exists():
        parser.error(f"{args.db} not found — run the ingest first.")
    paths = export(Path(args.db), Path(args.out))
    for name, path in paths.items():
        n = sum(1 for _ in open(path)) - 1
        print(f"{name}: {n} rows -> {path}")
    print(f"provenance: see {Path(args.out) / 'DATA_DICTIONARY.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
