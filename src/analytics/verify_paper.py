"""Verify every numeric claim in the paper draft against the analysis tables.

    python -m src.analytics.verify_paper [--db data/event_study.db]

Claims are transcribed from "Ye_TreasuryCurve_draft (1).docx" (July 2026).
Each is checked against data/event_study.db at the precision printed in the
paper (a value shown as 2.3 passes iff the stored value rounds to 2.3).
Exit code 0 = every claim matches; 1 = at least one mismatch.

If the data is re-ingested and results drift, this script says exactly which
sentences of the paper went stale. Re-run it after every ingest+analysis.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

from src import config

# --------------------------------------------------------------------------
# Claim helpers
# --------------------------------------------------------------------------


def cell(table, where, column, stated, decimals, label):
    """The table cell, rounded to the paper's printed decimals, must match."""
    return {
        "kind": "cell", "table": table, "where": where, "column": column,
        "stated": stated, "decimals": decimals, "label": label,
    }


def rng(table, where, column, lo, hi, label, agg=None):
    """An aggregate of matching rows must land inside [lo, hi]."""
    return {
        "kind": "range", "table": table, "where": where, "column": column,
        "lo": lo, "hi": hi, "agg": agg, "label": label,
    }


B = "analysis_baseline"
E = "analysis_era"
V = "analysis_event_vol"
G = "analysis_gap_trade"
A = "analysis_asymmetry"
C = "analysis_event_study"
O = "analysis_observations"

NOW = {"expectation": "nowcast"}

CLAIMS = [
    # ---- Table 2: baseline CPI, full sample --------------------------------
    cell(B, {**NOW, "indicator": "CPI", "factor": "level"}, "beta", 2.0, 1, "T2 level beta +2.0"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "level"}, "ci_low", 0.8, 1, "T2 level CI low +0.8"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "level"}, "ci_high", 3.1, 1, "T2 level CI high +3.1"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "level"}, "p", 0.001, 3, "T2 level p 0.001"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "level"}, "r2", 0.098, 3, "T2 level R2 0.098"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "level"}, "n", 153, 0, "T2 n = 153"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "slope_2s10s"}, "beta", -0.5, 1, "T2 2s10s beta -0.5"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "slope_2s10s"}, "ci_low", -1.4, 1, "T2 2s10s CI low -1.4"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "slope_2s10s"}, "ci_high", 0.4, 1, "T2 2s10s CI high +0.4"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "slope_2s10s"}, "p", 0.287, 3, "T2 2s10s p 0.287"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "slope_2s10s"}, "r2", 0.013, 3, "T2 2s10s R2 0.013"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "slope_5s30s"}, "beta", -1.3, 1, "T2 5s30s beta -1.3"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "slope_5s30s"}, "ci_low", -2.1, 1, "T2 5s30s CI low -2.1"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "slope_5s30s"}, "ci_high", -0.5, 1, "T2 5s30s CI high -0.5"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "slope_5s30s"}, "p", 0.001, 3, "T2 5s30s p 0.001"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "slope_5s30s"}, "r2", 0.087, 3, "T2 5s30s R2 0.087"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "curvature"}, "beta", 0.0, 1, "T2 curvature beta +0.0"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "curvature"}, "ci_low", -0.8, 1, "T2 curvature CI low -0.8"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "curvature"}, "ci_high", 0.8, 1, "T2 curvature CI high +0.8"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "curvature"}, "p", 0.966, 3, "T2 curvature p 0.966"),
    cell(B, {**NOW, "indicator": "CPI", "factor": "curvature"}, "r2", 0.000, 3, "T2 curvature R2 0.000"),
    # ---- Table 3: CPI by era (also intro's 2.3 / 1.7 / ~15% claims) --------
    cell(E, {"indicator": "CPI", "factor": "level", "era": "pre_2021"}, "beta", 1.0, 1, "T3 pre level beta +1.0"),
    cell(E, {"indicator": "CPI", "factor": "level", "era": "pre_2021"}, "p", 0.14, 2, "T3 pre level p 0.14"),
    cell(E, {"indicator": "CPI", "factor": "level", "era": "pre_2021"}, "r2", 0.02, 2, "T3 pre level R2 0.02"),
    cell(E, {"indicator": "CPI", "factor": "slope_5s30s", "era": "pre_2021"}, "beta", -0.3, 1, "T3 pre 5s30s beta -0.3"),
    cell(E, {"indicator": "CPI", "factor": "slope_5s30s", "era": "pre_2021"}, "p", 0.59, 2, "T3 pre 5s30s p 0.59"),
    cell(E, {"indicator": "CPI", "factor": "slope_5s30s", "era": "pre_2021"}, "r2", 0.00, 2, "T3 pre 5s30s R2 0.00"),
    cell(E, {"indicator": "CPI", "factor": "level", "era": "pre_2021"}, "n", 88, 0, "T3 pre n = 88"),
    cell(E, {"indicator": "CPI", "factor": "level", "era": "post_2021"}, "beta", 2.3, 1, "T3/intro post level beta +2.3"),
    cell(E, {"indicator": "CPI", "factor": "level", "era": "post_2021"}, "p", 0.004, 3, "T3 post level p 0.004"),
    cell(E, {"indicator": "CPI", "factor": "level", "era": "post_2021"}, "r2", 0.14, 2, "T3/intro post level R2 0.14"),
    cell(E, {"indicator": "CPI", "factor": "slope_5s30s", "era": "post_2021"}, "beta", -1.7, 1, "T3/intro post 5s30s beta -1.7"),
    cell(E, {"indicator": "CPI", "factor": "slope_5s30s", "era": "post_2021"}, "p", 0.001, 3, "T3 post 5s30s p 0.001"),
    cell(E, {"indicator": "CPI", "factor": "slope_5s30s", "era": "post_2021"}, "r2", 0.15, 2, "T3/intro post 5s30s R2 0.15"),
    cell(E, {"indicator": "CPI", "factor": "level", "era": "post_2021"}, "n", 65, 0, "T3 post n = 65"),
    # ---- 4.1 prose: event study day-0 jumps + asymmetry ---------------------
    rng(C, {"indicator": "CPI", "factor": "level", "group": "hot"}, "car",
        4.75, 4.85, "4.1 hot day-0 level jump ~ +4.8bp (CAR0 - CAR-1)", agg="day0"),
    rng(C, {"indicator": "CPI", "factor": "slope_5s30s", "group": "hot"}, "car",
        -3.05, -2.95, "4.1 hot day-0 5s30s ~ -3.0bp (CAR0 - CAR-1)", agg="day0"),
    rng(C, {"indicator": "CPI", "factor": "level", "group": "cold"}, "car",
        -6.0, -1.0, "4.1 cold prints 'do the reverse' (day-0 level < 0)", agg="day0"),
    cell(A, {"indicator": "CPI", "factor": "level"}, "beta_neg", 3.4, 1, "4.1 soft-print level beta 3.4"),
    cell(A, {"indicator": "CPI", "factor": "level"}, "beta_pos", 1.1, 1, "4.1 hot-print level beta 1.1"),
    cell(A, {"indicator": "CPI", "factor": "level"}, "p_equal", 0.24, 2, "4.1 asymmetry Wald p 0.24"),
    # ---- Table 4: event-day volatility (also intro's 1.4x claim) -----------
    cell(V, {"indicator": "CPI", "factor": "level", "window": "post_2021"}, "sd_event", 8.1, 1, "T4 CPI post sd 8.1"),
    cell(V, {"indicator": "CPI", "factor": "level", "window": "post_2021"}, "sd_control", 6.0, 1, "T4 CPI post control sd 6.0"),
    cell(V, {"indicator": "CPI", "factor": "level", "window": "post_2021"}, "vol_ratio", 1.37, 2, "T4/intro CPI post ratio 1.37"),
    cell(V, {"indicator": "CPI", "factor": "level", "window": "full"}, "sd_event", 6.3, 1, "T4 CPI full sd 6.3"),
    cell(V, {"indicator": "CPI", "factor": "level", "window": "full"}, "sd_control", 5.8, 1, "T4 CPI full control sd 5.8"),
    cell(V, {"indicator": "CPI", "factor": "level", "window": "full"}, "vol_ratio", 1.08, 2, "T4 CPI full ratio 1.08"),
    cell(V, {"indicator": "GDP", "factor": "level", "window": "full"}, "sd_event", 5.8, 1, "T4 GDP sd 5.8"),
    cell(V, {"indicator": "GDP", "factor": "level", "window": "full"}, "vol_ratio", 1.00, 2, "T4/intro GDP ratio 1.00"),
    cell(V, {"indicator": "PCE", "factor": "level", "window": "full"}, "sd_event", 4.9, 1, "T4 PCE sd 4.9"),
    cell(V, {"indicator": "PCE", "factor": "level", "window": "full"}, "vol_ratio", 0.84, 2, "T4/intro PCE ratio 0.84"),
    # ---- 4.2 prose ----------------------------------------------------------
    cell(B, {**NOW, "indicator": "PCE", "factor": "slope_2s10s"}, "beta", -0.5, 1, "4.2 PCE 2s10s beta -0.5"),
    cell(B, {**NOW, "indicator": "PCE", "factor": "slope_2s10s"}, "p", 0.03, 2, "4.2 PCE 2s10s p 0.03"),
    rng(B, {**NOW, "indicator": "GDP"}, "p", 0.7, 1.0, "4.2 GDP 'all p > 0.7'", agg="min"),
    cell(A, {"indicator": "GDP", "factor": "slope_2s10s"}, "beta_pos", 3.4, 1, "4.2 GDP upside 2s10s beta +3.4"),
    cell(A, {"indicator": "GDP", "factor": "slope_2s10s"}, "p_equal", 0.005, 3, "4.2 GDP Wald p 0.005"),
    cell(A, {"indicator": "GDP", "factor": "slope_2s10s"}, "n", 59, 0, "4.2 'only 59 quarters'"),
    rng(O, {"expectation": "nowcast"}, "sigma_ratio", 0.40, 0.60,
        "4.2 PCE surprise 'about half the size' of CPI's", agg="sigma_ratio"),
    # ---- Table 5: gap trade -------------------------------------------------
    cell(G, {"indicator": "CPI", "factor": "level"}, "n", 153, 0, "T5 CPI n 153"),
    cell(G, {"indicator": "CPI", "factor": "level"}, "hit_rate", 0.46, 2, "T5 CPI level hit 0.46"),
    cell(G, {"indicator": "CPI", "factor": "level"}, "mean_pnl", -0.60, 2, "T5 CPI level pnl -0.60"),
    cell(G, {"indicator": "CPI", "factor": "level"}, "t_pnl", -1.2, 1, "T5 CPI level t -1.2"),
    cell(G, {"indicator": "CPI", "factor": "slope_5s30s"}, "hit_rate", 0.50, 2, "T5 CPI 5s30s hit 0.50"),
    cell(G, {"indicator": "CPI", "factor": "slope_5s30s"}, "mean_pnl", 0.10, 2, "T5 CPI 5s30s pnl +0.10"),
    cell(G, {"indicator": "CPI", "factor": "slope_5s30s"}, "t_pnl", 0.3, 1, "T5 CPI 5s30s t +0.3"),
    cell(G, {"indicator": "PCE", "factor": "level"}, "n", 155, 0, "T5 PCE n 155"),
    cell(G, {"indicator": "PCE", "factor": "level"}, "hit_rate", 0.41, 2, "T5 PCE hit 0.41"),
    cell(G, {"indicator": "PCE", "factor": "level"}, "mean_pnl", 0.01, 2, "T5 PCE pnl +0.01"),
    cell(G, {"indicator": "PCE", "factor": "level"}, "t_pnl", 0.0, 1, "T5 PCE t +0.0"),
    cell(G, {"indicator": "GDP", "factor": "level"}, "n", 58, 0, "T5 GDP n 58"),
    cell(G, {"indicator": "GDP", "factor": "level"}, "hit_rate", 0.50, 2, "T5 GDP hit 0.50"),
    cell(G, {"indicator": "GDP", "factor": "level"}, "mean_pnl", -0.17, 2, "T5 GDP pnl -0.17"),
    cell(G, {"indicator": "GDP", "factor": "level"}, "t_pnl", -0.2, 1, "T5 GDP t -0.2"),
    # ---- 4.3 prose: 'twenty times more' -------------------------------------
    cell(B, {"indicator": "CPI", "factor": "level", "expectation": "naive"}, "r2", 0.005, 3, "4.3 naive level R2 0.005"),
    rng(B, {"indicator": "CPI", "factor": "level"}, "r2", 15.0, 25.0,
        "4.3 nowcast R2 'twenty times' naive", agg="r2_ratio"),
    # ---- Data section: sample spans -----------------------------------------
    rng(O, {"expectation": "nowcast", "indicator": "CPI"}, "ref_period", 2013, 2013,
        "Data: CPI sample starts 2013", agg="min_year"),
    rng(O, {"expectation": "nowcast", "indicator": "PCE"}, "ref_period", 2013, 2013,
        "Data: PCE sample starts 2013", agg="min_year"),
    rng(O, {"expectation": "nowcast", "indicator": "GDP"}, "ref_period", 2013, 2013,
        "Data: paper says releases span '2013 to 2026' (GDP too)", agg="min_year"),
]

NOTES = [
    "Wording (4.2): the paper attaches p = 0.005 to the +3.4bp GDP upside "
    "coefficient. In the tables, 0.005 is the Wald p for EQUAL slopes "
    "(beta+ = beta-); beta+'s own p is ~0.01. Consider rewording to "
    "'+3.4bp; Wald test against equal slopes p = 0.005' as in findings.md.",
    "KNOWN DOCX EDITS PENDING (the two FAILs above are intentional until the "
    "docx is updated): (1) 4.1 hot day-0 level jump is 4.87bp -> say 'about "
    "4.9bp', not 4.8 (4.8 came from subtracting rounded CAR values); "
    "(2) Data section: GDP sample starts 2011 (GDPNow history), not 2013 -> "
    "e.g. 'from 2013 (CPI, PCE) and 2011 (GDP) through 2026'. After editing "
    "the docx, update these two claims' stated values here so the manifest "
    "matches the paper again.",
]


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------


def _filter(df: pd.DataFrame, where: dict) -> pd.DataFrame:
    for col, val in where.items():
        df = df[df[col] == val]
    return df


def _aggregate(df: pd.DataFrame, claim: dict, tables: dict) -> float:
    agg, col = claim["agg"], claim["column"]
    if agg == "min":
        return float(df[col].min())
    if agg == "day0":  # CAR(0) - CAR(-1) = the release-day abnormal move
        s = df.set_index("tau")[col]
        return float(s.loc[0] - s.loc[-1])
    if agg == "min_year":
        return float(pd.to_datetime(df[col]).dt.year.min())
    if agg == "sigma_ratio":  # PCE raw-surprise sd over CPI's
        sd = df.groupby("indicator")["surprise_raw"].std(ddof=1)
        return float(sd["PCE"] / sd["CPI"])
    if agg == "r2_ratio":  # nowcast R2 over naive R2
        by = df.set_index("expectation")[col]
        return float(by["nowcast"] / by["naive"])
    raise ValueError(f"unknown agg {agg!r}")


def run(db_path: Path) -> int:
    with sqlite3.connect(db_path) as con:
        tables = {
            t: pd.read_sql(f"SELECT * FROM {t}", con)
            for t in {c["table"] for c in CLAIMS}
        }

    failures = 0
    for claim in CLAIMS:
        df = _filter(tables[claim["table"]], claim["where"])
        try:
            if claim["kind"] == "cell":
                assert len(df) == 1, f"expected 1 row, got {len(df)}"
                actual = float(df.iloc[0][claim["column"]])
                tol = 0.5 * 10 ** (-claim["decimals"]) + 1e-9
                ok = abs(actual - claim["stated"]) <= tol
                shown = f"stated {claim['stated']} vs stored {actual:.4f}"
            else:
                actual = _aggregate(df, claim, tables)
                ok = claim["lo"] - 1e-9 <= actual <= claim["hi"] + 1e-9
                shown = (
                    f"stored {actual:.4f} vs stated range "
                    f"[{claim['lo']}, {claim['hi']}]"
                )
        except Exception as exc:  # missing table/row counts as a failure
            ok, shown = False, f"error: {exc}"
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"[{status}] {claim['label']:55s} {shown}")

    print(f"\n{len(CLAIMS) - failures}/{len(CLAIMS)} claims verified against {db_path}")
    for note in NOTES:
        print(f"[NOTE] {note}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.analytics.verify_paper",
        description=__doc__.splitlines()[0],
    )
    parser.add_argument("--db", default=config.DB_PATH, type=Path)
    args = parser.parse_args(argv)
    if not args.db.exists():
        parser.error(f"{args.db} not found")
    return run(args.db)


if __name__ == "__main__":
    sys.exit(main())
