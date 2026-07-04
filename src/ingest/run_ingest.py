"""Ingest CLI: FRED/ALFRED -> normalized SQLite (data/event_study.db).

    python -m src.ingest.run_ingest --vintage first [--start 2000-01-01]

``--vintage`` is REQUIRED by design. Which value counts as "the actual" (first
print vs today's revision) is the project's flagship analytical decision and is
made by the human per run — the tooling refuses to default it (CLAUDE.md
gotcha #1).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import pandas as pd
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from src import config, db
from src.models import CurvePoint, Release as ReleaseRow
from src.sources.base import Release
from src.sources.cleveland_fed import ClevelandFedNowcast
from src.sources.consensus import ConsensusProvider, ProviderConsensusSource
from src.sources.fred import VALID_VINTAGES, FredDataSource
from src.sources.gdpnow import GdpNowNowcast
from src.sources.naive import NaiveConsensusSource

# Factories for registry-declared public consensus providers. Instantiated
# lazily and cached per run (each fetch downloads a multi-MB public file).
PROVIDER_FACTORIES: dict[str, type] = {
    ClevelandFedNowcast.source_label: ClevelandFedNowcast,
    GdpNowNowcast.source_label: GdpNowNowcast,
}

EPILOG = """\
Why --vintage has no default:
  first   = ALFRED first prints — what the market's surprise was judged against.
  latest  = today's revised values — silently corrupts historical surprises.
The choice (and its defense) belongs to the human. See CLAUDE.md "Known gotchas".
"""


def upsert_curve(session: Session, curve: pd.DataFrame) -> int:
    n = 0
    for dt, row in curve.iterrows():
        for tenor, value in row.items():
            if pd.isna(value):
                continue  # market holiday
            stmt = (
                insert(CurvePoint)
                .values(date=dt.date(), tenor=tenor, yield_pct=float(value))
                .on_conflict_do_update(
                    index_elements=["date", "tenor"],
                    # keyed by the real column ("yield"), not the ORM attribute
                    set_={CurvePoint.__table__.c["yield"]: float(value)},
                )
            )
            session.execute(stmt)
            n += 1
    return n


def upsert_releases(
    session: Session, indicator_ids: dict[str, int], releases: list[Release]
) -> int:
    n = 0
    for r in releases:
        stmt = (
            insert(ReleaseRow)
            .values(
                indicator_id=indicator_ids[r.indicator],
                ref_period=r.ref_period,
                release_datetime=r.release_datetime,
                actual=r.actual,
                consensus=r.consensus,
                consensus_stdev=r.consensus_stdev,
                n_estimates=r.n_estimates,
                previous=r.previous,
                is_first_print=r.is_first_print,
                source=r.source,
            )
            .on_conflict_do_update(
                index_elements=["indicator_id", "ref_period", "source"],
                set_={
                    "release_datetime": r.release_datetime,
                    "actual": r.actual,
                    "consensus": r.consensus,
                    "consensus_stdev": r.consensus_stdev,
                    "n_estimates": r.n_estimates,
                    "previous": r.previous,
                    "is_first_print": r.is_first_print,
                },
            )
        )
        session.execute(stmt)
        n += 1
    return n


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.ingest.run_ingest",
        description=__doc__.splitlines()[0],
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--vintage",
        required=True,
        choices=sorted(VALID_VINTAGES),
        help="Which value counts as 'the actual' — human decision, no default.",
    )
    parser.add_argument("--start", type=date.fromisoformat, default=date(2000, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    parser.add_argument(
        "--indicators",
        nargs="*",
        default=None,
        metavar="KEY",
        help="Registry keys to ingest (default: all active).",
    )
    parser.add_argument("--db", default=None, help=f"SQLite path (default {config.DB_PATH})")
    parser.add_argument("--skip-curve", action="store_true")
    parser.add_argument("--skip-releases", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    end = args.end or date.today()

    engine = db.get_engine(args.db)
    db.init_db(engine)

    fred = FredDataSource(vintage=args.vintage)
    source = NaiveConsensusSource(fred)  # baseline rows, always written
    providers: dict[str, ConsensusProvider] = {}
    registry = config.indicators_by_key()
    keys = args.indicators or config.active_indicator_keys()

    with db.session_scope(engine) as session:
        db.seed_indicators(session)
        indicator_ids = db.indicator_id_map(session)

        if not args.skip_curve:
            curve = source.get_curve(args.start, end)
            n_curve = upsert_curve(session, curve)
            print(f"curve: upserted {n_curve} (date, tenor) points")

        if not args.skip_releases:
            for key in keys:
                meta = registry.get(key)
                if meta is None:
                    print(f"{key}: unknown indicator key — skipped", file=sys.stderr)
                    continue
                if not meta["active"]:
                    print(
                        f"{key}: inactive ({meta['notes']}) — skipped",
                        file=sys.stderr,
                    )
                    continue
                releases = source.get_releases(key, args.start, end)
                n = upsert_releases(session, indicator_ids, releases)
                print(f"{key}: upserted {n} releases (vintage={args.vintage})")

                # Public consensus rows (Cleveland Fed / GDPNow) — written
                # ALONGSIDE the naive baseline, distinguished by source.
                label = meta.get("consensus")
                if not label:
                    continue
                try:
                    provider = providers.get(label)
                    if provider is None:
                        provider = PROVIDER_FACTORIES[label]()
                        providers[label] = provider
                    if isinstance(provider, GdpNowNowcast):
                        # GDP rows come wholly from the Atlanta Fed track
                        # record: ALFRED has no true pre-2014 first prints for
                        # the SAAR series (see gdpnow.py docstring).
                        prov_rows = provider.build_releases(
                            meta["release_time"], args.start, end
                        )
                    else:
                        overlay = ProviderConsensusSource(fred, provider)
                        prov_rows = overlay.get_releases(key, args.start, end)
                    n_prov = upsert_releases(session, indicator_ids, prov_rows)
                    print(f"{key}: upserted {n_prov} releases (consensus={label})")
                except Exception as exc:  # degrade gracefully; baseline stands
                    print(
                        f"{key}: consensus provider {label} failed ({exc}) — "
                        "naive baseline rows only",
                        file=sys.stderr,
                    )

    print(f"done -> {args.db or config.DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
