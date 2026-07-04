"""Schema roundtrip + seeding idempotency against a temp SQLite DB."""

from datetime import date, datetime

import pytest
from sqlalchemy import select

from src import db
from src.models import CurvePoint, EventImpact, Indicator, Release


@pytest.fixture()
def engine(tmp_path):
    eng = db.get_engine(tmp_path / "test.db")
    db.init_db(eng)
    return eng


def test_seed_indicators_idempotent(engine):
    with db.session_scope(engine) as s:
        db.seed_indicators(s)
        n1 = len(s.execute(select(Indicator)).scalars().all())
    with db.session_scope(engine) as s:
        db.seed_indicators(s)  # second run must not duplicate
        n2 = len(s.execute(select(Indicator)).scalars().all())
    assert n1 == n2 > 0


def test_release_curve_impact_roundtrip(engine):
    with db.session_scope(engine) as s:
        db.seed_indicators(s)
        cpi_id = db.indicator_id_map(s)["CPI"]
        release = Release(
            indicator_id=cpi_id,
            ref_period=date(2024, 3, 1),
            release_datetime=datetime(2024, 4, 10, 8, 30),
            actual=0.4,
            consensus=0.3,
            consensus_stdev=0.1,
            n_estimates=70,
            previous=0.3,
            is_first_print=True,
            source="fred_first+naive_prev",
        )
        s.add(release)
        s.add(CurvePoint(date=date(2024, 4, 10), tenor="10Y", yield_pct=4.55))
        s.flush()
        s.add(
            EventImpact(
                release_id=release.id,
                window_label="tm1c_t0c",
                pre_10y=4.50,
                post_10y=4.55,
                delta_2s10s_bps=-3.5,
            )
        )

    with db.session_scope(engine) as s:
        row = s.execute(select(Release)).scalar_one()
        assert row.indicator.key == "CPI"
        assert row.impacts[0].delta_2s10s_bps == -3.5
        curve = s.execute(select(CurvePoint)).scalar_one()
        assert curve.yield_pct == 4.55


def test_release_uniqueness_constraint(engine):
    from sqlalchemy.exc import IntegrityError

    with db.session_scope(engine) as s:
        db.seed_indicators(s)
        cpi_id = db.indicator_id_map(s)["CPI"]
    kwargs = dict(
        indicator_id=cpi_id,
        ref_period=date(2024, 3, 1),
        release_datetime=datetime(2024, 4, 10, 8, 30),
        actual=0.4,
        is_first_print=True,
        source="fred_first",
    )
    with db.session_scope(engine) as s:
        s.add(Release(**kwargs))
    with pytest.raises(IntegrityError):
        with db.session_scope(engine) as s:
            s.add(Release(**kwargs))  # same (indicator, period, source)
