# How Macro Surprises Move the Shape of the Treasury Curve

> **TODO(human): this entire document is the deliverable and is human-written.**
> The skeleton below only fixes the structure agreed in CLAUDE.md. Every claim,
> number, chart choice, and caveat is an analytical judgment the author must be
> able to defend in an interview — none of it is generated.

## TL;DR

<!-- TODO(human): 2–3 one-sentence findings, e.g.
     "A +1σ CPI surprise flattens 2s10s by ~X bps on average; the effect roughly
      doubles in a hiking regime versus on hold." -->

## Finding 1 — <title>

<!-- TODO(human): claim, chart (analysis/figures/), effect size with error bars,
     robustness note. -->

## Finding 2 — <title>

<!-- TODO(human) -->

## Finding 3 — <title> (optional)

<!-- TODO(human) -->

## Methodology

<!-- TODO(human): each subsection documents a decision YOU made. -->

### Data and vintages
<!-- TODO(human): first-print policy (ALFRED), why revised data corrupts surprises,
     consensus source (Bloomberg export vs naive proxy) per indicator. -->

### Surprise construction
<!-- TODO(human): raw vs standardized surprise; dispersion source and fallback;
     per-indicator yield_sign; the futures-based FOMC surprise. -->

### Event window and curve decomposition
<!-- TODO(human): window definition (daily H.15 close-to-close constraint),
     level/slope/curvature definitions and why shape over raw tenors. -->

### Regression specification
<!-- TODO(human): OLS spec, regime conditioning (hiking/cutting/hold), standard
     errors, co-release handling (NFP + UNRATE). -->

## Limitations

<!-- TODO(human): small samples, overlapping windows, endogeneity, daily close
     windows vs 8:30 ET releases, naive-proxy consensus quality, ISM licensing gap.
     Honest error bars signal more maturity than any feature. -->

## Reproduction

<!-- TODO(human): exact ingest command (incl. --vintage), analysis notebook/script,
     package versions. -->
