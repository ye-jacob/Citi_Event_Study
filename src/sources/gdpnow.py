"""Atlanta Fed GDPNow as a consensus provider for the advance GDP print.

Free and citable: https://www.atlantafed.org/cqer/research/gdpnow
The published tracking workbook's "TrackRecord" sheet has, per quarter:

    col A  quarter being forecast (quarter-END date)
    col B  final GDPNow model forecast before the advance release
    col C  BEA's advance estimate (the first print — used as a cross-check
           against our ALFRED-derived actuals, never as the consensus)
    col D  advance release date

The consensus for each advance GDP release is col B. GDPNow is a model
nowcast, not a survey (SPF is the free survey alternative but is ~2.5 months
stale by release day); the writeup must frame it accordingly. No dispersion ->
consensus_stdev stays None.

WHY GDP STUDY ROWS COME FROM THIS SHEET AND NOT ALFRED: the SAAR series
A191RL1Q225SBEA was only ADDED to FRED on 2014-09-26, so every earlier
quarter's "first vintage" is that day's revised value with a fake release
date — not a first print at all (verified: 20 pre-2014 quarters shared the
identical realtime_start). TrackRecord records the true advance estimate and
release date per quarter, validated equal to our ALFRED prints on all
post-2014 quarters. ``build_releases`` therefore constructs complete Release
rows from this sheet (source "gdpnow_track"), sidestepping ALFRED for GDP.
"""

from __future__ import annotations

from datetime import date, datetime, time
from io import BytesIO
from urllib.request import Request, urlopen

import pandas as pd

from src.sources.base import Release
from src.sources.consensus import ConsensusProvider

TRACKING_WORKBOOK_URL = (
    "https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/"
    "cqer/researchcq/gdpnow/GDPTrackingModelDataAndForecasts.xlsx"
)
SHEET = "TrackRecord"


class GdpNowNowcast(ConsensusProvider):
    source_label = "gdpnow"

    def __init__(self, workbook_bytes: bytes | None = None) -> None:
        """``workbook_bytes`` injects the xlsx in tests (no network)."""
        self._workbook_bytes = workbook_bytes
        self._table: pd.DataFrame | None = None

    def get_consensus(self, indicator: str) -> pd.DataFrame:
        if indicator != "GDP":
            raise ValueError(f"GdpNowNowcast covers ['GDP'], not {indicator!r}")
        if self._table is None:
            self._table = parse_track_record(self._fetch())
        return self._table

    def build_releases(
        self, release_time: time, start: date, end: date
    ) -> list[Release]:
        """Complete GDP Release rows from TrackRecord (see module docstring).

        actual   = BEA advance estimate as recorded by the Atlanta Fed
        previous = the PRIOR quarter's advance estimate (what the market had
                   seen last — correct real-time semantics, no revisions)
        """
        table = self.get_consensus("GDP").dropna(
            subset=["advance_estimate", "release_date"]
        )
        prior_advance = table["advance_estimate"].shift(1)
        out: list[Release] = []
        for ref_period, row in table.iterrows():
            if not (pd.Timestamp(start) <= ref_period <= pd.Timestamp(end)):
                continue
            prev = prior_advance.loc[ref_period]
            out.append(
                Release(
                    indicator="GDP",
                    ref_period=ref_period.date(),
                    release_datetime=datetime.combine(
                        row["release_date"].date(), release_time
                    ),
                    actual=float(row["advance_estimate"]),
                    consensus=float(row["consensus"]),
                    consensus_stdev=None,
                    n_estimates=None,
                    previous=None if pd.isna(prev) else float(prev),
                    is_first_print=True,  # the advance estimate IS the first print
                    source="gdpnow_track",
                )
            )
        return out

    def _fetch(self) -> bytes:
        if self._workbook_bytes is not None:
            return self._workbook_bytes
        req = Request(TRACKING_WORKBOOK_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=120) as resp:
            return resp.read()


def parse_track_record(workbook_bytes: bytes) -> pd.DataFrame:
    """TrackRecord sheet -> frame indexed by ref_period (quarter START date).

    Columns: consensus (final pre-release GDPNow), advance_estimate and
    release_date (kept for validation against the FRED/ALFRED pipeline).
    """
    df = pd.read_excel(
        BytesIO(workbook_bytes), sheet_name=SHEET, engine="openpyxl", header=0
    )
    df = df.iloc[:, :4].copy()
    df.columns = ["quarter_end", "consensus", "advance_estimate", "release_date"]
    df["quarter_end"] = pd.to_datetime(df["quarter_end"], errors="coerce")
    df["consensus"] = pd.to_numeric(df["consensus"], errors="coerce")
    df["advance_estimate"] = pd.to_numeric(df["advance_estimate"], errors="coerce")
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df = df.dropna(subset=["quarter_end", "consensus"])
    # FRED quarterly observations are dated at the quarter START.
    df["ref_period"] = (
        pd.PeriodIndex(df["quarter_end"], freq="Q").start_time
    )
    return (
        df.set_index("ref_period")[["consensus", "advance_estimate", "release_date"]]
        .sort_index()
    )
