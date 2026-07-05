"""Plotly figure helpers — used by analysis notebooks (figures/) and the app.

Presentation conventions follow the dataviz reference palette (validated:
worst adjacent CVD dE 24.2). Rules encoded here:

- Color follows the ENTITY: each tenor / shape measure / regime owns a fixed
  slot; filtering never repaints survivors.
- One axis — measures on different scales get small multiples, never dual axes.
- 2px lines; >=8px markers with a 2px surface ring; hairline solid gridlines.
- Aqua/yellow/magenta slots sit below 3:1 contrast on the light surface, so
  every chart's data must also be reachable as a table (the app provides one).

These helpers only draw. No I/O, no DB access, no analytics.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- reference palette (light mode) ---------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

# Categorical slots in fixed, CVD-validated order — never cycled or re-ranked.
_SLOTS = [
    "#2a78d6",  # 1 blue
    "#1baf7a",  # 2 aqua
    "#eda100",  # 3 yellow
    "#008300",  # 4 green
    "#4a3aa7",  # 5 violet
    "#e34948",  # 6 red
    "#e87ba4",  # 7 magenta
    "#eb6834",  # 8 orange
]

# Fixed entity -> color assignments.
TENOR_COLORS = {
    "2Y": _SLOTS[0],
    "5Y": _SLOTS[1],
    "10Y": _SLOTS[2],
    "30Y": _SLOTS[3],
    "3M": _SLOTS[4],
    "1Y": _SLOTS[5],
    "7Y": _SLOTS[6],
    "20Y": _SLOTS[7],
}
MEASURE_COLORS = {
    "level": _SLOTS[0],
    "slope_2s10s": _SLOTS[1],
    "slope_5s30s": _SLOTS[2],
    "curvature": _SLOTS[4],
}
# Polarity pairs use the diverging convention (warm = hot/upside, cool = cold/
# downside); the expectation measures are two entities with fixed slots.
SIGN_COLORS = {"hot": _SLOTS[5], "cold": _SLOTS[0], "positive": _SLOTS[5], "negative": _SLOTS[0]}
EXPECTATION_COLORS = {"nowcast": _SLOTS[0], "naive": _SLOTS[4]}
ERA_COLORS = {"pre_2021": _SLOTS[4], "post_2021": _SLOTS[0]}

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
ACCENT = _SLOTS[0]
ACCENT_DARK = "#184f95"  # blue-600, for fit lines over blue markers


def _base_layout(fig: go.Figure, *, title: str | None, show_legend: bool) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(color=INK, size=16)) if title else None,
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT, color=INK_SECONDARY, size=12),
        showlegend=show_legend,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, x=0,
            font=dict(color=INK_SECONDARY),
        ),
        margin=dict(l=56, r=24, t=56 if title else 24, b=44),
        hovermode="closest",
        hoverlabel=dict(font=dict(family=FONT)),
    )
    fig.update_xaxes(
        gridcolor=GRIDLINE, gridwidth=1, linecolor=BASELINE, zeroline=False,
        tickfont=dict(color=INK_MUTED),
    )
    fig.update_yaxes(
        gridcolor=GRIDLINE, gridwidth=1, linecolor=BASELINE, zeroline=False,
        tickfont=dict(color=INK_MUTED),
    )
    return fig


def fig_curve_history(
    curve: pd.DataFrame, tenors: list[str] | None = None, title: str | None = None
) -> go.Figure:
    """Yield time series, one 2px line per tenor (date index x tenor columns)."""
    tenors = tenors or [t for t in TENOR_COLORS if t in curve.columns]
    fig = go.Figure()
    for tenor in tenors:
        fig.add_trace(
            go.Scatter(
                x=curve.index,
                y=curve[tenor],
                name=tenor,
                mode="lines",
                line=dict(color=TENOR_COLORS.get(tenor, INK_MUTED), width=2),
                hovertemplate="%{y:.2f}%<extra>" + tenor + "</extra>",
            )
        )
    _base_layout(fig, title=title, show_legend=len(tenors) >= 2)
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(title_text="Yield (%)", title_font=dict(color=INK_MUTED))
    return fig


def fig_shape_history(shape: pd.DataFrame, title: str | None = None) -> go.Figure:
    """Level / slopes / curvature as SMALL MULTIPLES (shared x, one axis each).

    The measures live on different scales — separate facets, never a dual axis.
    One series per facet, so the facet title carries identity (no legend).
    """
    measures = [m for m in MEASURE_COLORS if m in shape.columns]
    fig = make_subplots(
        rows=len(measures), cols=1, shared_xaxes=True, vertical_spacing=0.06,
        subplot_titles=[m.replace("_", " ") for m in measures],
    )
    for i, m in enumerate(measures, start=1):
        fig.add_trace(
            go.Scatter(
                x=shape.index,
                y=shape[m],
                name=m,
                mode="lines",
                line=dict(color=MEASURE_COLORS[m], width=2),
                hovertemplate="%{y:.2f}%<extra>" + m + "</extra>",
            ),
            row=i,
            col=1,
        )
    _base_layout(fig, title=title, show_legend=False)
    fig.update_layout(height=max(480, 170 * len(measures)))
    fig.update_annotations(font=dict(color=INK_SECONDARY, size=12))
    return fig


def fig_surprise_scatter(
    df: pd.DataFrame,
    x: str = "surprise_z",
    y: str = "delta_bps",
    fit: pd.DataFrame | None = None,
    title: str | None = None,
    x_title: str = "Standardized surprise (σ)",
    y_title: str = "Curve change (bps)",
) -> go.Figure:
    """Surprise vs curve-change dots; optional precomputed fit line overlay.

    The fit (the regression) is human-owned — this only draws whatever
    ``fit`` frame (columns x, y) the human passes in.
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df[x],
            y=df[y],
            mode="markers",
            name="releases",
            marker=dict(
                color=ACCENT, size=9,
                line=dict(color=SURFACE, width=2),  # 2px surface ring
            ),
            hovertemplate=f"{x_title}: %{{x:.2f}}<br>{y_title}: %{{y:.1f}}<extra></extra>",
        )
    )
    if fit is not None:
        fig.add_trace(
            go.Scatter(
                x=fit["x"], y=fit["y"], mode="lines", name="OLS fit",
                line=dict(color=ACCENT_DARK, width=2),
            )
        )
    _base_layout(fig, title=title, show_legend=fit is not None)
    fig.update_xaxes(title_text=x_title, zeroline=True, zerolinecolor=BASELINE, zerolinewidth=1)
    fig.update_yaxes(title_text=y_title, zeroline=True, zerolinecolor=BASELINE, zerolinewidth=1)
    return fig


def fig_beta_bars(
    betas: pd.DataFrame,
    label_col: str = "factor",
    beta_col: str = "beta",
    ci_low_col: str | None = "ci_low",
    ci_high_col: str | None = "ci_high",
    group_col: str | None = None,
    color_map: dict[str, str] | None = None,
    title: str | None = None,
    x_title: str = "bps per 1σ surprise",
) -> go.Figure:
    """Horizontal bars with optional CI whiskers and optional grouping.

    One bar per label row; when ``group_col`` is given, one trace per group
    (colored via ``color_map``, legended). CI columns may be None for
    whisker-less bars (e.g. an R² comparison).
    """
    fig = go.Figure()
    has_ci = bool(
        ci_low_col and ci_high_col
        and ci_low_col in betas.columns and ci_high_col in betas.columns
    )

    def _bar(rows: pd.DataFrame, name: str | None, color: str, show: bool) -> None:
        error_x = None
        if has_ci:
            error_x = dict(
                type="data",
                array=rows[ci_high_col] - rows[beta_col],
                arrayminus=rows[beta_col] - rows[ci_low_col],
                color=INK_SECONDARY,
                thickness=2,
                width=4,
            )
        fig.add_trace(
            go.Bar(
                y=rows[label_col],
                x=rows[beta_col],
                name=name or beta_col,
                orientation="h",
                marker=dict(color=color, cornerradius=4),
                showlegend=show,
                error_x=error_x,
                hovertemplate=(
                    "%{y}: %{x:.2f} " + x_title + "<extra>" + (name or "") + "</extra>"
                ),
            )
        )

    if group_col and group_col in betas.columns:
        colors = color_map or {}
        for group, rows in betas.groupby(group_col, sort=False):
            _bar(rows, str(group), colors.get(str(group), INK_MUTED), True)
        fig.update_layout(barmode="group")
    else:
        _bar(betas, None, ACCENT, False)

    show_legend = bool(group_col and group_col in betas.columns)
    _base_layout(fig, title=title, show_legend=show_legend)
    fig.update_layout(bargap=0.45)
    fig.update_xaxes(title_text=x_title, zeroline=True, zerolinecolor=BASELINE, zerolinewidth=1)
    fig.update_yaxes(showgrid=False)
    return fig


def fig_car_lines(
    cars: pd.DataFrame,
    tau_col: str = "tau",
    car_col: str = "car",
    group_col: str = "group",
    color_map: dict[str, str] | None = None,
    title: str | None = None,
    y_title: str = "Cumulative abnormal change (bps)",
) -> go.Figure:
    """Event-study CAR paths: one 2px line per group, day-0 marked.

    Expects one (indicator, factor) slice of the analysis_event_study table.
    """
    colors = color_map or SIGN_COLORS
    fig = go.Figure()
    for group, rows in cars.groupby(group_col, sort=False):
        rows = rows.sort_values(tau_col)
        n = int(rows["n_events"].iloc[0]) if "n_events" in rows.columns else None
        name = f"{group} (n={n})" if n is not None else str(group)
        fig.add_trace(
            go.Scatter(
                x=rows[tau_col],
                y=rows[car_col],
                name=name,
                mode="lines",
                line=dict(color=colors.get(str(group), INK_MUTED), width=2),
                hovertemplate="τ=%{x}: %{y:.1f} bps<extra>" + str(group) + "</extra>",
            )
        )
    _base_layout(fig, title=title, show_legend=True)
    fig.add_vline(x=0, line_width=1, line_color=BASELINE)
    fig.update_xaxes(title_text="Trading days relative to release")
    fig.update_yaxes(
        title_text=y_title, zeroline=True, zerolinecolor=BASELINE, zerolinewidth=1
    )
    return fig
