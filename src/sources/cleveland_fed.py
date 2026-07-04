"""Cleveland Fed inflation nowcast as a consensus provider (CPI & PCE MoM).

Free and citable: https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting
The page's chart feed (nowcast_month.json) contains, for every month since
2013-07, the DAILY evolution of the CPI / core CPI / PCE / core PCE MoM
nowcasts, release-day marker labels (a category labeled "CPI Jul" instead of a
date — own-month PCE markers only exist in the pre-2014 chart format), and
"Actual ..." series that begin at the release. The consensus is the LAST
nowcast value at a column strictly BEFORE the release cutoff, where the cutoff
is the own-month marker or the first "Actual" value, whichever comes first
(verified on the live feed: the nowcast series itself stops pre-release, e.g.
month charts end days before the PCE print). Index-based, so no fragile date
parsing and no post-release information can leak in.

Known properties (documented for the methodology section):
- Model nowcast, not a survey median; accuracy on headline CPI is competitive
  with surveys (see Cleveland Fed's own comparisons), but it is a different
  object — the writeup must say so.
- No forecast dispersion -> consensus_stdev is always None here.
- Coverage starts 2013-07 (and the first weeks are partial), so provider-backed
  CPI/PCE samples begin ~2013 even though naive-baseline rows go back to 2000.
"""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

import pandas as pd

from src.sources.consensus import ConsensusProvider

NOWCAST_MONTH_URL = (
    "https://www.clevelandfed.org/-/media/files/webcharts/"
    "inflationnowcasting/nowcast_month.json"
)

# chart seriesname -> registry indicator key
SERIES_FOR_INDICATOR = {
    "CPI": "CPI Inflation",
    "PCE": "PCE Inflation",
    # Core series exist in the feed ("Core CPI Inflation", "Core PCE
    # Inflation") if the human adds core indicators to the registry later.
}

_MONTH_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


class ClevelandFedNowcast(ConsensusProvider):
    source_label = "cleveland_fed"

    def __init__(self, raw: list | None = None) -> None:
        """``raw`` injects the parsed JSON payload in tests (no network)."""
        self._raw = raw
        self._tables: dict[str, pd.DataFrame] | None = None

    def get_consensus(self, indicator: str) -> pd.DataFrame:
        if indicator not in SERIES_FOR_INDICATOR:
            raise ValueError(
                f"ClevelandFedNowcast covers {sorted(SERIES_FOR_INDICATOR)}, "
                f"not {indicator!r}"
            )
        if self._tables is None:
            self._tables = parse_month_charts(self._fetch())
        return self._tables[indicator]

    def _fetch(self) -> list:
        if self._raw is not None:
            return self._raw
        req = Request(NOWCAST_MONTH_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))


def parse_month_charts(raw: list) -> dict[str, pd.DataFrame]:
    """Per indicator: ref_period-indexed frame of last-nowcast-before-release.

    Each chart in ``raw`` describes one reference month (subcaption "YYYY-M").
    The release cutoff per indicator is the earliest of: its own-month marker
    label ("CPI Jul"), or the first non-empty "Actual <series>" value. The
    consensus is the last non-empty nowcast value strictly before that cutoff;
    with no cutoff present the series tail is used (the feed's nowcast series
    end before the release — months FRED hasn't published yet simply never
    match a release row in the overlay).
    """
    rows: dict[str, list[tuple[pd.Timestamp, float]]] = {
        key: [] for key in SERIES_FOR_INDICATOR
    }
    for chart in raw:
        sub = str(chart.get("chart", {}).get("subcaption", ""))
        try:
            year_s, month_s = sub.split("-")
            year, month = int(year_s), int(month_s)
        except ValueError:
            continue
        try:
            cats = chart["categories"][0]["category"]
        except (KeyError, IndexError):
            continue
        labels = [str(c.get("label", "")) for c in cats]
        series = {
            d.get("seriesname"): d.get("data", [])
            for d in chart.get("dataset", [])
        }
        for key, seriesname in SERIES_FOR_INDICATOR.items():
            data = series.get(seriesname, [])
            cutoffs = [len(data)]
            marker = f"{key} {_MONTH_ABBR[month]}"
            if marker in labels:
                cutoffs.append(labels.index(marker))
            first_actual = _first_value_index(series.get(f"Actual {seriesname}", []))
            if first_actual is not None:
                cutoffs.append(first_actual)
            value = _last_value_before(data, min(cutoffs))
            if value is not None:
                rows[key].append((pd.Timestamp(year, month, 1), value))

    tables: dict[str, pd.DataFrame] = {}
    for key, pairs in rows.items():
        df = pd.DataFrame(pairs, columns=["ref_period", "consensus"])
        tables[key] = df.set_index("ref_period").sort_index()
    return tables


def _entry_value(entry) -> str | None:
    value = entry.get("value") if isinstance(entry, dict) else None
    return None if value in (None, "") else value


def _first_value_index(data: list) -> int | None:
    for j, entry in enumerate(data):
        if _entry_value(entry) is not None:
            return j
    return None


def _last_value_before(data: list, stop_idx: int) -> float | None:
    for j in range(min(stop_idx, len(data)) - 1, -1, -1):
        value = _entry_value(data[j])
        if value is not None:
            return float(value)
    return None
