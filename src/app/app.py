"""Streamlit demo layer — READ-ONLY, deliberately thin.

The deliverable is analysis/findings.md; this app just lets a reader poke at
the precomputed data behind it (CLAUDE.md: "a link, not the pitch"). It reads
the committed SQLite DB, writes nothing, and hosts no scheduler — the GitHub
Actions workflow is the backend (ephemeral-filesystem deployment pattern).

Run:  streamlit run src/app/app.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

# Allow `streamlit run src/app/app.py` from the repo root without installing.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src import charts, config  # noqa: E402
from src.analytics import curve as curve_math  # noqa: E402

st.set_page_config(page_title="Treasury Curve Event Study", layout="wide")


# ----------------------------------------------------------------- loaders
@st.cache_data(ttl=3600)
def load_curve() -> pd.DataFrame:
    query = "SELECT date, tenor, yield AS yield_pct FROM curve ORDER BY date"
    with _connect() as con:
        long = pd.read_sql(query, con, parse_dates=["date"])
    return long.pivot(index="date", columns="tenor", values="yield_pct")


@st.cache_data(ttl=3600)
def load_releases() -> pd.DataFrame:
    query = """
        SELECT i.key AS indicator, i.name, i.units, i.yield_sign,
               r.ref_period, r.release_datetime, r.actual, r.consensus,
               r.consensus_stdev, r.n_estimates, r.previous,
               r.is_first_print, r.source
        FROM releases r JOIN indicators i ON i.id = r.indicator_id
        ORDER BY r.release_datetime
    """
    with _connect() as con:
        return pd.read_sql(
            query, con, parse_dates=["ref_period", "release_datetime"]
        )


def _connect():
    import sqlite3

    return sqlite3.connect(config.DB_PATH)


# ------------------------------------------------------------------ layout
st.title("Treasury Curve Event Study")
st.caption(
    "How macro surprises move the *shape* of the US Treasury curve — level, "
    "slope, curvature — conditional on the Fed regime. This app is a demo "
    "layer; the deliverable is the writeup."
)

if not config.DB_PATH.exists():
    st.info(
        "No data yet. Populate the committed DB first:\n\n"
        "```bash\nexport FRED_API_KEY=...\n"
        "python -m src.ingest.run_ingest --vintage first\n```\n\n"
        "`--vintage` is required on purpose — the first-print vs revised "
        "decision is human-owned (see CLAUDE.md)."
    )
    st.stop()

tab_findings, tab_curve, tab_releases = st.tabs(
    ["Findings", "Curve explorer", "Releases"]
)

with tab_findings:
    findings = config.FINDINGS_PATH
    if findings.exists():
        st.markdown(findings.read_text())
    else:
        st.info("analysis/findings.md not found.")

with tab_curve:
    curve = load_curve()
    if curve.empty:
        st.info("Curve table is empty — run the ingest.")
    else:
        min_d, max_d = curve.index.min().date(), curve.index.max().date()
        col1, col2 = st.columns(2)
        start = col1.date_input(
            "From", value=max(min_d, date(max_d.year - 5, 1, 1)),
            min_value=min_d, max_value=max_d,
        )
        end = col2.date_input("To", value=max_d, min_value=min_d, max_value=max_d)
        window = curve.loc[str(start) : str(end)]

        tenors = st.multiselect(
            "Tenors",
            options=list(curve.columns),
            default=[t for t in config.CORE_TENORS if t in curve.columns],
        )
        if tenors:
            st.plotly_chart(
                charts.fig_curve_history(window, tenors),
                use_container_width=True,
                theme=None,  # the helpers' validated palette governs
            )

        has_core = all(t in curve.columns for t in curve_math.REQUIRED_TENORS)
        if has_core and st.toggle("Show shape measures (level / slopes / curvature)"):
            st.plotly_chart(
                charts.fig_shape_history(curve_math.shape_measures(window)),
                use_container_width=True,
                theme=None,
            )

        # Relief rule: every chart's data is also reachable as a table.
        with st.expander("Data table"):
            st.dataframe(window[tenors] if tenors else window)

with tab_releases:
    releases = load_releases()
    if releases.empty:
        st.info("Releases table is empty — run the ingest.")
    else:
        keys = sorted(releases["indicator"].unique())
        key = st.selectbox("Indicator", keys)
        subset = releases[releases["indicator"] == key]
        srcs = st.multiselect(
            "Source", sorted(subset["source"].unique()),
            default=sorted(subset["source"].unique()),
        )
        subset = subset[subset["source"].isin(srcs)]
        st.caption(
            f"{len(subset)} releases. Consensus here may be the NAIVE proxy "
            "(expectation = previous) — check the source column."
        )
        st.dataframe(subset.drop(columns=["indicator"]), use_container_width=True)
        st.info(
            "Surprises, event-window curve deltas, and betas appear here once "
            "the human-owned analytics are implemented "
            "(src/analytics/surprise.py, event_study.py)."
        )

st.divider()
st.caption(
    "Data: FRED/ALFRED (first-print vintages supported). App is read-only; "
    "ingest runs in GitHub Actions and commits the refreshed DB."
)
