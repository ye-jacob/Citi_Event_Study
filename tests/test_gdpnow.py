"""GDPNow TrackRecord parser against an in-memory workbook."""

from datetime import datetime
from io import BytesIO

import openpyxl
import pandas as pd
import pytest

from src.sources.gdpnow import GdpNowNowcast, parse_track_record


def _workbook_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TrackRecord"
    ws.append(
        [
            "Quarter being forecast",
            "Model Forecast Right Before Advance Estimate",
            "BEA's Advance Estimate",
            "Release Date",
            "",
            "Error",
        ]
    )
    ws.append(
        [datetime(2026, 3, 31), 1.23917, 1.9901, datetime(2026, 4, 30), None, "=C2-B2"]
    )
    ws.append(
        [datetime(2025, 12, 31), 2.99897, 1.42261, datetime(2026, 2, 20), None, "=C3-B3"]
    )
    ws.append([None, None, None, None, None, None])  # trailing junk row
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_track_record_maps_quarter_end_to_quarter_start():
    df = parse_track_record(_workbook_bytes())
    # 2026-03-31 (Q1 end) -> ref_period 2026-01-01 (FRED quarterly obs date).
    assert list(df.index) == [pd.Timestamp(2025, 10, 1), pd.Timestamp(2026, 1, 1)]
    assert len(df) == 2  # junk row dropped
    assert df.loc[pd.Timestamp(2026, 1, 1), "consensus"] == pytest.approx(1.23917)
    # Advance estimate + release date carried along for validation.
    assert df.loc[pd.Timestamp(2026, 1, 1), "advance_estimate"] == pytest.approx(1.9901)
    assert df.loc[pd.Timestamp(2026, 1, 1), "release_date"] == pd.Timestamp(2026, 4, 30)


def test_provider_interface():
    provider = GdpNowNowcast(workbook_bytes=_workbook_bytes())
    assert provider.source_label == "gdpnow"
    df = provider.get_consensus("GDP")
    assert "consensus" in df.columns
    with pytest.raises(ValueError, match="GDP"):
        provider.get_consensus("CPI")


def test_build_releases_from_track_record():
    from datetime import date, datetime, time

    provider = GdpNowNowcast(workbook_bytes=_workbook_bytes())
    releases = provider.build_releases(time(8, 30), date(2020, 1, 1), date(2026, 12, 31))
    assert [r.ref_period for r in releases] == [date(2025, 10, 1), date(2026, 1, 1)]
    q1 = releases[1]
    # actual = BEA advance estimate; consensus = final GDPNow; true release date.
    assert q1.actual == pytest.approx(1.9901)
    assert q1.consensus == pytest.approx(1.23917)
    assert q1.release_datetime == datetime(2026, 4, 30, 8, 30)
    assert q1.is_first_print is True
    assert q1.source == "gdpnow_track"
    # previous = PRIOR quarter's advance estimate (as the market last saw it).
    assert q1.previous == pytest.approx(1.42261)
    assert releases[0].previous is None  # first row in sample has no prior
