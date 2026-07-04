# Treasury Curve Event Study

**How do macro surprises move the *shape* of the US Treasury yield curve — and does the
effect depend on the Fed regime?**

Free economic calendars answer "did the market move." This project answers a narrower
question a rates audience actually cares about: how a *surprise* (actual vs. consensus,
in standard deviations) moves curve **level, slope (2s10s, 5s30s), and curvature**,
conditional on whether the Fed is hiking, cutting, or on hold.

The deliverable is the writeup in [`analysis/findings.md`](analysis/findings.md) —
2–3 defensible findings with methodology and an honest limitations section. Everything
else in this repo (pipeline, database, Streamlit app) exists to earn one defensible
sentence per indicator, e.g.:

> *"A +1σ CPI surprise flattens 2s10s by ~X bps on average, and the effect roughly
> doubles in a hiking regime versus on hold."*

Working doctrine, division of labor, and design decisions live in [`CLAUDE.md`](CLAUDE.md).

---

## Why the data work is the hard part

### First prints, not revisions

A surprise is judged against what the market *saw at the time* — the first published
print — not against today's revised value. Using revised FRED data silently corrupts
historical surprises. This pipeline pulls **full vintage histories from ALFRED** and
tags every release with `is_first_print`.

It goes one level deeper: for indicators quoted as a *change* (NFP, CPI MoM), the
published headline is **not** the difference of consecutive first prints — it's this
month's first print minus the prior month **as revised in the same report**. NFP
revises prior months every release and re-benchmarks annually, so naive
diff-of-first-prints can miss the reported headline by >100k. The client computes
transforms against the prior period's value *as of the release date* (ALFRED as-of
lookup — the "same-vintage rule" in [`src/sources/fred.py`](src/sources/fred.py)).

Validated against the published record (NFP, first prints):

| Ref period | Naive diff of first prints | This pipeline | BLS actually reported |
|---|---|---|---|
| Jan 2024 | +468k | **+353k** | +353k ✓ |
| Feb 2024 | +108k | **+275k** | +275k ✓ |
| Mar 2024 | +325k | **+303k** | +303k ✓ |

A second vintage trap, caught and handled: a series' ALFRED vintages only exist
from the day it was **added to FRED** — for the SAAR GDP series that was
2014-09-26, meaning 20 earlier quarters shared one fake "release date" and a
revised value masquerading as a first print. The FRED client now drops that
backfill signature generically, and GDP study rows are built instead from the
**Atlanta Fed's own track record** of advance estimates and release dates
(verified equal to ALFRED prints on every overlapping post-2014 quarter).

### Surprises are standardized and sign-adjusted

- `raw = actual − consensus` (not comparable across indicators)
- `z = raw / forecast dispersion` — with a documented fallback to the historical stdev
  of raw surprises when dispersion is unavailable
- A per-indicator `yield_sign` (+1/−1) makes aggregation macro-meaningful: higher
  CPI/NFP/GDP pushes yields **up**, higher unemployment/claims pushes them **down**

### The gotchas are handled explicitly, not skipped

| Gotcha | Treatment |
|---|---|
| FOMC surprise ≠ target change | The surprise is the component *unexpected by fed funds futures* (Kuttner-style). FOMC stays **inactive** until that construction is implemented — a raw target change is never counted as a full surprise. |
| NFP + Unemployment co-release | Same 08:30 ET timestamp, entangled yield impacts — flagged in the registry; the regression design must not attribute one move to two indicators. |
| ISM PMI licensing | ISM data is not cleanly redistributable via FRED. Both ISM indicators ship **inactive**; S&P Global PMI is a *different* survey and is never spliced in. |
| Timestamps | All release datetimes stored in ET (08:30 for most, 10:00 ISM, 14:00 FOMC). Free H.15 curve data is daily close — the event window works within that constraint and says so. |

---

## Pipeline

```
FRED/ALFRED (first-print vintages, Treasury curve)      Bloomberg ECO export (optional, offline)
        │                                                │
        ▼                                                ▼
   normalize ──► releases (per event) + curve (date × tenor)          [SQLite]
        │
        ▼
   surprise: raw = actual − consensus ; z = raw / dispersion
        │
        ▼
   curve reaction: Δ over event window → level / 2s10s / 5s30s / curvature
        │
        ▼
   surprise betas: OLS of curve change on z, per indicator, by Fed regime
        │
        ▼
   findings writeup (2–3 results + charts + methodology + limitations)   ◄── THE DELIVERABLE
        │
        ▼
   Streamlit app (optional read-only demo of precomputed results)
```

## Data

### Sources — all free and ToS-clean (no Bloomberg dependency)

| Source | Provides | Mode |
|---|---|---|
| **FRED/ALFRED** (`fredapi`) | Actuals (first-print *and* latest vintages), Treasury curve (`DGS2/5/10/30`, more available) | Live API, free key |
| **Cleveland Fed inflation nowcast** | CPI & PCE MoM expectations — daily nowcast evolution per month since 2013-07, cut strictly before each release | Public chart feed (JSON) |
| **Atlanta Fed GDPNow** | Final pre-release model forecast per quarter since 2011Q3, plus the recorded advance estimate & release date | Public tracking workbook (XLSX) |
| **Naive proxy** | Consensus = previous as-reported value (the "no-change" forecast). Always available; permanent baseline to compare real consensus against | Derived |
| **Manual CSV** (`ConsensusCsvSource`) | Any hand-collected public consensus (news-wire recaps, SPF tables) — the revival path for removed indicators | Offline import |

The Fed nowcasts are **model nowcasts, not survey medians** — a documented
substitute for vendor consensus, framed as such in the methodology. Neither
provides forecast dispersion, so standardized surprises use the historical-stdev
fallback. Consensus provenance is encoded in `releases.source`
(`fred_first+naive_prev`, `fred_first+cleveland_fed`, `gdpnow_track`), so
baseline and real-consensus rows coexist and can be compared.

> Data whose provenance/license forbids committing belongs under `data/private/`
> (gitignored).

### Indicators

| Key | Series (actual) | Quoted as | Yield sign | Status |
|---|---|---|---|---|
| CPI | `CPIAUCSL` | % m/m | +1 | **active** — Cleveland Fed consensus (2013-08+) |
| PCE | `PCEPI` | % m/m | +1 | **active** — Cleveland Fed consensus (2013-07+) |
| GDP | advance estimate (Atlanta Fed track record) | % q/q SAAR | +1 | **active** — GDPNow consensus (2011Q3+) |
| NFP | `PAYEMS` | Δ level, k | +1 | **removed** — no public per-release consensus |
| UNRATE | `UNRATE` | % | −1 | **removed** — same |
| RETAIL | `RSAFS` | % m/m | +1 | **removed** — same |
| CLAIMS | `ICSA` | level | −1 | **removed** — same |
| FOMC | `DFEDTARU` | target | +1 | **inactive** until futures-based surprise exists |
| ISM_MFG / ISM_SRV | — | index | +1 | **inactive** (licensing) |

Removed ≠ deleted: survey consensus for NFP/UNRATE/Retail/Claims exists only
behind vendors or scraping-prohibited calendar sites. Any of them revives by
importing hand-collected public figures through `ConsensusCsvSource`.

### Current inventory (July 2026)

| Indicator | Baseline rows (naive, 2000+) | Real-consensus rows |
|---|---|---|
| CPI | 316 | 153 (Cleveland Fed, 2013-08 →) |
| PCE | 310 | 155 (Cleveland Fed, 2013-07 →) |
| GDP | 47 (post-2014 vintages only) | 59 (GDPNow track record, 2011Q3 →) |

Plus 26,500+ curve points (2Y/5Y/10Y/30Y daily closes, 2000 →). Refreshed by
re-running the ingest; upserts are idempotent.

### Schema (SQLite, `data/event_study.db`)

| Table | Contents |
|---|---|
| `indicators` | Registry: key, FRED series, transform, `yield_sign`, ET release time, active flag |
| `releases` | One row per (indicator, ref period, provenance): actual, consensus, dispersion, previous, `is_first_print`, release datetime (ET) |
| `curve` | date × tenor × yield (percent, H.15 daily close) |
| `event_impacts` | Per release + window label: pre/post yields, Δ level / 2s10s / 5s30s / curvature in **bps** (populated by the event study) |

---

## Getting started

Requires Python 3.11+.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` (gitignored) with a free [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html):

```bash
FRED_API_KEY=your_key_here
# macOS python.org builds only — point ssl at certifi if you see
# CERTIFICATE_VERIFY_FAILED:
SSL_CERT_FILE=/path/to/repo/.venv/lib/python3.13/site-packages/certifi/cacert.pem
```

### Ingest

```bash
export $(grep -v '^#' .env | xargs)
python -m src.ingest.run_ingest --vintage first --start 2000-01-01
```

`--vintage` is **required, with no default — by design**:

- `first` — ALFRED first prints: what the market's surprise was actually judged against
- `latest` — today's revised values: useful for comparison, corrupting for surprises

Which one counts as "the actual" is an analytical decision, so the tooling forces it to
be made explicitly on every run. Both vintages can coexist in the DB (distinguished by
`source` / `is_first_print`).

Useful flags: `--indicators CPI NFP` (subset), `--skip-curve`, `--skip-releases`,
`--db path.db`.

### Tests

```bash
pytest        # 51 tests, all offline (fake FRED client, temp DBs)
```

Coverage includes the same-vintage rule (same-report revisions used, later revisions
excluded), vintage selection, upsert idempotency, curve math against hand-computed
values, the Bloomberg CSV contract, and registry sanity (signs, gotcha indicators
staying inactive).

### App (optional demo layer)

```bash
streamlit run src/app/app.py
```

Read-only over the committed DB: findings page, curve/shape explorer, releases browser.
Deliberately thin — no calendars, no countdowns; the writeup is the product.

---

## Automation (GitHub Actions)

[`.github/workflows/ingest.yml`](.github/workflows/ingest.yml) refreshes the data and
commits the updated SQLite DB back to the repo — the Action is the backend; the app
only ever reads.

Setup:

1. Add a repo secret **`FRED_API_KEY`**.
2. Run it manually: *Actions → ingest → Run workflow* — the `vintage` input is required
   (same reasoning as the CLI).
3. The cron schedule is committed but **commented out** until the vintage policy is
   settled; enabling it means hard-coding the chosen `--vintage` in the run step.

Hosting note: Streamlit Community Cloud has an ephemeral filesystem and sleeping apps —
hence the read-only + Actions-commit pattern. It can deploy from a private repo with
broader GitHub scope; Hugging Face Spaces / Render / Railway are alternatives with
persistent disk.

---

## Repository layout

```
├── CLAUDE.md                 # working doctrine: division of labor, gotchas, decisions
├── README.md
├── analysis/
│   ├── findings.md           # THE DELIVERABLE (in progress)
│   └── figures/
├── data/
│   └── event_study.db        # committed SQLite (refreshed by Actions)
├── src/
│   ├── config.py             # paths, ET timezone, indicator registry
│   ├── models.py             # SQLAlchemy schema (4 tables)
│   ├── db.py                 # engine/session helpers, registry seeding
│   ├── charts.py             # Plotly helpers (CVD-validated palette)
│   ├── sources/
│   │   ├── base.py           # DataSource ABC + normalized Release
│   │   ├── fred.py           # FRED/ALFRED client: vintages, same-vintage rule, backfill guard
│   │   ├── consensus.py      # ConsensusProvider protocol + overlay
│   │   ├── cleveland_fed.py  # CPI/PCE nowcast consensus (public JSON feed)
│   │   ├── gdpnow.py         # GDP consensus + authoritative advance-release rows
│   │   ├── naive.py          # consensus = previous (baseline proxy)
│   │   └── consensus_csv.py  # manual public-consensus importer (revival path)
│   ├── ingest/run_ingest.py  # CLI (requires --vintage)
│   ├── analytics/
│   │   ├── curve.py          # level / 2s10s / 5s30s / curvature math
│   │   ├── surprise.py       # surprise construction        [stub — see status]
│   │   └── event_study.py    # windows, impacts, betas      [stub — see status]
│   └── app/app.py            # Streamlit shell (read-only)
├── tests/                    # 51 offline tests
└── .github/workflows/ingest.yml
```

## Status & roadmap

| # | Step | State |
|---|---|---|
| 1 | Schema, DB, `DataSource` interface, FRED/ALFRED client | ✅ done |
| 2 | First-print actuals + curve ingested; naive consensus baseline | ✅ done (2000→present) |
| 3 | Public real consensus (Cleveland Fed nowcast, GDPNow) integrated | ✅ done (replaces Bloomberg) |
| 4 | Surprise + standardized surprise | 🔶 next — `src/analytics/surprise.py` |
| 5 | Event windows, curve deltas, betas by regime | 🔶 stubbed — `src/analytics/event_study.py` |
| 6 | Findings writeup (2–3 results, methodology, limitations) | 🔶 skeleton — `analysis/findings.md` |
| 7 | Streamlit demo + scheduled ingest | ✅ shell + workflow ready (cron pending vintage policy) |

## Division of labor

This repo is built with AI assistance under an explicit split, documented in
[`CLAUDE.md`](CLAUDE.md): **tooling and plumbing are scaffolded (schema, API clients,
ingest, tests, app shell); every analytical judgment is made and implemented by the
author** — the vintage policy, the FOMC surprise construction, event-window and
decomposition choices, the regression specification, and all interpretation. The
stubs in `src/analytics/` raise `NotImplementedError` until those decisions are made,
and the test suite asserts they stay that way.

## Known limitations (previewed; full treatment in the findings)

- Daily H.15 closes mean the event window brackets the whole release day, not the
  release minute — intraday futures would tighten this.
- The "consensus" for CPI/PCE/GDP is a **Fed model nowcast, not a survey median** —
  a documented substitute after Bloomberg access ended. No forecast dispersion, so
  standardization uses the historical stdev of raw surprises.
- Real-consensus samples are shorter than the actuals history: CPI/PCE from
  2013, GDP from 2011 — small samples per (indicator × regime) cell; betas ship
  with error bars, not just point estimates.
- The study set is three indicators; the labor-market complex (NFP, claims) is
  absent until public consensus is hand-collected for it.
- Published prints are rounded (CPI to 0.1pp); stored values carry full precision —
  the precision policy for surprises is an open, documented decision.
