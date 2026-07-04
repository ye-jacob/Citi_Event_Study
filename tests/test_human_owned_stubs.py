"""The human-owned analytics must stay unimplemented until the human writes
them — the stubs exist, import cleanly, and say so loudly (CLAUDE.md division
of labor)."""

import pandas as pd
import pytest

from src.analytics import event_study, surprise


@pytest.mark.parametrize(
    "call",
    [
        lambda: surprise.compute_raw_surprise(pd.DataFrame()),
        lambda: surprise.compute_standardized_surprise(pd.DataFrame()),
        lambda: surprise.fomc_surprise(pd.DataFrame(), pd.DataFrame()),
        lambda: event_study.classify_regime(pd.DataFrame()),
        lambda: event_study.compute_event_impacts(
            pd.DataFrame(), pd.DataFrame(), "tm1c_t0c"
        ),
        lambda: event_study.estimate_surprise_betas(pd.DataFrame(), pd.DataFrame()),
    ],
)
def test_stub_raises_with_todo_human(call):
    with pytest.raises(NotImplementedError, match="TODO\\(human\\)"):
        call()
