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
    "6M": "DGS6MO",
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

# What the ingest actually pulls: the decomposition tenors plus the front end
# (bills/1Y) for money-market-adjacent exploration. Extra tenors never change
# the analytics — the factors are defined on CORE_TENORS only.
CURVE_TENORS: list[str] = ["3M", "6M", "1Y"] + CORE_TENORS

# How to turn the raw FRED series into the number the market quotes vs consensus:
#   "none"        use the published value as-is        (UNRATE %, GDP SAAR %, ICSA)
#   "diff"        period-over-period change in level   (NFP: change in PAYEMS)
#   "pct_change"  period-over-period % change          (CPI MoM %)
VALID_TRANSFORMS = {"none", "diff", "pct_change"}

# Programmatic public consensus providers (see src/sources/):
#   "cleveland_fed" -> Cleveland Fed inflation nowcast (CPI/PCE MoM, 2013-07+)
#   "gdpnow"        -> Atlanta Fed GDPNow final pre-release forecast (~2011+)
# None -> naive baseline only. Manual CSVs (ConsensusCsvSource) are imported
# ad hoc, not wired through the registry.
CONSENSUS_PROVIDERS = {"cleveland_fed", "gdpnow"}

# ---------------------------------------------------------------------------
# Indicator registry (starting points — TODO(human): verify every row before
# trusting surprises built on it; see the table + gotchas in CLAUDE.md).
#
# yield_sign: +1 if a positive surprise generally pushes yields UP (CPI, PCE,
# NFP, GDP, retail, ISM), -1 if DOWN (unemployment rate, jobless claims).
#
# STUDY SCOPE (2026-07, Bloomberg access lost): only indicators with a
# ToS-clean public consensus source stay active — CPI, PCE, GDP. NFP, UNRATE,
# RETAIL and CLAIMS are deactivated: their per-release survey consensus exists
# only behind vendors or scraping-prohibited calendar sites. Revive any of
# them via ConsensusCsvSource with hand-collected public figures.
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
        "consensus": None,
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
        "consensus": "cleveland_fed",  # model nowcast, daily, cut pre-release
        "active": True,
        "notes": "TODO(human): verify MoM headline is the consensus-quoted number; "
        "core alternative: CPILFESL (Cleveland feed has core too). YoY also quoted.",
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
        "consensus": "cleveland_fed",
        "active": True,
        "notes": "TODO(human): core PCEPILFE is the Fed's target — decide which "
        "series the study uses (Cleveland feed has core too).",
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
        "consensus": None,
        "active": False,  # removed from study: no public per-release consensus
        "notes": "REMOVED 2026-07 (no ToS-clean public consensus archive; "
        "vendor/scrape only). Revive via ConsensusCsvSource. Released value is "
        "the MoM change in level; co-released with UNRATE (entangled impacts).",
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
        "consensus": None,
        "active": False,  # removed from study: no public per-release consensus
        "notes": "REMOVED 2026-07 (no ToS-clean public consensus archive). "
        "Revive via ConsensusCsvSource. Co-released with NFP.",
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
        "consensus": None,
        "active": False,  # removed from study: no public per-release consensus
        "notes": "REMOVED 2026-07 (no ToS-clean public consensus archive). "
        "Revive via ConsensusCsvSource; ex-auto alt RSXFS.",
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
        "consensus": "gdpnow",  # final pre-release GDPNow model forecast
        "active": True,
        "notes": "Study rows (source=gdpnow_track) come from the Atlanta Fed "
        "track record: A191RL1Q225SBEA has NO real ALFRED vintages before "
        "2014-09-26 (fake first prints). Naive-baseline rows before then carry "
        "that defect — do not use them for surprises. SPF is the free survey "
        "alternative (staler). TODO(human): verify.",
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
        "consensus": None,
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
        "consensus": None,
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
        "consensus": None,
        "active": False,  # removed from study: no public per-release consensus
        "notes": "REMOVED 2026-07 (no ToS-clean public consensus archive). "
        "Revive via ConsensusCsvSource; mind persons-vs-thousands units.",
    },
]


def indicators_by_key() -> dict[str, dict]:
    return {row["key"]: row for row in INDICATORS}


def active_indicator_keys() -> list[str]:
    return [row["key"] for row in INDICATORS if row["active"]]
