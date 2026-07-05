"""Trading-oriented tests on top of the event study.

Three questions a desk would actually ask, each answerable with daily closes:

1. gap_signal_stats — is the PUBLIC pre-release information priced? The
   Cleveland/GDPNow nowcast is public before the print, so
   gap = nowcast − previous print is knowable at the prior close. Regress the
   release-day factor change on the standardized gap and score the naive rule
   "position in the direction of the gap at t−1 close, exit at t close":
   hit rate, mean bps per trade, and a t-stat on that mean. Entering at the
   prior close is exactly what daily data can account for honestly (unlike
   post-print reaction trades, which happen in seconds).

2. event_day_vol — are release days high-volatility days for the curve at
   all? Compares the stdev and mean |move| of each factor on an indicator's
   release days vs all non-release trading days. This is the own-gamma-into-
   the-event question and needs no consensus.

3. era_split — is the response concentrated in the post-2021 inflation era?
   Re-runs the baseline per era. A beta that lives in one regime is a sizing
   statement, not a constant of nature.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.event_study import FACTORS, fit_baseline, release_day_changes
from src.analytics.surprise import label_expectation


# ------------------------------------------------------- 1. ex-ante gap test


def build_gap_frame(releases: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    """Per nowcast-backed release: standardized public gap + factor changes.

    ``releases`` needs indicator, ref_period, release_datetime, consensus,
    previous, source. gap = consensus − previous, standardized per indicator
    (full-sample stdev, ddof=1 — disclosed as mild look-ahead; the sign, which
    drives the trade rule, needs no scaling).
    """
    df = releases.copy()
    df["expectation"] = df["source"].map(label_expectation)
    df = df[df["expectation"] == "nowcast"].dropna(subset=["consensus", "previous"])
    df["gap_raw"] = df["consensus"] - df["previous"]
    sigma = df.groupby("indicator")["gap_raw"].transform(lambda s: s.std(ddof=1))
    df["gap_z"] = df["gap_raw"] / sigma
    frame = df[
        ["indicator", "ref_period", "release_datetime", "expectation", "gap_z"]
    ].copy()
    return release_day_changes(frame, curve)


def gap_signal_stats(gap_obs: pd.DataFrame) -> pd.DataFrame:
    """Score the gap signal per (indicator, factor).

    hit_rate    share of releases where sign(ΔF) == sign(gap)
    mean_pnl    mean of ΔF·sign(gap), bps per release (gross, no costs)
    t_pnl       t-stat of that mean
    gamma       OLS slope of ΔF on gap_z (bps per 1σ of gap), HC1 errors
    """
    import statsmodels.api as sm

    rows = []
    for indicator, g in gap_obs.groupby("indicator"):
        g = g[g["gap_z"] != 0]
        X = pd.DataFrame({"const": 1.0, "gap": g["gap_z"]})
        for factor in FACTORS:
            y = g[f"delta_{factor}"].astype(float)
            res = sm.OLS(y, X.astype(float)).fit(cov_type="HC1")
            pnl = y.to_numpy() * np.sign(g["gap_z"].to_numpy())
            n = len(pnl)
            mean_pnl = float(pnl.mean())
            t_pnl = float(mean_pnl / (pnl.std(ddof=1) / np.sqrt(n))) if n > 1 else np.nan
            rows.append(
                {
                    "indicator": indicator,
                    "factor": factor,
                    "n": n,
                    "hit_rate": float((np.sign(y) == np.sign(g["gap_z"])).mean()),
                    "mean_pnl": mean_pnl,
                    "t_pnl": t_pnl,
                    "gamma": res.params["gap"],
                    "gamma_se": res.bse["gap"],
                    "gamma_p": res.pvalues["gap"],
                }
            )
    return pd.DataFrame(rows)


# ------------------------------------------------- 2. event-day vol premium


def event_day_vol(
    release_dates: pd.DataFrame, curve: pd.DataFrame
) -> pd.DataFrame:
    """Factor volatility on each indicator's release days vs non-release days.

    ``release_dates``: columns indicator, release_datetime. Day 0 is the first
    close on/after the release. Control days exclude EVERY indicator's day-0s
    so a CPI control day is never someone else's release day.
    """
    from src.analytics.curve import shape_measures, to_bps

    daily = to_bps(shape_measures(curve).dropna().diff()).dropna()
    idx = daily.index

    day0: dict[str, set] = {}
    for indicator, g in release_dates.groupby("indicator"):
        dates = pd.to_datetime(g["release_datetime"]).dt.normalize().unique()
        positions = [idx.searchsorted(d) for d in dates]
        day0[indicator] = {idx[p] for p in positions if 0 < p < len(idx)}
    all_event_days = set().union(*day0.values()) if day0 else set()
    control = daily.loc[~daily.index.isin(all_event_days)]

    rows = []
    for indicator, days in day0.items():
        event = daily.loc[daily.index.isin(days)]
        for factor in FACTORS:
            rows.append(
                {
                    "indicator": indicator,
                    "factor": factor,
                    "n_event": len(event),
                    "n_control": len(control),
                    "sd_event": float(event[factor].std(ddof=1)),
                    "sd_control": float(control[factor].std(ddof=1)),
                    "vol_ratio": float(
                        event[factor].std(ddof=1) / control[factor].std(ddof=1)
                    ),
                    "mean_abs_event": float(event[factor].abs().mean()),
                    "mean_abs_control": float(control[factor].abs().mean()),
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------- 3. era conditioning


def era_split(obs: pd.DataFrame, cutoff: str = "2021-01-01") -> pd.DataFrame:
    """Baseline betas re-estimated pre/post ``cutoff`` (nowcast expectation)."""
    sample = obs[obs["expectation"] == "nowcast"].copy()
    when = pd.to_datetime(sample["release_date"])
    out = []
    for era, mask in [
        (f"pre_{cutoff[:4]}", when < pd.Timestamp(cutoff)),
        (f"post_{cutoff[:4]}", when >= pd.Timestamp(cutoff)),
    ]:
        part = sample[mask]
        if part.empty:
            continue
        fitted = fit_baseline(part)
        fitted["era"] = era
        out.append(fitted)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()
