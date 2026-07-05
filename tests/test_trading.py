"""Trading-oriented tests: gap signal scoring, event-day vol, era split."""

import numpy as np
import pandas as pd
import pytest

from src.analytics.event_study import FACTORS
from src.analytics.trading import (
    build_gap_frame,
    era_split,
    event_day_vol,
    gap_signal_stats,
)


def _gap_obs(gaps, deltas):
    rows = []
    for i, (gz, d) in enumerate(zip(gaps, deltas)):
        row = {"indicator": "CPI", "gap_z": gz}
        for f in FACTORS:
            row[f"delta_{f}"] = d
        rows.append(row)
    return pd.DataFrame(rows)


def test_gap_stats_perfect_signal():
    gaps = [-2.0, -1.0, 1.0, 2.0]
    out = gap_signal_stats(_gap_obs(gaps, [2.0 * g for g in gaps]))
    level = out[out.factor == "level"].iloc[0]
    assert level["hit_rate"] == 1.0
    assert level["mean_pnl"] == pytest.approx(3.0)  # mean |2g| over the gaps
    assert level["gamma"] == pytest.approx(2.0)
    assert level["n"] == 4


def test_gap_stats_useless_signal():
    # Moves are constant regardless of gap sign -> hit rate 0.5, pnl ~ 0.
    out = gap_signal_stats(_gap_obs([-1.0, -1.0, 1.0, 1.0], [1.0, -1.0, 1.0, -1.0]))
    level = out[out.factor == "level"].iloc[0]
    assert level["hit_rate"] == 0.5
    assert level["mean_pnl"] == pytest.approx(0.0)


def test_build_gap_frame_uses_public_information_only():
    releases = pd.DataFrame(
        [
            {
                "indicator": "CPI",
                "ref_period": pd.Timestamp("2024-03-01"),
                "release_datetime": pd.Timestamp("2024-04-10 08:30"),
                "consensus": 0.35,
                "previous": 0.20,  # gap = +0.15, knowable at t-1 close
                "source": "fred_first+cleveland_fed",
            },
            {  # naive rows are not part of the gap signal
                "indicator": "CPI",
                "ref_period": pd.Timestamp("2024-03-01"),
                "release_datetime": pd.Timestamp("2024-04-10 08:30"),
                "consensus": 0.20,
                "previous": 0.20,
                "source": "fred_first+naive_prev",
            },
        ]
    )
    dates = pd.bdate_range("2024-04-08", periods=5)
    curve = pd.DataFrame(
        {"2Y": 4.0, "5Y": 4.0, "10Y": [4.0, 4.0, 4.05, 4.05, 4.05], "30Y": 4.0},
        index=dates,
    )
    out = build_gap_frame(releases, curve)
    assert len(out) == 1
    assert out.loc[0, "delta_level"] == pytest.approx(5.0)


def test_event_day_vol_ratio():
    dates = pd.bdate_range("2024-01-01", periods=61)
    event_positions = [10, 20, 30, 40, 50]
    # Moves must VARY within each group or ddof=1 stdevs are zero/NaN:
    # ordinary days alternate +/-0.1bp, event days jump 3..7bp.
    event_jumps = {10: 0.03, 20: 0.04, 30: 0.05, 40: 0.06, 50: 0.07}
    level = np.full(61, 4.0)
    for i in range(1, 61):
        jump = event_jumps.get(i, 0.001 * (1 if i % 2 else -1))
        level[i] = level[i - 1] + jump
    curve = pd.DataFrame({"2Y": 4.0, "5Y": 4.0, "10Y": level, "30Y": 4.0}, index=dates)
    release_dates = pd.DataFrame(
        {
            "indicator": "CPI",
            "release_datetime": [dates[p] for p in event_positions],
        }
    )
    out = event_day_vol(release_dates, curve)
    level_row = out[out.factor == "level"].iloc[0]
    assert level_row["n_event"] == 5
    assert level_row["mean_abs_event"] == pytest.approx(5.0)  # mean of 3..7
    assert level_row["mean_abs_control"] == pytest.approx(0.1)
    assert level_row["vol_ratio"] > 3


def test_era_split_partitions_sample():
    rows = []
    for i in range(10):
        row = {
            "indicator": "CPI",
            "expectation": "nowcast",
            "release_date": pd.Timestamp("2019-01-15") + pd.DateOffset(months=6 * i),
            "surprise_z": float(i - 5) / 2,
        }
        for f in FACTORS:
            row[f"delta_{f}"] = 2.0 * row["surprise_z"]
        rows.append(row)
    out = era_split(pd.DataFrame(rows), cutoff="2021-01-01")
    assert set(out["era"]) == {"pre_2021", "post_2021"}
    n_by_era = out[out.factor == "level"].set_index("era")["n"]
    assert n_by_era.sum() == 10
    assert (out[out.factor == "level"]["beta"] - 2.0).abs().max() < 1e-6
