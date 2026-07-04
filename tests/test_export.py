"""CSV audit export: files, headers, row counts."""

from datetime import date, datetime

from src import db
from src.ingest.export_csv import export
from src.models import CurvePoint, Release


def test_export_writes_both_csvs(tmp_path):
    db_path = tmp_path / "t.db"
    engine = db.get_engine(db_path)
    db.init_db(engine)
    with db.session_scope(engine) as s:
        db.seed_indicators(s)
        cpi_id = db.indicator_id_map(s)["CPI"]
        s.add(
            Release(
                indicator_id=cpi_id,
                ref_period=date(2024, 3, 1),
                release_datetime=datetime(2024, 4, 10, 8, 30),
                actual=0.4,
                consensus=0.35,
                is_first_print=True,
                source="fred_first+cleveland_fed",
            )
        )
        s.add(CurvePoint(date=date(2024, 4, 10), tenor="10Y", yield_pct=4.55))
        s.add(CurvePoint(date=date(2024, 4, 10), tenor="2Y", yield_pct=4.90))

    paths = export(db_path, tmp_path / "exports")

    releases = (paths["releases"]).read_text().splitlines()
    assert releases[0] == (
        "indicator,units,ref_period,release_datetime,actual,consensus,"
        "consensus_stdev,n_estimates,previous,is_first_print,source"
    )
    assert len(releases) == 2
    assert releases[1].startswith("CPI,% m/m,2024-03-01")

    curve = (paths["curve"]).read_text().splitlines()
    assert curve[0] == "date,2Y,10Y"  # registry tenor order, only present tenors
    assert curve[1] == "2024-04-10,4.9,4.55"
