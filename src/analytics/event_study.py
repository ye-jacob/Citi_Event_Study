"""Event study core — HUMAN-OWNED (CLAUDE.md "Human owns").

Everything here is a stub on purpose: the event-window definition, the curve
decomposition choice, regime classification, and the regression spec are the
analytical judgments this project exists to demonstrate. Claude Code provides
the surrounding plumbing (curve math in analytics/curve.py, EventImpact schema,
data access) and stops.

--------------------------------------------------------------------------
Decision notes (options + tradeoffs; the human picks)
--------------------------------------------------------------------------

EVENT WINDOW — free H.15 data is DAILY CLOSE, so with 08:30 ET releases:
  (a) close(t-1) -> close(t): tightest free window; the release is inside it,
      but so is everything else that day (label e.g. "tm1c_t0c").
  (b) close(t-1) -> close(t+1): catches slow digestion, doubles contamination.
  (c) Intraday futures around the timestamp: the clean answer, not free —
      candidate future work. ISM at 10:00 and FOMC at 14:00 still sit inside
      the daily window; only the label/interpretation changes.
  Also decide holiday alignment: "previous close" = previous TRADING day
  (curve.change_between refuses to guess).

CO-RELEASES — NFP + UNRATE share one 08:30 timestamp; their impacts are
  entangled. Options: joint regression, headline-only attribution, or dropping
  the smaller signal. Don't double-count one move in two single-indicator betas.

REGIME — hiking / cutting / hold. Options: direction of the last target change
  within N months (DFEDTARU diff), or market-implied. Boundary meetings (first
  cut after a hiking cycle) dominate the interesting variation — rule matters.

REGRESSION — delta_shape ~ beta * z_surprise per indicator:
  OLS with HAC (Newey-West) vs plain; regime split vs interaction term; pooled
  multi-indicator with yield_sign applied vs per-indicator. Small samples:
  report n and CIs for every beta (limitations section promise).
"""

from __future__ import annotations

import pandas as pd


def classify_regime(curve_or_policy: pd.DataFrame) -> pd.Series:
    """Label each date hiking / cutting / hold.

    Returns a date-indexed Series of {"hiking", "cutting", "hold"}.
    """
    raise NotImplementedError(
        "TODO(human): regime rule is an analytical choice — see module "
        "docstring (last-move direction vs market-implied, lookback length)."
    )


def compute_event_impacts(
    releases: pd.DataFrame, curve: pd.DataFrame, window_label: str
) -> pd.DataFrame:
    """Per release: pre/post yields + level/slope/curvature deltas (bps).

    Should return rows matching the event_impacts schema (models.EventImpact),
    using analytics.curve.change_between once the window policy picks the
    pre/post dates for each release_datetime.
    """
    raise NotImplementedError(
        "TODO(human): the window definition is human-owned — options (a)/(b)/(c) "
        "in the module docstring. Plumbing ready: curve.change_between + "
        "models.EventImpact."
    )


def estimate_surprise_betas(
    impacts: pd.DataFrame,
    surprises: pd.DataFrame,
    by_regime: bool = False,
) -> pd.DataFrame:
    """Surprise betas: OLS of curve-shape change on standardized surprise.

    Expected output shape (feeds charts.fig_beta_bars and the writeup):
    one row per (indicator, shape_measure[, regime]) with beta, stderr, ci_low,
    ci_high, n_obs.
    """
    raise NotImplementedError(
        "TODO(human): the regression specification and its interpretation are "
        "human-owned — see module docstring (HAC errors, regime interaction, "
        "co-release handling)."
    )
