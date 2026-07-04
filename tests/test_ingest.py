"""Ingest CLI: vintage is mandatory; upserts are idempotent."""

from datetime import date, datetime

import pandas as pd
import pytest
from sqlalchemy import select

from src import db
from src.ingest.run_ingest import build_parser, upsert_curve, upsert_releases
from src.models import CurvePoint, Release as ReleaseRow
from src.sources.base import Release


def test_vintage_is_required():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])  # no --vintage -> argparse error


def test_vintage_choices():
    args = build_parser().parse_args(["--vintage", "first"])
    assert args.vintage == "first"
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--vintage", "revised"])


@pytest.fixture()
def engine(tmp_path):
    eng = db.get_engine(tmp_path / "ingest.db")
    db.init_db(eng)
    return eng


def test_upsert_curve_idempotent_and_skips_nan(engine):
    curve = pd.DataFrame(
        {"2Y": [4.5, 4.6], "10Y": [4.1, float("nan")]},
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )
    with db.session_scope(engine) as s:
        assert upsert_curve(s, curve) == 3  # NaN holiday point skipped
    revised = curve.copy()
    revised.loc["2024-01-02", "10Y"] = 4.15
    with db.session_scope(engine) as s:
        upsert_curve(s, revised)  # re-run updates in place, no dupes
        rows = s.execute(select(CurvePoint)).scalars().all()
        assert len(rows) == 3
        ten_y = {(r.date.isoformat(), r.tenor): r.yield_pct for r in rows}
        assert ten_y[("2024-01-02", "10Y")] == 4.15


def test_upsert_releases_idempotent(engine):
    with db.session_scope(engine) as s:
        db.seed_indicators(s)
        ids = db.indicator_id_map(s)
    release = Release(
        indicator="CPI",
        ref_period=date(2024, 3, 1),
        release_datetime=datetime(2024, 4, 10, 8, 30),
        actual=0.4,
        consensus=0.3,
        consensus_stdev=None,
        n_estimates=None,
        previous=0.3,
        is_first_print=True,
        source="fred_first+naive_prev",
    )
    with db.session_scope(engine) as s:
        upsert_releases(s, ids, [release])
        upsert_releases(s, ids, [release])  # same key -> update, not dupe
        rows = s.execute(select(ReleaseRow)).scalars().all()
        assert len(rows) == 1
        assert rows[0].actual == 0.4
