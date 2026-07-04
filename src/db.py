"""Engine/session helpers and indicator seeding."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src import config
from src.models import Base, Indicator


def get_engine(db_path: str | Path | None = None) -> Engine:
    path = Path(db_path) if db_path is not None else config.DB_PATH
    return create_engine(f"sqlite:///{path}")


def init_db(engine: Engine) -> None:
    """Create the data directory (if needed) and all tables."""
    db_file = engine.url.database
    if db_file:  # not :memory:
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def seed_indicators(session: Session) -> None:
    """Upsert the config registry into the indicators table (idempotent).

    Existing rows are updated in place so registry edits (e.g. the human fixing
    a transform after verification) propagate on the next ingest.
    """
    existing = {
        ind.key: ind for ind in session.execute(select(Indicator)).scalars()
    }
    for row in config.INDICATORS:
        ind = existing.get(row["key"])
        if ind is None:
            ind = Indicator(key=row["key"])
            session.add(ind)
        ind.name = row["name"]
        ind.freq = row["freq"]
        ind.fred_series = row["fred_series"]
        ind.yield_sign = row["yield_sign"]
        ind.release_time = row["release_time"]
        ind.transform = row["transform"]
        ind.units = row["units"]
        ind.consensus_source = row["consensus"]
        ind.active = row["active"]
        ind.notes = row["notes"]
    session.flush()


def indicator_id_map(session: Session) -> dict[str, int]:
    return {
        ind.key: ind.id for ind in session.execute(select(Indicator)).scalars()
    }
