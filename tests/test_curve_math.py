"""Curve decomposition math vs hand-computed values (formulas from CLAUDE.md)."""

import pandas as pd
import pytest

from src.analytics import curve


@pytest.fixture()
def toy():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    return pd.DataFrame(
        {
            "2Y": [4.30, 4.40],
            "5Y": [4.00, 4.05],
            "10Y": [4.10, 4.12],
            "30Y": [4.35, 4.33],
        },
        index=idx,
    )


def test_level_is_10y(toy):
    assert curve.level(toy).tolist() == [4.10, 4.12]


def test_slope_2s10s(toy):
    # 10Y - 2Y
    assert curve.slope_2s10s(toy).tolist() == pytest.approx([-0.20, -0.28])


def test_slope_5s30s(toy):
    # 30Y - 5Y
    assert curve.slope_5s30s(toy).tolist() == pytest.approx([0.35, 0.28])


def test_curvature(toy):
    # 2*10Y - 2Y - 30Y
    expected = [2 * 4.10 - 4.30 - 4.35, 2 * 4.12 - 4.40 - 4.33]
    assert curve.curvature(toy).tolist() == pytest.approx(expected)


def test_shape_measures_columns(toy):
    m = curve.shape_measures(toy)
    assert list(m.columns) == curve.SHAPE_MEASURES


def test_change_between_in_bps(toy):
    d0, d1 = toy.index[0], toy.index[1]
    delta = curve.change_between(toy, d0, d1)
    # 2s10s: -0.28 - (-0.20) = -0.08pp = -8 bps (a flattening)
    assert delta["slope_2s10s"] == pytest.approx(-8.0)
    assert delta["level"] == pytest.approx(2.0)


def test_change_between_refuses_to_guess_dates(toy):
    with pytest.raises(KeyError):
        curve.change_between(toy, toy.index[0], pd.Timestamp("2024-01-06"))


def test_missing_tenor_raises():
    df = pd.DataFrame({"10Y": [4.0]})
    with pytest.raises(KeyError):
        curve.slope_2s10s(df)
