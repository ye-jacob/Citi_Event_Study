"""The FOMC surprise stays a stub: out of the study scope (Methodology covers
CPI/PCE/GDP) and human-owned per CLAUDE.md."""

import pandas as pd
import pytest

from src.analytics import surprise


def test_fomc_surprise_still_stubbed():
    with pytest.raises(NotImplementedError, match="TODO\\(human\\)"):
        surprise.fomc_surprise(pd.DataFrame(), pd.DataFrame())
