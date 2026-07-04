"""Sanity checks on the indicator registry (config.INDICATORS)."""

from datetime import time

from src import config


def test_keys_unique():
    keys = [row["key"] for row in config.INDICATORS]
    assert len(keys) == len(set(keys))


def test_yield_signs_are_unit():
    for row in config.INDICATORS:
        assert row["yield_sign"] in (1, -1), row["key"]


def test_directionality_matches_claude_md():
    # Higher unemployment / claims push yields DOWN; CPI/PCE/NFP/GDP push UP.
    by_key = config.indicators_by_key()
    assert by_key["UNRATE"]["yield_sign"] == -1
    assert by_key["CLAIMS"]["yield_sign"] == -1
    for key in ("CPI", "PCE", "NFP", "GDP", "RETAIL"):
        assert by_key[key]["yield_sign"] == 1


def test_active_indicators_are_ingestable():
    for row in config.INDICATORS:
        if row["active"]:
            assert row["fred_series"], f"{row['key']} active but has no FRED series"
        assert row["transform"] in config.VALID_TRANSFORMS, row["key"]
        assert isinstance(row["release_time"], time), row["key"]


def test_known_gotchas_stay_inactive_until_human_enables():
    by_key = config.indicators_by_key()
    # FOMC: futures-based surprise not built; ISM: licensing unverified.
    assert by_key["FOMC"]["active"] is False
    assert by_key["ISM_MFG"]["active"] is False
    assert by_key["ISM_SRV"]["active"] is False


def test_core_tenors_have_fred_series():
    for tenor in config.CORE_TENORS:
        assert tenor in config.TENOR_FRED_SERIES
