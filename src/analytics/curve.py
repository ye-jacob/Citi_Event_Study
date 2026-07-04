"""Mechanical curve-shape math.

The formulas are transcribed verbatim from CLAUDE.md ("Curve, not tenors"):

    level      = 10Y
    slope      = 2s10s (10Y - 2Y), 5s30s (30Y - 5Y)
    curvature  = 2*10Y - 2Y - 30Y

WHICH of these the study reports, and why shape beats raw tenors, is a
human-owned choice (CLAUDE.md "Human owns"); this module is just arithmetic on
a curve DataFrame (date index x tenor columns, percent).
"""

from __future__ import annotations

import pandas as pd

SHAPE_MEASURES = ["level", "slope_2s10s", "slope_5s30s", "curvature"]
REQUIRED_TENORS = ["2Y", "5Y", "10Y", "30Y"]


def _require_tenors(curve: pd.DataFrame, needed: list[str]) -> None:
    missing = [t for t in needed if t not in curve.columns]
    if missing:
        raise KeyError(f"curve is missing tenor columns {missing}")


def level(curve: pd.DataFrame) -> pd.Series:
    """Level proxy: the 10Y yield (percent)."""
    _require_tenors(curve, ["10Y"])
    return curve["10Y"].rename("level")


def slope_2s10s(curve: pd.DataFrame) -> pd.Series:
    """2s10s slope = 10Y - 2Y (percent)."""
    _require_tenors(curve, ["2Y", "10Y"])
    return (curve["10Y"] - curve["2Y"]).rename("slope_2s10s")


def slope_5s30s(curve: pd.DataFrame) -> pd.Series:
    """5s30s slope = 30Y - 5Y (percent)."""
    _require_tenors(curve, ["5Y", "30Y"])
    return (curve["30Y"] - curve["5Y"]).rename("slope_5s30s")


def curvature(curve: pd.DataFrame) -> pd.Series:
    """Butterfly curvature = 2*10Y - 2Y - 30Y (percent)."""
    _require_tenors(curve, ["2Y", "10Y", "30Y"])
    return (2.0 * curve["10Y"] - curve["2Y"] - curve["30Y"]).rename("curvature")


def shape_measures(curve: pd.DataFrame) -> pd.DataFrame:
    """All four shape measures as columns, same index as ``curve`` (percent)."""
    _require_tenors(curve, REQUIRED_TENORS)
    return pd.concat(
        [level(curve), slope_2s10s(curve), slope_5s30s(curve), curvature(curve)],
        axis=1,
    )


def to_bps(x):
    """Percentage points -> basis points."""
    return x * 100.0


def change_between(curve: pd.DataFrame, d0, d1) -> pd.Series:
    """Shape-measure changes from date d0 to d1, in BASIS POINTS.

    Pure lookup — both dates must exist in the index. Picking d0/d1 (the event
    window: which close precedes the release, holiday/weekend alignment) is the
    human-owned window policy in event_study.py.
    """
    measures = shape_measures(curve)
    try:
        pre, post = measures.loc[d0], measures.loc[d1]
    except KeyError as e:
        raise KeyError(
            f"{e.args[0]!r} not in curve index — window/holiday alignment is the "
            "caller's job (see event_study.compute_event_impacts)."
        ) from e
    return to_bps(post - pre).rename("delta_bps")
