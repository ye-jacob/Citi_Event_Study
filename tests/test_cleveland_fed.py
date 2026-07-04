"""Cleveland Fed nowcast parser: last nowcast STRICTLY before the release
marker, released-months-only, no post-release leakage."""

import pandas as pd
import pytest

from src.sources.cleveland_fed import ClevelandFedNowcast, parse_month_charts


def _chart(subcaption, labels, series):
    return {
        "chart": {"subcaption": subcaption},
        "categories": [{"category": [{"label": lb} for lb in labels]}],
        "dataset": [
            {"seriesname": name, "data": [{"value": v} for v in values]}
            for name, values in series.items()
        ],
    }


RAW = [
    # Post-2014 chart format: the window ends at the own-month CPI release;
    # there is NO own-month PCE marker — the PCE nowcast series just stops
    # before the (later) PCE release, and "Actual PCE" never appears.
    _chart(
        "2024-3",
        ["03/28", "03/29", "04/01", "CPI Mar", "04/11", "04/12"],
        {
            "CPI Inflation": ["0.31", "0.32", "0.35", "0.99", "", ""],
            "PCE Inflation": ["0.28", "0.29", "0.30", "0.33", "0.34", ""],
            "Actual CPI Inflation": ["", "", "", "0.38", "0.38", "0.38"],
        },
    ),
    # Pre-2014 format: own-month PCE marker present -> marker cutoff wins
    # over the series tail (0.99 at/after the marker must never be used).
    _chart(
        "2013-7",
        ["08/28", "08/29", "PCE Jul"],
        {
            "PCE Inflation": ["0.11", "0.12", "0.99"],
            "CPI Inflation": ["", "", ""],
            "Actual PCE Inflation": ["", "", "0.14"],
        },
    ),
    # Malformed subcaption -> skipped, not fatal.
    {"chart": {"subcaption": "n/a"}, "categories": [{"category": []}], "dataset": []},
]


def test_cpi_cutoff_is_marker_and_actual_never_leaks():
    tables = parse_month_charts(RAW)
    cpi = tables["CPI"]
    assert list(cpi.index) == [pd.Timestamp(2024, 3, 1)]
    # 0.35 (the 04/01 nowcast), NOT 0.99 at the "CPI Mar" column.
    assert cpi.loc[pd.Timestamp(2024, 3, 1), "consensus"] == pytest.approx(0.35)


def test_pce_without_marker_uses_series_tail():
    tables = parse_month_charts(RAW)
    # Nowcast series stops pre-release: last non-empty value is the consensus.
    assert tables["PCE"].loc[pd.Timestamp(2024, 3, 1), "consensus"] == pytest.approx(
        0.34
    )


def test_pce_marker_cutoff_wins_when_present():
    tables = parse_month_charts(RAW)
    # Pre-2014 format: 0.12 (last before "PCE Jul"), never 0.99 at the marker.
    assert tables["PCE"].loc[pd.Timestamp(2013, 7, 1), "consensus"] == pytest.approx(
        0.12
    )


def test_provider_interface():
    provider = ClevelandFedNowcast(raw=RAW)
    assert provider.source_label == "cleveland_fed"
    df = provider.get_consensus("CPI")
    assert "consensus" in df.columns
    with pytest.raises(ValueError, match="covers"):
        provider.get_consensus("NFP")
