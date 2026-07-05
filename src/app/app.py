"""Streamlit demo layer — READ-ONLY, deliberately thin.

Shows the precomputed results of the event study (Methodology 3.1-3.4) plus
the underlying data. It reads the committed SQLite DB, writes nothing, and
hosts no scheduler; ingest + analysis run offline / in Actions.

Run:  streamlit run src/app/app.py
"""

from __future__ import annotations

import sqlite3
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

FACTOR_LABELS = {
    "level": "Level (10Y)",
    "slope_2s10s": "2s10s slope",
    "slope_5s30s": "5s30s slope",
    "curvature": "Curvature",
}


# ----------------------------------------------------------------- loaders
def _connect():
    return sqlite3.connect(config.DB_PATH)


@st.cache_data(ttl=3600)
def table_names() -> set[str]:
    with _connect() as con:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {r[0] for r in rows}


@st.cache_data(ttl=3600)
def load_table(name: str) -> pd.DataFrame:
    with _connect() as con:
        return pd.read_sql(f"SELECT * FROM {name}", con)


@st.cache_data(ttl=3600)
def load_curve() -> pd.DataFrame:
    query = "SELECT date, tenor, yield AS yield_pct FROM curve ORDER BY date"
    with _connect() as con:
        long = pd.read_sql(query, con, parse_dates=["date"])
    return long.pivot(index="date", columns="tenor", values="yield_pct")


@st.cache_data(ttl=3600)
def load_releases() -> pd.DataFrame:
    query = """
        SELECT i.key AS indicator, i.units, r.ref_period, r.release_datetime,
               r.actual, r.consensus, r.previous, r.is_first_print, r.source
        FROM releases r JOIN indicators i ON i.id = r.indicator_id
        ORDER BY r.release_datetime
    """
    with _connect() as con:
        return pd.read_sql(query, con, parse_dates=["ref_period", "release_datetime"])


# ------------------------------------------------------------------ layout
st.title("Treasury Curve Event Study")
st.caption(
    "How macro surprises move the *shape* of the US Treasury curve — level, "
    "slope, curvature. CPI, PCE and GDP surprises vs. free public consensus "
    "(Cleveland Fed nowcast, Atlanta Fed GDPNow), first-print actuals via "
    "ALFRED. This app is a demo layer; the writeup is the deliverable."
)

if not config.DB_PATH.exists():
    st.info(
        "No data yet:\n\n```bash\nexport FRED_API_KEY=...\n"
        "python -m src.ingest.run_ingest --vintage first\n"
        "python -m src.analytics.run_analysis\n```"
    )
    st.stop()

tab_results, tab_curve, tab_releases, tab_findings = st.tabs(
    ["Results", "Curve explorer", "Releases", "Findings"]
)

# ------------------------------------------------------------- results tab
with tab_results:
    needed = {
        "analysis_observations",
        "analysis_baseline",
        "analysis_asymmetry",
        "analysis_event_study",
    }
    if not needed <= table_names():
        st.info(
            "Results not computed yet — run:\n\n"
            "```bash\npython -m src.analytics.run_analysis\n```"
        )
    else:
        obs = load_table("analysis_observations")
        baseline = load_table("analysis_baseline")
        asym = load_table("analysis_asymmetry")
        cars = load_table("analysis_event_study")

        indicator = st.selectbox("Indicator", sorted(baseline["indicator"].unique()))
        b_now = baseline[
            (baseline.indicator == indicator) & (baseline.expectation == "nowcast")
        ].assign(factor_label=lambda d: d["factor"].map(FACTOR_LABELS))

        # --- 3.1 baseline ---------------------------------------------------
        st.subheader("Baseline: curve response per 1σ surprise")
        col_fig, col_scatter = st.columns(2)
        with col_fig:
            st.plotly_chart(
                charts.fig_beta_bars(b_now, label_col="factor_label"),
                use_container_width=True,
                theme=None,
            )
        with col_scatter:
            factor = st.selectbox(
                "Factor", list(FACTOR_LABELS), format_func=FACTOR_LABELS.get
            )
            o = obs[(obs.indicator == indicator) & (obs.expectation == "nowcast")]
            row = b_now[b_now.factor == factor].iloc[0]
            xs = pd.Series([o["surprise_z"].min(), o["surprise_z"].max()])
            fit = pd.DataFrame({"x": xs, "y": row["alpha"] + row["beta"] * xs})
            st.plotly_chart(
                charts.fig_surprise_scatter(
                    o.rename(columns={f"delta_{factor}": "delta_bps"}),
                    fit=fit,
                    y_title=f"Δ {FACTOR_LABELS[factor]} (bps)",
                ),
                use_container_width=True,
                theme=None,
            )
        st.dataframe(
            b_now[["factor", "n", "beta", "se", "t", "p", "r2"]].round(3),
            use_container_width=True, hide_index=True,
        )

        # --- 3.2 asymmetry ----------------------------------------------------
        st.subheader("Asymmetry: upside vs downside surprises")
        a = asym[asym.indicator == indicator]
        long = pd.concat(
            [
                a.assign(
                    side="positive", b=a.beta_pos,
                    lo=a.ci_pos_low, hi=a.ci_pos_high,
                ),
                a.assign(
                    side="negative", b=a.beta_neg,
                    lo=a.ci_neg_low, hi=a.ci_neg_high,
                ),
            ]
        ).assign(factor_label=lambda d: d["factor"].map(FACTOR_LABELS))
        st.plotly_chart(
            charts.fig_beta_bars(
                long, label_col="factor_label", beta_col="b",
                ci_low_col="lo", ci_high_col="hi",
                group_col="side", color_map=charts.SIGN_COLORS,
            ),
            use_container_width=True, theme=None,
        )
        st.dataframe(
            a[["factor", "n", "beta_pos", "se_pos", "beta_neg", "se_neg",
               "p_equal", "r2"]].round(3),
            use_container_width=True, hide_index=True,
        )

        # --- 3.3 nowcast vs naive ----------------------------------------------
        st.subheader("Nowcast vs naive expectations (matched samples)")
        b_both = baseline[baseline.indicator == indicator].assign(
            factor_label=lambda d: d["factor"].map(FACTOR_LABELS)
        )
        st.plotly_chart(
            charts.fig_beta_bars(
                b_both, label_col="factor_label", beta_col="r2",
                ci_low_col=None, ci_high_col=None,
                group_col="expectation", color_map=charts.EXPECTATION_COLORS,
                x_title="R² of the release-day regression",
            ),
            use_container_width=True, theme=None,
        )
        st.dataframe(
            b_both.pivot_table(
                index="factor", columns="expectation", values=["beta", "r2"]
            ).round(3),
            use_container_width=True,
        )

        # --- 3.4 event study ------------------------------------------------
        st.subheader("Event study: extreme surprises (top/bottom decile)")
        c = cars[(cars.indicator == indicator) & (cars.factor == factor)]
        if c.empty:
            st.caption("No event-study rows for this slice.")
        else:
            st.plotly_chart(
                charts.fig_car_lines(
                    c, title=f"{indicator} — {FACTOR_LABELS[factor]}"
                ),
                use_container_width=True, theme=None,
            )
            st.caption(
                "Abnormal = daily change minus the mean release-day change on "
                "control (non-extreme) releases; cumulated from τ=−5."
            )

        # --- era conditioning -------------------------------------------------
        if "analysis_era" in table_names():
            eras = load_table("analysis_era")
            e = eras[eras.indicator == indicator].assign(
                factor_label=lambda d: d["factor"].map(FACTOR_LABELS)
            )
            if not e.empty:
                st.subheader("When the print matters: pre- vs post-2021 betas")
                st.plotly_chart(
                    charts.fig_beta_bars(
                        e, label_col="factor_label",
                        group_col="era", color_map=charts.ERA_COLORS,
                    ),
                    use_container_width=True, theme=None,
                )
                st.dataframe(
                    e[["era", "factor", "n", "beta", "se", "p", "r2"]].round(3),
                    use_container_width=True, hide_index=True,
                )

        # --- event-day vol premium ---------------------------------------------
        if "analysis_event_vol" in table_names():
            vol = load_table("analysis_event_vol")
            v = vol[vol.indicator == indicator]
            if not v.empty:
                st.subheader("Are release days high-vol days?")
                st.dataframe(
                    v[["window", "factor", "n_event", "sd_event", "sd_control",
                       "vol_ratio", "mean_abs_event", "mean_abs_control"]].round(2),
                    use_container_width=True, hide_index=True,
                )
                st.caption(
                    "Release-day stdev of each factor's daily change vs all "
                    "non-release trading days (bps)."
                )

        # --- ex-ante gap signal ---------------------------------------------
        if "analysis_gap_trade" in table_names():
            gap = load_table("analysis_gap_trade")
            gp = gap[gap.indicator == indicator]
            if not gp.empty:
                st.subheader("Ex-ante test: is the public nowcast already priced?")
                st.dataframe(
                    gp[["factor", "n", "hit_rate", "mean_pnl", "t_pnl",
                        "gamma", "gamma_p"]].round(3),
                    use_container_width=True, hide_index=True,
                )
                st.caption(
                    "Rule: at the close before the release, position in the "
                    "direction of (public nowcast − previous print); exit at "
                    "the release-day close. mean_pnl is gross bps per trade. "
                    "The signal uses only information public before the print."
                )

# --------------------------------------------------------------- curve tab
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
            "Tenors", options=list(curve.columns),
            default=[t for t in config.CORE_TENORS if t in curve.columns],
        )
        if tenors:
            st.plotly_chart(
                charts.fig_curve_history(window, tenors),
                use_container_width=True, theme=None,
            )
        has_core = all(t in curve.columns for t in curve_math.REQUIRED_TENORS)
        if has_core and st.toggle("Show shape measures (level / slopes / curvature)"):
            st.plotly_chart(
                charts.fig_shape_history(curve_math.shape_measures(window)),
                use_container_width=True, theme=None,
            )
        with st.expander("Data table"):
            st.dataframe(window[tenors] if tenors else window)

# ------------------------------------------------------------ releases tab
with tab_releases:
    releases = load_releases()
    if releases.empty:
        st.info("Releases table is empty — run the ingest.")
    else:
        keys = sorted(releases["indicator"].unique())
        key = st.selectbox("Indicator", keys, key="rel_ind")
        subset = releases[releases["indicator"] == key]
        srcs = st.multiselect(
            "Source", sorted(subset["source"].unique()),
            default=sorted(subset["source"].unique()),
        )
        subset = subset[subset["source"].isin(srcs)]
        st.caption(
            f"{len(subset)} releases. First-print actuals; consensus provenance "
            "in the source column (see data/exports/DATA_DICTIONARY.md)."
        )
        st.dataframe(
            subset.drop(columns=["indicator"]),
            use_container_width=True, hide_index=True,
        )

# ------------------------------------------------------------ findings tab
with tab_findings:
    findings = config.FINDINGS_PATH
    if findings.exists():
        st.markdown(findings.read_text())
    else:
        st.info("analysis/findings.md not found.")

st.divider()
st.caption(
    "Data: FRED/ALFRED first prints · Cleveland Fed inflation nowcast · "
    "Atlanta Fed GDPNow · Fed H.15 curve. Read-only app over committed data."
)
