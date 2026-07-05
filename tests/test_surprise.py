"""Standardized surprises: mapping, matched samples, per-group scaling."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src.analytics.surprise import label_expectation, standardized_surprises


def _release(indicator, period, actual, consensus, source):
    return {
        "indicator": indicator,
        "ref_period": pd.Timestamp(period),
        "release_datetime": datetime(2024, 1, 15, 8, 30),
        "actual": actual,
        "consensus": consensus,
        "source": source,
    }


RAWS = [0.1, -0.1, 0.2, -0.2]


@pytest.fixture()
def releases():
    rows = []
    for i, raw in enumerate(RAWS, start=1):
        period = f"2024-0{i}-01"
        rows.append(
            _release("CPI", period, 0.3 + raw, 0.3, "fred_first+cleveland_fed")
        )
        rows.append(_release("CPI", period, 0.3 + raw, 0.3, "fred_first+naive_prev"))
    # naive-only period (no nowcast row) -> excluded under matched samples
    rows.append(_release("CPI", "2024-05-01", 0.9, 0.3, "fred_first+naive_prev"))
    # consensus-less row -> always dropped
    rows.append(_release("CPI", "2024-06-01", 0.4, None, "fred_first"))
    # GDP track rows count as nowcast
    rows.append(_release("GDP", "2024-01-01", 2.5, 2.0, "gdpnow_track"))
    rows.append(_release("GDP", "2024-04-01", 1.5, 2.0, "gdpnow_track"))
    return pd.DataFrame(rows)


def test_label_expectation():
    assert label_expectation("fred_first+naive_prev") == "naive"
    assert label_expectation("fred_first+cleveland_fed") == "nowcast"
    assert label_expectation("gdpnow_track") == "nowcast"
    assert label_expectation("fred_first") is None


def test_z_is_raw_over_group_stdev(releases):
    out = standardized_surprises(releases)
    cpi_now = out[(out.indicator == "CPI") & (out.expectation == "nowcast")]
    sigma = np.std(RAWS, ddof=1)
    assert cpi_now["surprise_z"].tolist() == pytest.approx(
        [r / sigma for r in RAWS]
    )
    # By construction each group's z has unit sample stdev.
    assert cpi_now["surprise_z"].std(ddof=1) == pytest.approx(1.0)


def test_naive_restricted_to_nowcast_release_days(releases):
    out = standardized_surprises(releases)
    naive = out[(out.indicator == "CPI") & (out.expectation == "naive")]
    assert len(naive) == 4  # 2024-05 naive-only row excluded
    assert pd.Timestamp("2024-05-01") not in set(naive["ref_period"])


def test_match_can_be_disabled(releases):
    out = standardized_surprises(releases, match_naive=False)
    naive = out[(out.indicator == "CPI") & (out.expectation == "naive")]
    assert len(naive) == 5


def test_unlabeled_and_consensusless_rows_dropped(releases):
    out = standardized_surprises(releases)
    assert pd.Timestamp("2024-06-01") not in set(out["ref_period"])


def test_scaling_is_per_indicator(releases):
    out = standardized_surprises(releases)
    gdp = out[out.indicator == "GDP"]
    sigma = np.std([0.5, -0.5], ddof=1)
    assert gdp["surprise_z"].tolist() == pytest.approx([0.5 / sigma, -0.5 / sigma])
