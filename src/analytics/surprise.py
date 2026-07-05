"""Surprise construction.

Specification: the author's Methodology (2026-07-04), Sections 2-3. This module
implements it mechanically; interpretation of results stays with the author.

Definitions
-----------
raw surprise          = actual - consensus, in the indicator's units
standardized surprise = raw / sigma_hat(raw), where sigma_hat is the sample
                        stdev (ddof=1) of raw surprises per (indicator,
                        expectation measure). No public source provides
                        forecast dispersion, so the historical-stdev
                        standardization is the operative rule. Surprises are
                        NOT demeaned (Balduzzi et al. convention); the
                        regression intercept absorbs any mean.

Expectation measures (Methodology 3.3), inferred from releases.source:
- "nowcast": Cleveland Fed nowcast rows (…+cleveland_fed) and GDPNow rows
  (gdpnow_track) — the study's consensus.
- "naive":   previous-value rows (…+naive_prev) — the random-walk benchmark.

For the nowcast-vs-naive comparison to measure expectation quality rather than
sample-period differences, naive rows are restricted to the release days that
also exist in the nowcast sample (matched samples; ``match_naive`` to disable).
"""

from __future__ import annotations

import pandas as pd

EXPECTATIONS = ["nowcast", "naive"]


def label_expectation(source: str) -> str | None:
    """Map a releases.source string to its expectation measure (None = neither)."""
    if source.endswith("+naive_prev"):
        return "naive"
    if source.endswith("+cleveland_fed") or source == "gdpnow_track":
        return "nowcast"
    return None


def standardized_surprises(
    releases: pd.DataFrame, match_naive: bool = True
) -> pd.DataFrame:
    """Standardized surprises per release under both expectation measures.

    Input columns: indicator, ref_period, release_datetime, actual, consensus,
    source. Output: indicator, ref_period, release_datetime, expectation,
    surprise_raw, surprise_z — one row per (release, expectation measure).
    """
    df = releases.dropna(subset=["actual", "consensus"]).copy()
    df["expectation"] = df["source"].map(label_expectation)
    df = df.dropna(subset=["expectation"])

    if match_naive:
        nowcast_keys = set(
            map(
                tuple,
                df.loc[
                    df["expectation"] == "nowcast", ["indicator", "ref_period"]
                ].itertuples(index=False),
            )
        )
        keep = df.apply(
            lambda r: r["expectation"] == "nowcast"
            or (r["indicator"], r["ref_period"]) in nowcast_keys,
            axis=1,
        )
        df = df[keep]

    df["surprise_raw"] = df["actual"] - df["consensus"]
    sigma = df.groupby(["indicator", "expectation"])["surprise_raw"].transform(
        lambda s: s.std(ddof=1)
    )
    df["surprise_z"] = df["surprise_raw"] / sigma

    out = df[
        [
            "indicator",
            "ref_period",
            "release_datetime",
            "expectation",
            "surprise_raw",
            "surprise_z",
        ]
    ].reset_index(drop=True)
    return out.sort_values(["indicator", "expectation", "ref_period"]).reset_index(
        drop=True
    )


def fomc_surprise(meetings: pd.DataFrame, futures: pd.DataFrame) -> pd.Series:
    """The UNEXPECTED component of an FOMC decision — NOT the raw target change.

    Still human-owned and out of the current study (Methodology covers CPI,
    PCE, GDP only). Options if ever added: Kuttner (2001) scaled fed-funds-
    futures move (needs CME data, not on FRED); OIS-based alternatives;
    CME FedWatch-style implied probabilities (public page, no clean history).
    """
    raise NotImplementedError(
        "TODO(human): futures-based FOMC surprise is out of the study scope "
        "and needs futures data the repo doesn't ship."
    )
