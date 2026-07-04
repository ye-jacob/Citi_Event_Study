"""Surprise construction — HUMAN-OWNED (CLAUDE.md "Human owns").

Claude Code scaffolds signatures and lays out the options; the human makes the
calls and writes the math, or the piece can't be defended in an interview.

Definitions the implementations must satisfy (CLAUDE.md "Domain concepts"):

    raw surprise           = actual - consensus
    standardized surprise  = raw / forecast_dispersion   (z, comparable across
                             indicators; fall back to historical stdev of the
                             raw surprise when dispersion is unavailable)

Decisions to make BEFORE implementing (each shifts results):

1. Vintage — which value is "the actual"?
   The market was surprised relative to the FIRST print; revised values corrupt
   historical surprises. Plumbing supports both: FredDataSource(vintage="first")
   uses ALFRED first prints and rows carry is_first_print. The naive proxy's
   "previous" also inherits the chosen vintage. Decide and document.

2. Dispersion fallback — naive-proxy rows have consensus_stdev=None.
   Historical stdev of raw surprises: full-sample (stable, peeks into the
   future) vs rolling/expanding (real-time honest, noisy early). Winsorize
   outliers or not?

3. Sign convention — apply the per-indicator yield_sign here (so +1 always
   means "hawkish for yields") or keep surprises in data units and apply signs
   only when aggregating? Pick one, apply everywhere.

4. Precision — consensus is quoted at published precision (CPI 0.1pp). Compare
   against the rounded print or full-precision FRED values?
"""

from __future__ import annotations

import pandas as pd


def compute_raw_surprise(releases: pd.DataFrame) -> pd.Series:
    """Raw surprise per release: actual - consensus, in the indicator's units.

    Expects columns: actual, consensus. Rows lacking either stay NaN.
    """
    raise NotImplementedError(
        "TODO(human): surprise construction is human-owned — see module "
        "docstring for the decisions (vintage, precision) to make first."
    )


def compute_standardized_surprise(
    releases: pd.DataFrame, dispersion_fallback: str | None = None
) -> pd.Series:
    """Standardized surprise z = raw / dispersion, comparable across indicators.

    Must handle consensus_stdev=None rows via the chosen historical-stdev
    fallback (decision #2 in the module docstring).
    """
    raise NotImplementedError(
        "TODO(human): dispersion fallback + winsorization are analytical "
        "choices — see module docstring."
    )


def fomc_surprise(meetings: pd.DataFrame, futures: pd.DataFrame) -> pd.Series:
    """The UNEXPECTED component of an FOMC decision — NOT the raw target change.

    Options (human picks and defends):
    - Kuttner (2001): scaled change in the current-month fed funds future on
      decision day: surprise = (D/(D-t)) * Δff1, with month-end scaling caveats
      and unscheduled-meeting handling. Needs CME FF futures (not on FRED).
    - OIS-based: change in the meeting-dated OIS rate — cleaner post-2008 but a
      different data acquisition problem.
    - CME FedWatch-style implied probabilities (public page, no clean history).

    The FOMC indicator stays active=False in the registry until this exists.
    """
    raise NotImplementedError(
        "TODO(human): futures-based FOMC surprise is human-owned (CLAUDE.md "
        "gotcha #2) and needs futures data the repo doesn't ship."
    )
