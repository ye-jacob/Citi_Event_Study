"""Event-study mechanics: windows, OLS recovery, asymmetry, CARs."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src.analytics.event_study import (
    FACTORS,
    event_study_cars,
    fit_asymmetric,
    fit_baseline,
    release_day_changes,
)


def _flat_curve(dates, ten_y):
    """Curve where only 10Y varies -> level delta known, slopes/curv derived."""
    return pd.DataFrame(
        {"2Y": 4.0, "5Y": 4.0, "10Y": ten_y, "30Y": 4.0}, index=dates
    )


def _surprise_row(indicator, period, release_dt, z):
    return {
        "indicator": indicator,
        "ref_period": pd.Timestamp(period),
        "release_datetime": release_dt,
        "expectation": "nowcast",
        "surprise_raw": z,
        "surprise_z": z,
    }


# ----------------------------------------------------------------- windows


def test_release_day_change_is_close_over_close():
    dates = pd.bdate_range("2024-04-08", periods=5)  # Mon..Fri
    curve = _flat_curve(dates, [4.00, 4.00, 4.05, 4.05, 4.05])
    s = pd.DataFrame(
        [_surprise_row("CPI", "2024-03-01", datetime(2024, 4, 10, 8, 30), 1.0)]
    )
    obs = release_day_changes(s, curve)
    # Wed release: F(Wed) - F(Tue) = 5bp on the level, 0 elsewhere... slopes
    # move too since only 10Y moved: 2s10s +5, 5s30s 0, curvature +10.
    assert obs.loc[0, "delta_level"] == pytest.approx(5.0)
    assert obs.loc[0, "delta_slope_2s10s"] == pytest.approx(5.0)
    assert obs.loc[0, "delta_slope_5s30s"] == pytest.approx(0.0)
    assert obs.loc[0, "delta_curvature"] == pytest.approx(10.0)


def test_weekend_release_maps_to_next_close():
    dates = pd.bdate_range("2024-04-08", periods=10)
    curve = _flat_curve(dates, np.linspace(4.0, 4.09, 10))
    s = pd.DataFrame(
        [_surprise_row("CPI", "2024-03-01", datetime(2024, 4, 13, 8, 30), 1.0)]
    )  # Saturday
    obs = release_day_changes(s, curve)
    # Day 0 = Monday 04/15; pre = Friday 04/12 -> one daily step of 1bp.
    assert obs.loc[0, "delta_level"] == pytest.approx(1.0)


def test_long_gap_dropped():
    dates = pd.to_datetime(["2024-04-01", "2024-04-30"])
    curve = _flat_curve(dates, [4.0, 4.5])
    s = pd.DataFrame(
        [_surprise_row("CPI", "2024-03-01", datetime(2024, 4, 15, 8, 30), 1.0)]
    )
    obs = release_day_changes(s, curve)
    assert obs.empty
    assert obs.attrs["dropped_no_window"] == 1


# -------------------------------------------------------------- estimation


def _obs_frame(z, deltas):
    rows = []
    for i, (zi, di) in enumerate(zip(z, deltas)):
        row = {
            "indicator": "CPI",
            "expectation": "nowcast",
            "ref_period": pd.Timestamp(2020, 1, 1) + pd.DateOffset(months=i),
            "release_date": pd.Timestamp(2020, 2, 1) + pd.DateOffset(months=i),
            "surprise_z": zi,
        }
        for f in FACTORS:
            row[f"delta_{f}"] = di
        rows.append(row)
    return pd.DataFrame(rows)


def test_fit_baseline_recovers_known_beta():
    z = [-2.0, -1.0, 0.0, 1.0, 2.0]
    obs = _obs_frame(z, [5.0 * zi for zi in z])  # exact dF = 5*S
    out = fit_baseline(obs)
    assert len(out) == len(FACTORS)
    level = out[out.factor == "level"].iloc[0]
    assert level["beta"] == pytest.approx(5.0)
    assert level["alpha"] == pytest.approx(0.0, abs=1e-9)
    assert level["r2"] == pytest.approx(1.0)
    assert level["n"] == 5


def test_fit_asymmetric_recovers_split_betas():
    z = [-3.0, -2.0, -1.0, 1.0, 2.0, 3.0]
    noise = [0.05, -0.05, 0.02, -0.02, 0.04, -0.04]
    # dF = 3*S+ + 1*S- (+ tiny noise so the robust Wald test is nondegenerate)
    deltas = [3.0 * max(zi, 0) + 1.0 * min(zi, 0) + e for zi, e in zip(z, noise)]
    out = fit_asymmetric(_obs_frame(z, deltas))
    level = out[out.factor == "level"].iloc[0]
    assert level["beta_pos"] == pytest.approx(3.0, abs=0.1)
    assert level["beta_neg"] == pytest.approx(1.0, abs=0.1)
    assert level["r2"] > 0.99
    assert 0.0 <= level["p_equal"] <= 1.0


# ------------------------------------------------------------- event study


def test_event_study_cars_zero_when_all_days_alike():
    # 10Y rises exactly 1bp every trading day -> every daily level change is
    # 1bp, control mean is 1bp, so abnormal CARs are identically zero.
    dates = pd.bdate_range("2024-01-01", periods=120)
    curve = _flat_curve(dates, 4.0 + 0.0001 * np.arange(120) * 100 / 100)

    releases = []
    for i in range(12):
        d = dates[20 + i * 7]
        releases.append(
            _surprise_row("CPI", f"2023-{i % 12 + 1:02d}-01",
                          d.to_pydatetime().replace(hour=8, minute=30),
                          float(i + 1))
        )
    s = pd.DataFrame(releases)
    obs = release_day_changes(s, curve)
    cars = event_study_cars(obs, curve)

    assert set(cars["group"]) == {"hot", "cold"}
    level_hot = cars[(cars.factor == "level") & (cars.group == "hot")]
    assert list(level_hot["tau"]) == list(range(-5, 11))
    assert level_hot["car"].abs().max() == pytest.approx(0.0, abs=1e-9)
    assert (level_hot["n_events"] >= 1).all()
