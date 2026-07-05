"""Chart helpers return well-formed figures (no rendering)."""

import pandas as pd
import plotly.graph_objects as go

from src import charts


def _toy_curve():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    return pd.DataFrame(
        {"2Y": [4.3, 4.4, 4.35], "5Y": [4.0, 4.05, 4.02],
         "10Y": [4.1, 4.12, 4.11], "30Y": [4.35, 4.33, 4.34]},
        index=idx,
    )


def test_curve_history_fixed_entity_colors():
    fig = charts.fig_curve_history(_toy_curve(), tenors=["10Y", "2Y"])
    assert isinstance(fig, go.Figure)
    by_name = {t.name: t.line.color for t in fig.data}
    # Color follows the entity, not the plot order.
    assert by_name["10Y"] == charts.TENOR_COLORS["10Y"]
    assert by_name["2Y"] == charts.TENOR_COLORS["2Y"]
    assert fig.layout.showlegend is True  # >= 2 series -> legend


def test_single_series_has_no_legend():
    fig = charts.fig_curve_history(_toy_curve(), tenors=["10Y"])
    assert fig.layout.showlegend is False


def test_shape_history_small_multiples():
    from src.analytics.curve import shape_measures

    fig = charts.fig_shape_history(shape_measures(_toy_curve()))
    assert len(fig.data) == 4  # one facet per measure, one axis each


def test_surprise_scatter_with_fit():
    df = pd.DataFrame({"surprise_z": [-1.0, 0.5, 2.0], "delta_bps": [3.0, -1.0, -6.0]})
    fit = pd.DataFrame({"x": [-1.0, 2.0], "y": [2.0, -5.0]})
    fig = charts.fig_surprise_scatter(df, fit=fit)
    assert len(fig.data) == 2


def test_beta_bars_grouped_with_cis():
    betas = pd.DataFrame(
        {
            "factor": ["level", "slope_2s10s", "level", "slope_2s10s"],
            "beta": [4.0, -2.5, 1.5, -1.0],
            "ci_low": [2.0, -4.0, 0.0, -2.2],
            "ci_high": [6.0, -1.0, 3.0, 0.2],
            "side": ["positive", "positive", "negative", "negative"],
        }
    )
    fig = charts.fig_beta_bars(
        betas, group_col="side", color_map=charts.SIGN_COLORS
    )
    assert len(fig.data) == 2  # one trace per group
    assert fig.layout.showlegend is True
    assert fig.data[0].marker.color == charts.SIGN_COLORS["positive"]
    fig_single = charts.fig_beta_bars(betas[betas.side == "positive"])
    assert fig_single.layout.showlegend is False


def test_beta_bars_without_cis():
    df = pd.DataFrame(
        {"factor": ["level", "curvature"], "beta": [0.3, 0.1],
         "expectation": ["nowcast", "nowcast"]}
    )
    fig = charts.fig_beta_bars(
        df, ci_low_col=None, ci_high_col=None,
        group_col="expectation", color_map=charts.EXPECTATION_COLORS,
    )
    assert fig.data[0].error_x.array is None


def test_car_lines():
    cars = pd.DataFrame(
        {
            "tau": [-1, 0, 1, -1, 0, 1],
            "car": [0.0, 3.0, 3.5, 0.0, -2.0, -2.5],
            "group": ["hot", "hot", "hot", "cold", "cold", "cold"],
            "n_events": [15, 15, 15, 14, 14, 14],
        }
    )
    fig = charts.fig_car_lines(cars)
    assert len(fig.data) == 2
    assert "n=15" in fig.data[0].name
    assert fig.data[0].line.color == charts.SIGN_COLORS["hot"]
