# How Macro Surprises Move the Shape of the Treasury Curve

<!-- Drafted from the computed results in data/event_study.db (analysis_* tables,
     July 2026 run). The author edits and owns every claim before publishing. -->

## TL;DR

- Since 2021, a one standard deviation CPI surprise (about 0.15pp on monthly
  headline) moves the whole curve about 2.3bp and flattens 5s30s by about
  1.7bp on the day, and the surprise explains roughly 15% of the release-day
  move. Before 2021 the same regression finds nothing. The CPI beta is a
  regime object, not a constant.
- The event premium is CPI-specific. Post-2021 CPI days run 1.4x the volatility
  of ordinary days in the curve level. Advance GDP days are indistinguishable
  from ordinary days, and PCE days are actually quieter than ordinary days.
  If you pay for optionality into an event, this says which event.
- There is no free lunch in public forecasts. A rule that positions at the
  prior close in the direction of (public nowcast minus previous print) earns
  roughly zero gross (hit rate 46% on the level, −0.6bp per trade). The
  market has the public information priced before the release; the only
  tradable object is the residual surprise at 8:30:00, which is a speed and
  information game, not an analysis game.

## Finding 1: the CPI trade is a bear-flattener through the long end, and it lives in the inflation era

Full sample (n = 153 monthly releases, 2013-2026), per one standard deviation
of CPI surprise on the release day:

| Factor | beta (bps/1σ) | 95% CI | p | R² |
|---|---|---|---|---|
| Level (10Y) | +2.0 | [+0.8, +3.1] | 0.001 | 0.098 |
| 2s10s | −0.5 | [−1.4, +0.4] | 0.287 | 0.013 |
| 5s30s | −1.3 | [−2.1, −0.5] | 0.001 | 0.087 |
| Curvature | +0.0 | [−0.8, +0.8] | 0.966 | 0.000 |

Two features matter for expression. First, the flattening is in 5s30s, not
2s10s: the belly sells off with the front end and the 30Y anchors. A CPI
surprise view expressed as a 2s10s flattener was the wrong trade in this
sample; the long-end slope or outright duration carried the signal. Second,
the response is not stable over time:

| Era | Level beta | p | R² | 5s30s beta | p | R² | n |
|---|---|---|---|---|---|---|---|
| 2013-2020 | +1.0 | 0.14 | 0.02 | −0.3 | 0.59 | 0.00 | 88 |
| 2021-2026 | +2.3 | 0.004 | 0.14 | −1.7 | 0.001 | 0.15 | 65 |

Pre-2021, CPI surprises did not significantly move the curve at a daily
horizon. Everything in the full-sample result is carried by the inflation
era, when the Fed's reaction function made each print a policy input. For
sizing, the post-2021 numbers are the relevant ones; for humility, the
pre-2021 rows are a reminder that this beta can go back to zero when
inflation stops being the binding concern.

The event study (top and bottom surprise deciles, 16 events per tail) places
the response on the release day itself: hot prints jump the level about
+4.8bp and 5s30s about −3.0bp on day 0 versus the control-day benchmark,
cold prints do roughly the mirror image, and the paths before and after stay
within noise for a 16-event average. There is no reliable post-print drift
to chase. Asymmetry point estimates say soft prints move the level more than
hot ones (3.4 vs 1.1 bps/1σ), but the difference is not statistically
distinguishable (Wald p = 0.24).

## Finding 2: CPI is the only one of these events the curve prices as an event

Standard deviation of the daily curve-level change on release days versus all
non-release trading days, in bps:

| Event | Window | Release-day sd | Ordinary-day sd | Ratio |
|---|---|---|---|---|
| CPI | post-2021 | 8.1 | 6.0 | 1.37 |
| CPI | full sample | 6.3 | 5.8 | 1.08 |
| GDP advance | full sample | 5.8 | 5.8 | 1.00 |
| PCE | full sample | 4.9 | 5.8 | 0.84 |

Post-2021 CPI days are materially higher-volatility days for the curve.
Advance GDP day is an ordinary day: the print is well nowcast in public
(GDPNow) and the quarter is old news by release. PCE days are quieter than
ordinary days, which is what you would expect when one sigma of PCE surprise
is 0.07pp (half the CPI figure) because CPI three weeks earlier already
pinned the month's inflation.

The regression evidence agrees: PCE surprises move only 2s10s and only
marginally (−0.5bp per sigma, p = 0.03), GDP shows no linear response on any
factor (all p > 0.7). The one suggestive GDP pattern is asymmetric, with
upside growth surprises steepening 2s10s (+3.4bp per sigma of upside, Wald
p = 0.005 against equal slopes), but with 59 quarterly events I flag it as
suggestive only.

The direct reading for an options or gamma book: the calendar premium belongs
on CPI day and, in this sample, was not earned back on PCE or advance GDP
days.

## Finding 3: the public nowcast is already in the price by the prior close

The Cleveland Fed nowcast and GDPNow are public before the release, so a
natural question is whether the market leaves any of that information on the
table. I test the cheapest possible rule: at the close before the release,
position in the direction of (nowcast minus previous print), exit at the
release-day close. Everything in the signal is public before the print, and
the accounting (close to close) is exactly what daily data measures honestly.

| Signal on | Factor | n | Hit rate | Gross bps/trade | t |
|---|---|---|---|---|---|
| CPI gap | Level | 153 | 0.46 | −0.60 | −1.2 |
| CPI gap | 5s30s | 153 | 0.50 | +0.10 | +0.3 |
| PCE gap | Level | 155 | 0.41 | +0.01 | +0.0 |
| GDP gap | Level | 58 | 0.50 | −0.17 | −0.2 |

Nothing survives. Hit rates sit at or below a coin flip and gross P&L per
trade is zero to negative before costs (of 12 indicator-factor cells, one
shows p < 0.01 with negative P&L, which I read as multiple-testing noise).
The market prices the public nowcast by the prior close.

This null is the practical content of the expectation-measure comparison: the
same regressions run against the nowcast explain up to twenty times more
release-day variance than against a naive random walk (CPI level R² 0.098 vs
0.005), so the market's effective expectation is at least as good as the
public nowcast, and the nowcast is not better than the market. Both facts
point the same way: the tradable object is the residual surprise at
8:30:00.000, and capturing it is a latency and positioning problem, not a
forecasting-from-free-data problem.

## Methodology

I measure the response of the yield curve to a surprise by regressing the
change in each curve factor around a release on the standardized surprise for
that release. For a release on date d, the response is the one-day change in
the factor across the release, F(d) − F(d−1) in trading days, where F is the
level (10Y), the 2s10s slope (10Y − 2Y), the 5s30s slope (30Y − 5Y), or the
curvature (2×10Y − 2Y − 30Y). Because the curve data are daily closes and the
releases print at 08:30 ET, this one-day window contains the release. Curve
factors are in percentage points and I report coefficients in basis points
per one standard deviation of surprise.

### Data and vintages

Actuals are first prints. CPI and PCE come from ALFRED vintage archives with
month-over-month changes computed against the prior month as revised in the
same report, which reproduces the as-published headline. Advance GDP prints
and their release dates come from the Atlanta Fed's GDPNow track record,
because the SAAR series on FRED has no true vintages before September 2014.
The curve is Fed H.15 constant-maturity closes (2Y, 5Y, 10Y, 30Y).

### Surprise construction

The raw surprise is actual minus expectation. The standardized surprise
divides by the sample standard deviation of the raw surprise per indicator
and expectation measure (no public source provides forecast dispersion).
Expectations come in two forms: the nowcast (Cleveland Fed inflation nowcast
for CPI and PCE, cut strictly before each release; the final pre-release
GDPNow forecast for GDP) and the naive random walk (expectation = previous
as-reported print). These are model nowcasts, not survey medians, and I frame
every result accordingly.

### 3.1 Baseline specification

For each indicator and each curve factor I estimate

ΔF(d) = α + β·Surprise(d) + ε(d)     (1)

on release days only, so β is the average curve response to a one standard
deviation surprise. I report R² alongside each coefficient, since it measures
how much of the release-day move is attributable to the surprise component.

### 3.2 Asymmetric effects

ΔF(d) = α + β⁺·Surprise⁺(d) + β⁻·Surprise⁻(d) + ε(d)     (2)

with Surprise⁺ = max(0, S) and Surprise⁻ = min(0, S). A difference between β⁺
and β⁻ (robust Wald test) indicates the curve reacts more strongly to hot
prints than cold ones, or the reverse.

### 3.3 Nowcast versus naive expectations

I re-estimate (1) with each expectation measure and compare coefficients and
R². To keep the comparison about expectation quality rather than sample
period, the naive regressions run on the same release days as the nowcast
sample (matched samples).

### 3.4 Event study

Surprise days are releases in the top and bottom deciles of the standardized
surprise per indicator; control days are the remaining releases. The abnormal
change is the realized daily change minus the mean release-day change on
control days, cumulated from five trading days before to ten after the
release. A response concentrated on the release day is consistent with
efficient pricing; drift afterwards would suggest delayed adjustment.

### 3.5 Era conditioning

I re-estimate (1) on releases before and after 2021-01-01, a single disclosed
cutoff chosen as the start of the post-pandemic inflation episode. A beta
concentrated in one era is a sizing statement, not a constant of nature.

### 3.6 Event-day volatility

For each indicator I compare the standard deviation and mean absolute value
of each factor's daily change on that indicator's release days against all
trading days that host none of the three releases. This asks whether the day
is an event at all, independently of any expectation measure.

### 3.7 Ex-ante gap test

gap(d) = nowcast(d) − previous print, standardized per indicator, is public
before the release. I regress ΔF(d) on the standardized gap and score the
rule "position in the direction of the gap at the prior close, exit at the
release-day close" by hit rate and mean gross bps per trade. A significant
edge would mean the market underweights free public information.

All regressions use heteroskedasticity-robust standard errors (White 1980,
HC1 finite-sample variant) and are estimated separately by indicator, never
pooled.

## Limitations

- Daily close data. The one-day window contains the 08:30 ET print and
  everything else that happened that day. Intraday futures would isolate the
  release; with daily data the betas are a lower bound on signal-to-noise.
- The expectation is a model nowcast, not a survey median, and provides no
  dispersion. Standardization (and the gap scaling) uses full-sample stdev,
  which peeks ahead mildly relative to a real-time rolling version. The gap
  rule's sign, which drives the hit rate and P&L, does not depend on the
  scaling.
- Samples are short: 153 CPI months, 155 PCE months, 59 GDP quarters, 65
  post-2021 CPI months, 16 events per tail in the event study. Every estimate
  ships with robust standard errors and n.
- The era cutoff (2021-01-01) is one disclosed choice, not searched over; the
  contrast is large enough that nearby cutoffs tell the same story, but a
  formal break test is future work.
- Reported tables span 12 indicator-factor cells per exercise, so isolated
  p < 0.01 cells (like PCE curvature in the gap test) should be read against
  the number of comparisons.
- Release days can host other news (weekly claims print most Thursdays, PCE
  arrives inside the income-and-outlays release), so single-indicator betas
  attribute the whole day to one surprise.
- No transaction costs are modeled; for the gap rule this does not matter
  because gross P&L is already zero to negative. The three indicators here
  exclude the labor complex, for which no license-clean public consensus
  archive exists.

## Reproduction

```bash
export FRED_API_KEY=...
python -m src.ingest.run_ingest --vintage first --start 2000-01-01
python -m src.analytics.run_analysis
python -m src.ingest.export_csv   # audit CSVs + data dictionary
```

Results land in the analysis_* tables of data/event_study.db (baseline,
asymmetry, event_study, era, event_vol, gap_trade) and render in the
Streamlit app's Results tab. Data provenance, column by column with links:
data/exports/DATA_DICTIONARY.md.
