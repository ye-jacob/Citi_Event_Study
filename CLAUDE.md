# CLAUDE.md

Project guidance for Claude Code. Read this fully before writing any code — especially
the **Division of labor** section, which defines what you should and should not build.

## What this project actually is

A **portfolio research piece** for a markets/rates audience. The deliverable that matters
is a **rigorous event-study writeup** — 2–3 defensible findings about how macro *surprises*
move the *shape* of the US Treasury yield curve, with clean charts, a methodology section,
and an honest limitations section.

A Streamlit app is a **secondary, optional demo layer** on top of the precomputed results —
"explore it yourself," a link, not the pitch. **Do not let the app become the center of
gravity.** If effort is drifting into countdown timers and calendar polish, that's the wrong
direction: those features replicate Trading Economics / Forex Factory and add nothing for
this audience.

The entire pipeline upstream of "Findings" exists to earn **one defensible sentence per
indicator**, e.g. *"A +1σ CPI surprise flattens 2s10s by ~4bps on average, and the effect
roughly doubles in a hiking regime versus on hold."*

### The edge (the only parts that differentiate this)
- **Curve-first lens.** Free calendars are built for FX/equity-vol traders and answer "did
  the market move." This answers "how does a surprise move curve *shape* (level / slope /
  curvature), conditional on regime." That specific question is the entire point.
- **Methodological rigor.** First-print data, futures-based FOMC surprise, co-release
  handling, stated error bars. These are the signals that separate someone who understands
  releases from someone who scraped a calendar.

## Division of labor (READ THIS — it governs how you work)

The human is building this to *show* competence to a rates audience. If Claude Code makes
the analytical decisions, the human can't defend them in an interview and the piece
backfires. So the split is strict:

**Claude Code builds the plumbing. The human makes every analytical judgment call.**

### Claude Code owns (build these freely)
- Repo scaffolding, env setup, project structure, `.gitignore`, requirements.
- The FRED/ALFRED API client and all data-fetching boilerplate.
- The SQLAlchemy schema and DB access layer (from the spec below).
- Charting/plotting utility functions and the Streamlit app shell.
- Tests, and the GitHub Actions ingest workflow.
- Data-source abstraction scaffolding (interfaces, the FRED and naive implementations).

### Human owns — DO NOT implement these without the human driving
Leave these decisions and their core implementation to the human. If a task touches one of
these, **scaffold the surrounding code, leave a clearly-marked `TODO(human)` stub, and stop.**
Explain the options and tradeoffs; do not pick for them.
- **The vintage / first-print decision** — which value counts as "the actual" for a surprise.
- **The FOMC surprise construction** — the fed-funds-futures approach vs. alternatives.
- **The event window definition** and the **curve decomposition** choices (which slopes,
  why slope/curvature over raw tenors).
- **The regression specification**, running it, and **interpreting** the coefficients.
- **The findings writeup and the limitations section.**

**Rule of thumb:** if you're about to write the surprise math, the regression setup, or any
prose interpreting results — stop and hand it to the human. If you're writing a FRED wrapper
or a Plotly helper — proceed.

## The pipeline

```
Raw data       FRED/ALFRED (actual vintages, Treasury curve)
               + public consensus: Cleveland Fed inflation nowcast (CPI/PCE),
                 Atlanta Fed GDPNow (advance GDP), manual CSV of public figures
      |
      v
Normalize      two tables — releases (per event) and curve (date x tenor)
      |
      v
Surprise       raw = actual - consensus ; standardized = raw / forecast dispersion
      |
      v
Curve          yield change in a window around each release, decomposed into
reaction       level / slope (2s10s, 5s30s) / curvature
      |
      v
Surprise beta  regress curve change on standardized surprise, per indicator,
               conditioned on regime (hiking / cutting / hold)
      |
      v
Findings       2-3 crisp results + charts + methodology + limitations   <-- THE DELIVERABLE
      |
      v
[optional] App Streamlit layer to explore the precomputed results
```

One-line summary: *pull first-print macro surprises and the Treasury curve, decompose the
curve into level/slope/curvature, estimate how much each 1σ surprise moves curve shape while
conditioning on the rate regime, then write up the findings — with an interactive Streamlit
layer on top.*

## Domain concepts (get these right)

**Surprise.** `raw = actual - consensus`. Not comparable across indicators. Always also
compute **standardized surprise** `z = (actual - consensus) / forecast_dispersion` (or, if
dispersion is unavailable, standardize by the historical stdev of that indicator's raw
surprise). Use standardized surprise everywhere you compare or aggregate across indicators.

**Directionality isn't universal.** A positive surprise isn't always "hawkish." Higher
CPI/PCE/NFP/GDP generally pushes yields up; higher unemployment / jobless claims generally
pushes them down. Store a per-indicator `yield_sign` (+1/−1) so anything aggregated is
macro-meaningful.

**Curve, not tenors.** The object of study is curve *shape*: level (10Y), slope
(2s10s = 10Y − 2Y; 5s30s), curvature (2×10Y − 2Y − 30Y). Report impacts on these.

**Event study.** For each release, measure the curve change over a window around the release
timestamp. The **surprise beta** is the OLS slope of (curve change) on (standardized
surprise) across all historical releases of that indicator, optionally split by regime.

**Composite surprise index.** If built, this is a z-scored aggregate of the indicators — it
is essentially Citi's Economic Surprise Index (CESI, 2003). **Frame it honestly in the
writeup as a CESI-like reconstruction used to validate the pipeline, never as an original
idea** — a rates reader will recognize it on sight.

## Indicators and FRED series

Frequency and the FRED series to use as the actual. **Starting points — the human verifies
each** (seasonal adjustment, headline vs. core, and matching the exact number consensus is
quoted against).

| # | Indicator | Freq | FRED series (starting point) | Notes |
|---|-----------|------|------------------------------|-------|
| 1 | FOMC / Fed Funds target | ~8×/yr | `DFEDTARU`, `DFEDTARL` | Surprise ≠ level change — human-owned, futures-based |
| 2 | CPI | Monthly | `CPIAUCSL` (headline SA), `CPILFESL` (core) | MoM and YoY both quoted |
| 3 | PCE | Monthly | `PCEPI`, `PCEPILFE` (core) | Core PCE is the Fed's target |
| 4 | Nonfarm Payrolls | Monthly | `PAYEMS` | Released value is MoM change in level |
| 5 | Unemployment Rate | Monthly | `UNRATE` | Co-released with NFP — see gotcha |
| 6 | Retail Sales | Monthly | `RSAFS`, `RSXFS` (ex-auto) | MoM change |
| 7 | GDP | Quarterly | `GDPC1` or `A191RL1Q225SBEA` | Advance / 2nd / 3rd estimates |
| 8 | ISM Manufacturing PMI | Monthly | ⚠️ not cleanly on FRED (licensing) | See gotcha; S&P Global PMI is a possible substitute |
| 9 | ISM Services PMI | Monthly | ⚠️ not cleanly on FRED (licensing) | Same |
| 10 | Initial Jobless Claims | Weekly | `ICSA` | Highest-frequency signal |

**Treasury curve (free on FRED):** `DGS2`, `DGS5`, `DGS10`, `DGS30` (plus `DGS3MO`, `DGS1`,
`DGS7`, `DGS20` as needed).

## Data-source abstraction

No analytics or UI code calls a vendor directly. Everything goes through a `DataSource`
interface so Bloomberg, FRED, and a naive proxy populate the same normalized schema.

```python
class DataSource(ABC):
    @abstractmethod
    def get_releases(self, indicator, start, end) -> list[Release]: ...
    # Release: date, indicator, actual, consensus, consensus_stdev,
    #          n_estimates, previous, is_first_print, source
    @abstractmethod
    def get_curve(self, start, end) -> pd.DataFrame: ...  # tenor cols, date index
```

Consensus sourcing (Bloomberg access ended 2026-07 — the project uses free,
ToS-clean public sources only), in order: (1) **Fed-published nowcasts** —
Cleveland Fed inflation nowcast for CPI/PCE (daily evolution per month since
2013-07, cut strictly pre-release) and Atlanta Fed GDPNow for the advance GDP
print (final pre-release forecast since 2011Q3). These are model nowcasts, not
survey medians, and carry no dispersion — the writeup frames them accordingly
and standardization falls back to historical surprise stdev. (2) **Manual CSV
import** (`ConsensusCsvSource`) — hand-collected public figures (news-wire
recaps, SPF tables); the revival path for indicators without a programmatic
source. (3) **Naive proxy** — expectation = previous value; always available,
permanent baseline to compare real consensus against.

**Study scope:** only indicators with a public consensus source are active —
CPI, PCE, GDP. NFP, UNRATE, Retail Sales and Jobless Claims are deactivated in
the registry (their survey consensus exists only behind vendors or
scraping-prohibited calendar sites); revive any of them via manual CSV.

## Data model (minimum)

- `indicators` — id, name, freq, fred_series, yield_sign, release_time
- `releases` — indicator_id, ref_period, release_datetime, actual, consensus,
  consensus_stdev, n_estimates, previous, is_first_print, source
- `curve` — date, tenor, yield
- `event_impacts` — release_id, pre/post window yields, curve deltas (level/slope/curv)

## Known gotchas (do not skip)

- **Vintage / first-print (human-owned).** The surprise was judged against the *first
  published print*, not today's revised value. Revised FRED data silently corrupts historical
  surprises. Use ALFRED / first-release vintages and store `is_first_print`. This is the
  clearest single signal of understanding data releases — the human decides and owns it.
- **Series-inception trap (discovered 2026-07).** ALFRED vintages exist only from the day a
  series was *added to FRED* — earlier observations' "first vintage" is a revision with a
  fake release date (the SAAR GDP series had 20 such quarters; PCEPI's first months too).
  The FRED client drops that backfill signature; GDP study rows come from the Atlanta Fed
  track record instead. Check vintage coverage before trusting any series' early history.
- **FOMC surprise is special (human-owned).** The surprise is the *unexpected* component vs.
  what fed-funds futures priced in, not the raw target change. Do not treat every rate change
  as a full surprise.
- **NFP + Unemployment co-release.** Both drop in the same report; their yield impacts are
  entangled. Don't attribute the whole move to one when estimating single-indicator betas.
- **ISM PMI licensing (#8, #9).** Restricted on FRED. Verify before building; S&P Global
  (Markit) PMIs are a different series — don't mix them with ISM history.
- **Timestamps.** US data is mostly 08:30 ET; ISM 10:00 ET; FOMC ~14:00 ET. Store all times
  in ET and define the pre/post window explicitly.
- **Small samples / overlapping windows / endogeneity.** State these in the limitations
  section. Honest error bars signal more maturity than any feature.

## Tech stack

> Change the stack by editing this section only — the analytics layer is presentation-agnostic.

Python 3.11+ · pandas, numpy · statsmodels (OLS betas), scipy · SQLite via SQLAlchemy ·
`fredapi` · Streamlit (demo only) · Plotly.

## Deployment (Streamlit)

Hosted Streamlit (Community Cloud) has an **ephemeral filesystem and apps sleep when idle**,
so the app can't write or persist a DB at runtime and can't run a scheduler. Pattern:

1. **GitHub Actions runs the ingest** on a cron, pulls FRED + precomputed analytics, and
   **commits the refreshed data** (SQLite or Parquet) back to the repo. The Action is the
   backend.
2. **The Streamlit app only reads** committed data, wrapped in `st.cache_data`. No writes.

Free Community Cloud requires a **public repo** (private works with broader GitHub scope).
All committed data is from free public sources (FRED/ALFRED, Cleveland Fed, Atlanta Fed),
so committing it is fine; anything whose provenance forbids redistribution goes under
`data/private/` (gitignored). Alternatives with persistent disk: Hugging Face Spaces,
Render, Railway.

## Project structure

```
.
├── CLAUDE.md
├── data/                     # committed Parquet/SQLite (gitignore if repo is public + Bloomberg data)
├── analysis/                 # THE DELIVERABLE — notebooks + writeup + charts
│   ├── findings.md
│   └── figures/
├── src/
│   ├── sources/              # base.py, fred.py, consensus.py, cleveland_fed.py,
│   │                         #   gdpnow.py, naive.py, consensus_csv.py
│   ├── ingest/
│   ├── analytics/            # surprise.py, curve.py, event_study.py  (human-owned core)
│   ├── models.py
│   └── app/                  # Streamlit (demo only)
├── .github/workflows/        # scheduled ingest-and-commit
└── tests/
```

## Build order (analysis-first)

1. Scaffolding: schema, SQLite, `DataSource` interface, FRED client. *(Claude Code)*
2. Load FRED actuals + Treasury curve; naive consensus proxy. *(Claude Code)*
3. **Surprise + standardized surprise.** *(human decides vintage handling; Claude Code stubs)*
4. **Event study: pre/post curve deltas, decomposition, betas by regime.** *(human-owned)*
5. **Findings writeup — 2–3 results, charts, methodology, limitations.** *(human-owned — the deliverable)*
6. Public real consensus: Cleveland Fed nowcast (CPI/PCE) + GDPNow (GDP), alongside the
   proxy baseline. *(done — Claude Code; manual CSVs revive removed indicators)*
7. *(Optional)* Streamlit demo over the precomputed results + Actions ingest. *(Claude Code)*
