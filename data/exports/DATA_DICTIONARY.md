# Data dictionary & provenance — audit reference

Companion to `releases.csv` and `curve.csv` (regenerate both anytime with
`python -m src.ingest.export_csv`). Every value in the exports is traceable to
a free public source listed below. Ingested with `--vintage first`.

**Reconciling against published headlines:** stored values carry full
precision; official prints are rounded. Round `actual` to **1 decimal** and it
must match the headline (CPI/PCE MoM %, GDP SAAR %). If it doesn't, that's a
finding — flag it.

---

## releases.csv

One row per (indicator × reference period × provenance). The same period
appears once per `source` value — that's by design, so the naive baseline and
the real consensus can be compared row by row.

### Columns

| Column | Meaning | Where the value comes from |
|---|---|---|
| `indicator` | Registry key | `src/config.py` registry (CPI, PCE, GDP) |
| `units` | Units of `actual`/`consensus`/`previous` | Registry: `% m/m` (CPI, PCE), `% q/q saar` (GDP) |
| `ref_period` | Period the data describes | FRED observation-date convention: month start (CPI/PCE), quarter start (GDP) |
| `release_datetime` | When the print hit the tape, **ET-naive** | Date: per-source (below). Time-of-day: registry convention — 08:30 ET for CPI ([BLS schedule](https://www.bls.gov/schedule/news_release/cpi.htm)), PCE and GDP ([BEA schedule](https://www.bea.gov/news/schedule)). Intraday times are NOT in any vintage archive — this is a documented convention, not data. |
| `actual` | The first-print value of the quoted number | Per-source, below |
| `consensus` | Pre-release expectation | Per-source, below |
| `consensus_stdev` | Forecast dispersion | **Always empty** — no free public source publishes dispersion. Standardized surprises must use the historical-stdev fallback. |
| `n_estimates` | Survey size | **Always empty** — same reason. |
| `previous` | Prior period's value as the market last saw it | Derived: the prior period's own as-reported first print (see per-source notes) |
| `is_first_print` | Actual is a first print, not a revision | All `1` in this export (`--vintage first`); the FRED client also drops pre-inception backfill that would fake this flag |
| `source` | Provenance of (actual + consensus) | One of three values, documented below |

### Provenance by `source` value

#### 1. `fred_first+naive_prev` — baseline rows (CPI, PCE, GDP)

- **actual** — first-print value from full ALFRED vintage archives, fetched via
  the [FRED API](https://fred.stlouisfed.org/docs/api/fred/) (`fredapi`,
  all-releases endpoint). Underlying series:
  - CPI: [CPIAUCSL on FRED](https://fred.stlouisfed.org/series/CPIAUCSL) · [vintages on ALFRED](https://alfred.stlouisfed.org/series?seid=CPIAUCSL)
  - PCE: [PCEPI on FRED](https://fred.stlouisfed.org/series/PCEPI) · [vintages on ALFRED](https://alfred.stlouisfed.org/series?seid=PCEPI)
  - GDP: [A191RL1Q225SBEA on FRED](https://fred.stlouisfed.org/series/A191RL1Q225SBEA) · [vintages on ALFRED](https://alfred.stlouisfed.org/series?seid=A191RL1Q225SBEA)
- **Transform (CPI/PCE):** `actual = 100 × (index_M / index_{M−1} − 1)`, where
  `index_M` is month M's **first print** and `index_{M−1}` is the prior month
  **as revised in the same report** (ALFRED as-of lookup on the release date —
  the "same-vintage rule"; reproduces the as-published MoM %). GDP: the series
  already is the published SAAR %, no transform.
- **consensus** — equals `previous` (the "no-change" proxy). Not an external
  source; it is the permanent baseline the real consensus is judged against.
- **previous** — prior period's as-reported first print (shift of `actual`).
- **release date** — ALFRED `realtime_start` of the period's first vintage
  (= publication date). Verify any row on its ALFRED page above.
- **Caveats:** GDP baseline rows exist only from 2014Q3 (the SAAR series was
  added to FRED 2014-09-26; earlier "vintages" are fakes and are dropped —
  GDP study rows use the Atlanta Fed record instead). PCE baseline starts
  2000-08 for the same reason (PCEPI vintage coverage).

#### 2. `fred_first+cleveland_fed` — CPI & PCE study rows (2013-07 →)

- **actual / previous / release date** — same as №1 (ALFRED first prints).
- **consensus** — Federal Reserve Bank of Cleveland **inflation nowcast**:
  - Methodology & charts: <https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting>
  - Exact machine feed ingested: <https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_month.json>
    (the JSON behind their monthly chart: daily nowcast values per reference
    month since 2013-07, with release-day markers and "Actual" series)
  - Rule: the **last nowcast value strictly before the release cutoff** — the
    own-month marker or the first "Actual" value, whichever is earlier. The
    feed's nowcast series stop before the release; no post-release value can
    be selected. Verify any month by opening the chart for that month on the
    page above and reading the last plotted nowcast before the release.
  - Model reference: [Knotek & Zaman, "Nowcasting U.S. Headline and Core Inflation" (Cleveland Fed WP 14-03)](https://www.clevelandfed.org/publications/working-paper/2014/wp-1403-nowcasting-us-headline-and-core-inflation)
- **Caveat:** a model nowcast, **not** a survey median. PCE consensus values
  legitimately incorporate that month's already-released CPI (so does any
  market PCE expectation).

#### 3. `gdpnow_track` — GDP study rows (2011Q3 →)

Entire row from the Federal Reserve Bank of Atlanta **GDPNow** record:

- Project page: <https://www.atlantafed.org/cqer/research/gdpnow>
- Exact file ingested: <https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/cqer/researchcq/gdpnow/GDPTrackingModelDataAndForecasts.xlsx>
  — sheet **`TrackRecord`**, first four columns:
  | Sheet column | Export column |
  |---|---|
  | "Quarter being forecast" (quarter-end date) | `ref_period` (mapped to quarter start) |
  | "Model Forecast Right Before Advance Estimate" | `consensus` |
  | "BEA's Advance Estimate" | `actual` |
  | "Release Date" | `release_datetime` (date part) |
- **previous** — the prior quarter's advance estimate from the same sheet.
- **Why not ALFRED for GDP:** the SAAR series has no true vintages before
  2014-09-26. On every overlapping post-2014 quarter, this sheet's advance
  estimate equals the ALFRED first print (validated in-pipeline).
- Independent cross-checks: [BEA GDP releases](https://www.bea.gov/data/gdp/gross-domestic-product)
  (advance-estimate news releases and dates).

### Independent verification sources (not used by the pipeline)

- CPI headline archive: [BLS CPI news releases](https://www.bls.gov/bls/news-release/cpi.htm)
- PCE price index: [BEA Personal Income releases](https://www.bea.gov/data/income-saving/personal-income) · [PCE price index page](https://www.bea.gov/data/personal-consumption-expenditures-price-index)
- GDP advance estimates: [BEA GDP news release archive](https://www.bea.gov/data/gdp/gross-domestic-product)

---

## curve.csv

Wide format: one row per market date, one column per tenor. Values are
**percent** (e.g. `4.48` = 4.48%), constant-maturity, daily close. Missing
cells = market holidays.

| Column | Series | Source |
|---|---|---|
| `date` | Observation date | — |
| `2Y` | [DGS2](https://fred.stlouisfed.org/series/DGS2) | FRED mirror of Fed H.15 |
| `5Y` | [DGS5](https://fred.stlouisfed.org/series/DGS5) | FRED mirror of Fed H.15 |
| `10Y` | [DGS10](https://fred.stlouisfed.org/series/DGS10) | FRED mirror of Fed H.15 |
| `30Y` | [DGS30](https://fred.stlouisfed.org/series/DGS30) | FRED mirror of Fed H.15 |

Ultimate source: Federal Reserve **H.15 Selected Interest Rates**
(<https://www.federalreserve.gov/releases/h15/>), Treasury constant maturities,
business-day frequency. Independent cross-check:
[Treasury.gov daily yield curve rates](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve).
