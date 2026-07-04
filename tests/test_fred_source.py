"""FredDataSource against a fake fredapi client (no network).

The fake reproduces fredapi's get_series_all_releases shape:
columns realtime_start / date / value, one row per vintage.

Vintage timeline used throughout:

  2024-02-13  Jan first print 100.0
  2024-03-12  Jan revised to 101.0  (same report as Feb's first print — NFP-style)
  2024-03-12  Feb first print 102.0
  2024-03-20  Jan revised again to 100.5  (AFTER Feb's release — must not leak in)
  2024-04-10  Mar first print 103.5

So the as-reported Feb change is 102 - 101 = 1.0 (against the same-report
revision), NOT 102 - 100 (diff of first prints) and NOT 102 - 100.5 (a
revision the market hadn't seen yet).
"""

from datetime import date, datetime, time

import pandas as pd
import pytest

from src.sources.fred import FredDataSource

REGISTRY = [
    {
        "key": "CPI",
        "name": "CPI",
        "freq": "monthly",
        "fred_series": "CPIAUCSL",
        "yield_sign": 1,
        "release_time": time(8, 30),
        "transform": "pct_change",
        "units": "% m/m",
        "active": True,
        "notes": "",
    },
    {
        "key": "NFP",
        "name": "NFP",
        "freq": "monthly",
        "fred_series": "PAYEMS",
        "yield_sign": 1,
        "release_time": time(8, 30),
        "transform": "diff",
        "units": "k",
        "active": True,
        "notes": "",
    },
    {
        "key": "UNRATE",
        "name": "UNRATE",
        "freq": "monthly",
        "fred_series": "UNRATE",
        "yield_sign": -1,
        "release_time": time(8, 30),
        "transform": "none",
        "units": "%",
        "active": True,
        "notes": "",
    },
    {
        "key": "ISM",
        "name": "ISM",
        "freq": "monthly",
        "fred_series": None,
        "yield_sign": 1,
        "release_time": time(10, 0),
        "transform": "none",
        "units": "index",
        "active": False,
        "notes": "licensing",
    },
]


class FakeFred:
    def __init__(self):
        self.all_releases = pd.DataFrame(
            {
                "realtime_start": pd.to_datetime(
                    [
                        "2024-02-13",
                        "2024-03-12",
                        "2024-03-12",
                        "2024-03-20",
                        "2024-04-10",
                    ]
                ),
                "date": pd.to_datetime(
                    [
                        "2024-01-01",
                        "2024-01-01",
                        "2024-02-01",
                        "2024-01-01",
                        "2024-03-01",
                    ]
                ),
                "value": [100.0, 101.0, 102.0, 100.5, 103.5],
            }
        )
        self.curve = {
            "DGS2": pd.Series(
                [4.5, 4.6], index=pd.to_datetime(["2024-01-02", "2024-01-03"])
            ),
            "DGS10": pd.Series(
                [4.1, float("nan")],
                index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
            ),
        }

    def get_series_all_releases(self, series_id):
        return self.all_releases.copy()

    def get_series(self, series_id, observation_start=None, observation_end=None):
        return self.curve[series_id].copy()


@pytest.fixture()
def fake():
    return FakeFred()


def _src(fake, vintage="first"):
    return FredDataSource(vintage=vintage, fred=fake, registry=REGISTRY)


# --------------------------------------------------- first-print semantics


def test_diff_uses_same_report_revision_not_first_print(fake):
    releases = _src(fake).get_releases("NFP", date(2024, 1, 1), date(2024, 12, 31))
    # Jan has no prior -> dropped; Feb reported change = 102 - 101 (the prior
    # level as revised in the SAME report), not 102 - 100.
    assert [r.ref_period for r in releases] == [date(2024, 2, 1), date(2024, 3, 1)]
    assert releases[0].actual == pytest.approx(1.0)
    assert releases[1].actual == pytest.approx(1.5)  # 103.5 - 102
    assert all(r.is_first_print for r in releases)
    assert releases[0].source == "fred_first"


def test_revisions_after_release_day_do_not_leak(fake):
    # Jan's 2024-03-20 revision to 100.5 postdates Feb's 03-12 release: the
    # as-of lookup must use 101.0, never 100.5.
    releases = _src(fake).get_releases("NFP", date(2024, 2, 1), date(2024, 2, 28))
    assert releases[0].actual == pytest.approx(102.0 - 101.0)


def test_pct_change_same_vintage_and_previous_chain(fake):
    releases = _src(fake).get_releases("CPI", date(2024, 1, 1), date(2024, 12, 31))
    feb = (102.0 / 101.0 - 1) * 100
    mar = (103.5 / 102.0 - 1) * 100
    assert releases[0].actual == pytest.approx(feb)
    assert releases[1].actual == pytest.approx(mar)
    # previous = the prior release's own as-reported headline
    assert releases[1].previous == pytest.approx(feb)
    assert releases[0].previous is None  # Jan's change is undefined
    assert releases[0].consensus is None  # FRED carries no consensus


def test_transform_none_takes_first_print_as_is(fake):
    releases = _src(fake).get_releases("UNRATE", date(2024, 1, 1), date(2024, 12, 31))
    # No differencing -> Jan survives with its first print (100.0, not 100.5).
    assert [r.ref_period for r in releases] == [
        date(2024, 1, 1),
        date(2024, 2, 1),
        date(2024, 3, 1),
    ]
    assert releases[0].actual == pytest.approx(100.0)
    assert releases[0].previous is None
    assert releases[1].previous == pytest.approx(100.0)


def test_pre_inception_backfill_dropped(fake):
    # A series added to FRED on 2024-05-01: Jan/Feb/Mar all "first appear" that
    # day (backfill — revisions with fake release dates), Apr genuinely prints
    # on 2024-05-03. Only Apr may survive as a first print.
    fake.all_releases = pd.DataFrame(
        {
            "realtime_start": pd.to_datetime(
                ["2024-05-01", "2024-05-01", "2024-05-01", "2024-05-03"]
            ),
            "date": pd.to_datetime(
                ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]
            ),
            "value": [5.0, 5.1, 5.2, 5.3],
        }
    )
    releases = _src(fake).get_releases("UNRATE", date(2024, 1, 1), date(2024, 12, 31))
    assert [r.ref_period for r in releases] == [date(2024, 4, 1)]
    assert releases[0].actual == pytest.approx(5.3)


def test_single_obs_at_minimum_realtime_is_kept(fake):
    # The default fixture's earliest vintage (2024-02-13) covers exactly ONE
    # observation — a legitimate first release, not backfill.
    releases = _src(fake).get_releases("UNRATE", date(2024, 1, 1), date(2024, 12, 31))
    assert releases[0].ref_period == date(2024, 1, 1)


# ------------------------------------------------------ latest-vintage path


def test_latest_vintage_uses_revised_values_but_original_release_date(fake):
    releases = _src(fake, vintage="latest").get_releases(
        "NFP", date(2024, 1, 1), date(2024, 12, 31)
    )
    # Latest levels: Jan 100.5, Feb 102, Mar 103.5.
    assert releases[0].actual == pytest.approx(1.5)
    assert releases[1].actual == pytest.approx(1.5)
    assert releases[0].is_first_print is False
    # But the event still happened when the first print hit the tape.
    assert releases[0].release_datetime == datetime(2024, 3, 12, 8, 30)


# ----------------------------------------------------------- shared plumbing


def test_release_datetime_combines_alfred_date_and_registry_time(fake):
    releases = _src(fake).get_releases("CPI", date(2024, 1, 1), date(2024, 12, 31))
    assert releases[0].release_datetime == datetime(2024, 3, 12, 8, 30)


def test_ref_period_window_filter(fake):
    releases = _src(fake).get_releases("CPI", date(2024, 3, 1), date(2024, 3, 31))
    assert [r.ref_period for r in releases] == [date(2024, 3, 1)]


def test_curve_frame_shape(fake):
    df = _src(fake).get_curve(date(2024, 1, 1), date(2024, 1, 31), tenors=["2Y", "10Y"])
    assert list(df.columns) == ["2Y", "10Y"]
    assert df.index.name == "date"
    assert df.loc["2024-01-02", "10Y"] == pytest.approx(4.1)
    assert pd.isna(df.loc["2024-01-03", "10Y"])  # holiday NaN preserved


def test_indicator_without_series_raises(fake):
    with pytest.raises(ValueError, match="no FRED series"):
        _src(fake).get_releases("ISM", date(2024, 1, 1), date(2024, 12, 31))


def test_invalid_vintage_rejected(fake):
    with pytest.raises(ValueError, match="vintage"):
        FredDataSource(vintage="revised", fred=fake, registry=REGISTRY)
