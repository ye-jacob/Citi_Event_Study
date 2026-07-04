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


def test_beta_bars_with_cis_and_regimes():
    betas = pd.DataFrame(
        {
            "indicator": ["CPI", "NFP", "CPI", "NFP"],
            "beta": [-4.0, -2.5, -1.5, -1.0],
            "ci_low": [-6.0, -4.0, -3.0, -2.2],
            "ci_high": [-2.0, -1.0, 0.0, 0.2],
            "regime": ["hiking", "hiking", "hold", "hold"],
        }
    )
    fig = charts.fig_beta_bars(betas, regime_col="regime")
    assert len(fig.data) == 2  # one trace per regime
    assert fig.layout.showlegend is True
    fig_single = charts.fig_beta_bars(betas[betas.regime == "hiking"])
    assert fig_single.layout.showlegend is False
