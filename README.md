# Treasury Curve Event Study

**How do macro surprises move the shape of the US Treasury yield curve?**

For CPI, PCE and GDP releases, I measure the one-day response of four curve
factors — level (10Y), 2s10s slope, 5s30s slope, curvature (2×10Y − 2Y − 30Y) —
to the *standardized surprise* in the print, using first-print data and free
public consensus. The writeup is [`analysis/findings.md`](analysis/findings.md);
the Streamlit app is a demo layer over the precomputed results.

## Methodology (implemented in `src/analytics/`)

For each indicator × factor, on release days, with surprise
`S = (actual − consensus) / σ(actual − consensus)` and ΔF the close-over-close
factor change across the release (bps):

1. **Baseline** — `ΔF = α + β·S + ε`; β is the curve response in bps per 1σ
   surprise, reported with R².
2. **Asymmetry** — `ΔF = α + β⁺·max(S,0) + β⁻·min(S,0) + ε`, with a Wald test
   of β⁺ = β⁻.
3. **Nowcast vs naive** — the baseline re-estimated under both expectation
   measures (Fed nowcast vs previous-value random walk) on **matched release
   days**; comparing β and R² tests whether the market prices the genuinely
   unexpected component.
4. **Event study** — cumulative abnormal factor changes from 5 days before to
   10 days after top/bottom-decile surprises, benchmarked against the mean
   release-day change on non-extreme releases.
5. **Trading-oriented tests** — betas re-estimated pre/post the 2021 inflation
   era; release-day vs ordinary-day volatility per indicator; and an ex-ante
   check that the *public* nowcast is already priced by the prior close
   (position on nowcast−previous at t−1 close, exit at t close: hit rate and
   bps per trade).

All regressions are per indicator (never pooled) with White
heteroskedasticity-robust standard errors (HC1).

## Data

| What | Source |
|---|---|
| Actuals (first prints) | FRED/[ALFRED](https://alfred.stlouisfed.org/) vintage archives: [CPIAUCSL](https://fred.stlouisfed.org/series/CPIAUCSL), [PCEPI](https://fred.stlouisfed.org/series/PCEPI); GDP advance estimates from the Atlanta Fed track record |
| Consensus — CPI, PCE | [Cleveland Fed inflation nowcast](https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting), last value strictly before each release (2013-07 →) |
| Consensus — GDP | [Atlanta Fed GDPNow](https://www.atlantafed.org/cqer/research/gdpnow), final pre-release forecast (2011Q3 →) |
| Consensus — baseline | Naive proxy: expectation = previous as-reported print |
| Treasury curve | FRED `DGS2/5/10/30` (Fed [H.15](https://www.federalreserve.gov/releases/h15/) daily closes, 2000 →) |

Vintage rigor, verified against published prints:

- **Same-vintage rule.** MoM changes are computed against the prior month *as
  revised in the same report*, not the prior first print (diff-of-first-prints
  can miss the reported headline badly — e.g. +108k vs the actual +275k Feb-2024
  NFP print during validation).
- **Series-inception guard.** ALFRED "vintages" that predate a series' addition
  to FRED are revisions with fake release dates; the client drops that backfill
  signature, and GDP rows come from the Atlanta Fed record (which matches ALFRED
  on every overlapping quarter).

Consensus here is a **Fed model nowcast, not a survey median**, and carries no
dispersion — standardization uses the historical stdev of raw surprises.
Column-by-column provenance with links: [`data/exports/DATA_DICTIONARY.md`](data/exports/DATA_DICTIONARY.md).

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo "FRED_API_KEY=<free key from fred.stlouisfed.org>" > .env

export $(grep -v '^#' .env | xargs)
python -m src.ingest.run_ingest --vintage first   # data  (vintage is an explicit choice)
python -m src.analytics.run_analysis              # results -> analysis_* tables
python -m src.ingest.export_csv                   # audit CSVs -> data/exports/
streamlit run src/app/app.py                      # results explorer
pytest                                            # offline test suite
```

The GitHub Actions workflow (`.github/workflows/ingest.yml`, manual dispatch)
refreshes data, recomputes results, and commits the DB — the app only reads.
Requires a `FRED_API_KEY` repo secret.

## Layout

```
analysis/findings.md      the writeup (in progress)
data/event_study.db       committed SQLite: raw tables + analysis_* results
data/exports/             audit CSVs + DATA_DICTIONARY.md
src/sources/              FRED/ALFRED client, Cleveland Fed + GDPNow consensus,
                          naive proxy, manual-CSV importer (DataSource interface)
src/analytics/            surprise.py, event_study.py, run_analysis.py, curve.py
src/app/app.py            read-only Streamlit demo (Results / Curve / Releases)
src/charts.py             Plotly helpers (CVD-validated palette)
tests/                    75 offline tests
```

## Limitations

- Daily H.15 closes: the release-day window contains the 08:30 ET print but
  also everything else that day.
- Consensus is a model nowcast, not a survey; no dispersion available.
- Samples: CPI/PCE from 2013, GDP from 2011 — small cells, so every coefficient
  ships with robust standard errors and n.
- Three indicators; the labor complex (NFP, claims) is out until public
  consensus is hand-collected for it (`ConsensusCsvSource` is the import path).
- Stored values are full precision; published prints are rounded to 0.1.
