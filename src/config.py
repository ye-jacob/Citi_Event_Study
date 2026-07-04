"""Project configuration: paths, timezone, FRED series maps, indicator registry.

The indicator registry rows are STARTING POINTS transcribed from CLAUDE.md — the
human verifies each one (seasonal adjustment, headline vs core, and that the
transform matches the exact number consensus is quoted against) before trusting
any surprise built on top of it.
"""

from __future__ import annotations

import os
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "event_study.db"
FINDINGS_PATH = PROJECT_ROOT / "analysis" / "findings.md"

# All release timestamps are stored as ET-naive datetimes (CLAUDE.md "Timestamps").
ET = ZoneInfo("America/New_York")

FRED_API_KEY_ENV = "FRED_API_KEY"


def get_fred_api_key() -> str:
    """Read the FRED API key from the environment, with a helpful error."""
    key = os.environ.get(FRED_API_KEY_ENV, "").strip()
    if not key:
        raise RuntimeError(
            f"{FRED_API_KEY_ENV} is not set. Get a free key at "
            "https://fred.stlouisfed.org/docs/api/api_key.html and run "
            f"`export {FRED_API_KEY_ENV}=...` before ingesting."
        )
    return key


# Treasury constant-maturity series (H.15). Percent, daily close, NaN on holidays.
TENOR_FRED_SERIES: dict[str, str] = {
    "3M": "DGS3MO",
    "1Y": "DGS1",
    "2Y": "DGS2",
    "5Y": "DGS5",
    "7Y": "DGS7",
    "10Y": "DGS10",
    "20Y": "DGS20",
    "30Y": "DGS30",
}

# The tenors the level/slope/curvature decomposition needs.
CORE_TENORS: list[str] = ["2Y", "5Y", "10Y", "30Y"]

# How to turn the raw FRED series into the number the market quotes vs consensus:
#   "none"        use the published value as-is        (UNRATE %, GDP SAAR %, ICSA)
#   "diff"        period-over-period change in level   (NFP: change in PAYEMS)
#   "pct_change"  period-over-period % change          (CPI MoM %)
VALID_TRANSFORMS = {"none", "diff", "pct_change"}

# ---------------------------------------------------------------------------
# Indicator registry (starting points — TODO(human): verify every row before
# trusting surprises built on it; see the table + gotchas in CLAUDE.md).
#
# yield_sign: +1 if a positive surprise generally pushes yields UP (CPI, PCE,
# NFP, GDP, retail, ISM), -1 if DOWN (unemployment rate, jobless claims).
# ---------------------------------------------------------------------------
INDICATORS: list[dict] = [
    {
        "key": "FOMC",
        "name": "FOMC / Fed Funds target",
        "freq": "8x/yr",
        "fred_series": "DFEDTARU",
        "yield_sign": 1,
        "release_time": time(14, 0),
        "transform": "none",
        "units": "% (target upper bound)",
        "active": False,  # TODO(human): the surprise is the UNEXPECTED component
        # vs fed-funds futures (Kuttner), NOT the raw target change. Needs futures
        # data that is not on FRED. Activate only once analytics/surprise.py's
        # fomc_surprise() is implemented by the human.
        "notes": "Surprise != level change; futures-based construction is human-owned.",
    },
    {
        "key": "CPI",
        "name": "CPI (headline, SA)",
        "freq": "monthly",
        "fred_series": "CPIAUCSL",
        "yield_sign": 1,
        "release_time": time(8, 30),
        "transform": "pct_change",
        "units": "% m/m",
        "active": True,
        "notes": "TODO(human): verify MoM headline is the consensus-quoted number; "
        "core alternative: CPILFESL. YoY is also quoted.",
    },
    {
        "key": "PCE",
        "name": "PCE price index (headline)",
        "freq": "monthly",
        "fred_series": "PCEPI",
        "yield_sign": 1,
        "release_time": time(8, 30),
        "transform": "pct_change",
        "units": "% m/m",
        "active": True,
        "notes": "TODO(human): core PCEPILFE is the Fed's target — decide which "
        "series the study uses.",
    },
    {
        "key": "NFP",
        "name": "Nonfarm Payrolls",
        "freq": "monthly",
        "fred_series": "PAYEMS",
        "yield_sign": 1,
        "release_time": time(8, 30),
        "transform": "diff",
        "units": "k (change in level)",
        "active": True,
        "notes": "Released value is the MoM change in the level. Co-released with "
        "UNRATE (entangled impacts — CLAUDE.md gotcha).",
    },
    {
        "key": "UNRATE",
        "name": "Unemployment Rate",
        "freq": "monthly",
        "fred_series": "UNRATE",
        "yield_sign": -1,
        "release_time": time(8, 30),
        "transform": "none",
        "units": "%",
        "active": True,
        "notes": "Co-released with NFP — don't attribute the whole move to one.",
    },
    {
        "key": "RETAIL",
        "name": "Retail Sales (advance)",
        "freq": "monthly",
        "fred_series": "RSAFS",
        "yield_sign": 1,
        "release_time": time(8, 30),
        "transform": "pct_change",
        "units": "% m/m",
        "active": True,
        "notes": "TODO(human): verify headline vs ex-auto (RSXFS) against consensus.",
    },
    {
        "key": "GDP",
        "name": "Real GDP (SAAR, q/q)",
        "freq": "quarterly",
        "fred_series": "A191RL1Q225SBEA",
        "yield_sign": 1,
        "release_time": time(8, 30),
        "transform": "none",  # series is already the published SAAR % change
        "units": "% q/q saar",
        "active": True,
        "notes": "First print = advance estimate; 2nd/3rd are revisions. Level "
        "alternative: GDPC1. TODO(human): verify.",
    },
    {
        "key": "ISM_MFG",
        "name": "ISM Manufacturing PMI",
        "freq": "monthly",
        "fred_series": None,
        "yield_sign": 1,
        "release_time": time(10, 0),
        "transform": "none",
        "units": "index",
        "active": False,  # ISM licensing — not cleanly on FRED (CLAUDE.md gotcha)
        "notes": "TODO(human): verify sourcing. S&P Global (Markit) PMI is a "
        "DIFFERENT series — do not splice with ISM history.",
    },
    {
        "key": "ISM_SRV",
        "name": "ISM Services PMI",
        "freq": "monthly",
        "fred_series": None,
        "yield_sign": 1,
        "release_time": time(10, 0),
        "transform": "none",
        "units": "index",
        "active": False,
        "notes": "Same licensing situation as ISM_MFG.",
    },
    {
        "key": "CLAIMS",
        "name": "Initial Jobless Claims",
        "freq": "weekly",
        "fred_series": "ICSA",
        "yield_sign": -1,
        "release_time": time(8, 30),
        "transform": "none",
        "units": "persons",
        "active": True,
        "notes": "FRED level is persons; consensus is quoted in thousands. "
        "TODO(human): verify units line up before computing surprises.",
    },
]


def indicators_by_key() -> dict[str, dict]:
    return {row["key"]: row for row in INDICATORS}


def active_indicator_keys() -> list[str]:
    return [row["key"] for row in INDICATORS if row["active"]]
