"""Event-study econometrics.

Specification: the author's Methodology (2026-07-04), Sections 3.1-3.4,
implemented mechanically. All regressions are per indicator x curve factor,
never pooled, with White heteroskedasticity-robust standard errors (HC1
finite-sample variant). Curve factors are in percentage points upstream;
everything here reports BASIS POINTS per one standard deviation of surprise.

3.1 Baseline      dF(d) = a + b*S(d) + e            -> fit_baseline
3.2 Asymmetry     dF(d) = a + b+*S+ + b-*S- + e     -> fit_asymmetric
3.3 Nowcast/naive baseline under both expectation measures (same fit_baseline;
    the surprise table carries both, matched samples)
3.4 Event study   CARs around top/bottom-decile surprises vs the mean
    release-day change on control (non-extreme) releases -> event_study_cars

Window: dF(d) = F(d) - F(d-1) in trading days. A release date that is not a
trading day maps to the first close on/after it; the pre date is the last
close strictly before it. Rows whose window straddles more than ``max_gap``
calendar days on either side are dropped (long holiday gaps).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.analytics.curve import SHAPE_MEASURES, shape_measures, to_bps

FACTORS = list(SHAPE_MEASURES)  # level, slope_2s10s, slope_5s30s, curvature
COV_TYPE = "HC1"  # White (1980) heteroskedasticity-robust, finite-sample variant


# ------------------------------------------------------------- observations


def release_day_changes(
    surprises: pd.DataFrame, curve: pd.DataFrame, max_gap: int = 5
) -> pd.DataFrame:
    """Attach the release-window factor changes (bps) to each surprise row.

    ``surprises`` is standardized_surprises() output; ``curve`` is the tenor
    frame (percent). Output adds one delta_<factor> column per shape measure.
    """
    measures = shape_measures(curve).dropna()
    idx = measures.index

    dates = pd.to_datetime(surprises["release_datetime"]).dt.normalize()
    windows: dict[pd.Timestamp, pd.Series | None] = {}
    for d in dates.unique():
        pos = idx.searchsorted(d)
        if pos <= 0 or pos >= len(idx):
            windows[d] = None
            continue
        d1, d0 = idx[pos], idx[pos - 1]
        if (d1 - d).days > max_gap or (d - d0).days > max_gap:
            windows[d] = None
            continue
        windows[d] = to_bps(measures.loc[d1] - measures.loc[d0])

    out = surprises.copy()
    out["release_date"] = dates
    for factor in FACTORS:
        out[f"delta_{factor}"] = [
            None if windows[d] is None else float(windows[d][factor])
            for d in dates
        ]
    n_before = len(out)
    out = out.dropna(subset=[f"delta_{f}" for f in FACTORS]).reset_index(drop=True)
    out.attrs["dropped_no_window"] = n_before - len(out)
    return out


# -------------------------------------------------------------- estimation


def _ols(y: pd.Series, X: pd.DataFrame):
    return sm.OLS(y.astype(float), X.astype(float)).fit(cov_type=COV_TYPE)


def fit_baseline(obs: pd.DataFrame) -> pd.DataFrame:
    """Methodology 3.1/3.3: dF = a + b*S per (indicator, expectation, factor)."""
    rows = []
    for (indicator, expectation), g in obs.groupby(["indicator", "expectation"]):
        X = pd.DataFrame({"const": 1.0, "surprise": g["surprise_z"]})
        for factor in FACTORS:
            res = _ols(g[f"delta_{factor}"], X)
            ci = res.conf_int().loc["surprise"]
            rows.append(
                {
                    "indicator": indicator,
                    "expectation": expectation,
                    "factor": factor,
                    "n": int(res.nobs),
                    "beta": res.params["surprise"],
                    "se": res.bse["surprise"],
                    "t": res.tvalues["surprise"],
                    "p": res.pvalues["surprise"],
                    "ci_low": ci[0],
                    "ci_high": ci[1],
                    "alpha": res.params["const"],
                    "r2": res.rsquared,
                }
            )
    return pd.DataFrame(rows)


def fit_asymmetric(obs: pd.DataFrame, expectation: str = "nowcast") -> pd.DataFrame:
    """Methodology 3.2: dF = a + b+*max(S,0) + b-*min(S,0), per indicator x factor.

    ``p_equal`` is the robust Wald p-value of H0: b+ = b-.
    """
    rows = []
    sample = obs[obs["expectation"] == expectation]
    for indicator, g in sample.groupby("indicator"):
        X = pd.DataFrame(
            {
                "const": 1.0,
                "s_pos": g["surprise_z"].clip(lower=0.0),
                "s_neg": g["surprise_z"].clip(upper=0.0),
            }
        )
        for factor in FACTORS:
            res = _ols(g[f"delta_{factor}"], X)
            ci = res.conf_int()
            rows.append(
                {
                    "indicator": indicator,
                    "expectation": expectation,
                    "factor": factor,
                    "n": int(res.nobs),
                    "beta_pos": res.params["s_pos"],
                    "se_pos": res.bse["s_pos"],
                    "ci_pos_low": ci.loc["s_pos", 0],
                    "ci_pos_high": ci.loc["s_pos", 1],
                    "beta_neg": res.params["s_neg"],
                    "se_neg": res.bse["s_neg"],
                    "ci_neg_low": ci.loc["s_neg", 0],
                    "ci_neg_high": ci.loc["s_neg", 1],
                    "p_equal": float(res.f_test("s_pos = s_neg").pvalue),
                    "r2": res.rsquared,
                }
            )
    return pd.DataFrame(rows)


def event_study_cars(
    obs: pd.DataFrame,
    curve: pd.DataFrame,
    expectation: str = "nowcast",
    pre: int = 5,
    post: int = 10,
    decile: float = 0.10,
) -> pd.DataFrame:
    """Methodology 3.4: mean CAR paths around extreme-surprise releases.

    Surprise days: top/bottom ``decile`` of surprise_z per indicator ("hot" /
    "cold"). Control days: the remaining releases; the benchmark is their mean
    release-day change per factor. Abnormal change on each relative trading
    day tau in [-pre, +post] is the realized daily change minus that constant;
    CARs cumulate from tau=-pre. Events too close to the sample edge for the
    full window are dropped (n_events reports what remains).
    """
    measures = shape_measures(curve).dropna()
    daily = to_bps(measures.diff()).dropna()
    idx = daily.index

    sample = obs[obs["expectation"] == expectation]
    rows = []
    for indicator, g in sample.groupby("indicator"):
        hi = g["surprise_z"].quantile(1.0 - decile)
        lo = g["surprise_z"].quantile(decile)
        groups = {
            "hot": g[g["surprise_z"] >= hi],
            "cold": g[g["surprise_z"] <= lo],
        }
        control = g[(g["surprise_z"] > lo) & (g["surprise_z"] < hi)]
        control_mean = {f: control[f"delta_{f}"].mean() for f in FACTORS}

        for group_name, events in groups.items():
            paths: dict[str, list[np.ndarray]] = {f: [] for f in FACTORS}
            for d in pd.to_datetime(events["release_date"]):
                pos = idx.searchsorted(d)  # day 0: first close on/after release
                if pos - pre < 0 or pos + post >= len(idx):
                    continue
                window = daily.iloc[pos - pre : pos + post + 1]
                for f in FACTORS:
                    paths[f].append(window[f].to_numpy() - control_mean[f])
            n_events = len(paths[FACTORS[0]])
            if n_events == 0:
                continue
            taus = np.arange(-pre, post + 1)
            for f in FACTORS:
                car = np.cumsum(np.mean(paths[f], axis=0))
                for tau, value in zip(taus, car):
                    rows.append(
                        {
                            "indicator": indicator,
                            "expectation": expectation,
                            "factor": f,
                            "group": group_name,
                            "tau": int(tau),
                            "car": float(value),
                            "n_events": n_events,
                        }
                    )
    return pd.DataFrame(rows)
