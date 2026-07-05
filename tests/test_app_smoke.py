"""Execute the Streamlit app end-to-end against the committed DB.

Skipped when the DB hasn't been built yet (fresh clone before ingest)."""

import pytest

from src import config


@pytest.mark.skipif(not config.DB_PATH.exists(), reason="no committed DB")
def test_app_runs_without_exceptions():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("src/app/app.py", default_timeout=60)
    at.run()
    assert not at.exception, at.exception
