# Lane status — GEMSDOE65 "bandrf" lane

*Generated from `evidence/lane65-bandrf/` on 2026-10-11; the site's decision block is rendered from
the same run card by `scripts/build_site_bandrf.py` and cannot be edited by hand.*

## The download decision

**CLEARED — one file, one click, submit it.**

| | |
|---|---|
| File | `docs/downloads/gems65-h65-1-sarpu-bandrf-22726dots-64c0fa71-nan.tif` |
| Encoding | canonical template convention: finite [0, 1] inside the footprint, NaN outside it, NaN nodata tag |
| Dots | 22 726 |
| Gate | pooled blocked-hold-out **0.01646 [0.01201, 0.02113]** vs matched `nnpu` **0.00614 [0.00121, 0.01164]**; high-propensity tercile 0.0266 vs 0.0034 (no loss) |
| On-disk validator | every canonical check passes (`single_band`, `dtype_float32`, `dimensions_3730x3292`, `crs_epsg_32611`, transform, `in_footprint_all_finite`, `in_footprint_range_0_1`, `outside_footprint_nan`, `nodata_nan`, `zero_dots_on_mapped_catalogue`) |
| Uniqueness | 62 hash-verified staged priors compared; worst ρ 0.0440, worst Jaccard 0.0046, byte- and pixel-unique |
| Also published | `…-zeros.tif` (diagnostics encoding; fails the canonical outside-footprint check **by design**) and `…-nan.zip` + receipt (single-member ZIP of the same TIFF) |

The full machine-readable decision, including the degenerate-rule demonstration, is
`docs/lane65-bandrf/data/run-card.json`.

## The evidence behind it

| arm | pooled blocked-hold-out DTI | 95 % CI |
|---|---|---|
| `nnpu` (baseline) | 0.00614 | [0.00121, 0.01164] |
| `prop` (SAR propensity-weighted, weights clipped at 10) | 0.00790 | [0.00220, 0.01541] |
| **`wire` (declared splay-band × range-front rule)** | **0.01646** | **[0.01201, 0.02113]** |

Evaluator `gems57-pooled-hide-v2`, four folds, 11 321 withheld positive pixels, paired bootstrap.
Per-fold `wire`: NW 0.0364 · NE 0.0149 · SW 0.0085 · SE 0.0147. The mandated comparison
`prop − nnpu` = +0.00176 [−0.00596, +0.01112] is a **null** and is reported as one
(`docs/lane65-bandrf/IRREGULARITIES.md`, IR-65-025b). No leaderboard score is claimed anywhere; a
hold-out DTI is an internal instrument value, not a competition result.

## What it is built from

* Split: the pinned template's own `gems57.holdout.buffered_component_draw` — whole 8-connected
  catalogue components withheld inside label-blind eroded quadrants, a 3 px feature collar removed
  from visible context, visible faults masked pixel-exactly from scoring.
* Features: 27 physical channels (competition stack + hash-pinned public mirrors) plus the lane's
  catalogue-distance and catalogue-density channels; five declared propensity covariates.
* Methods: SAR-EM propensity (`sarem.py`), matched risk arms `nnpu` / `prop` (`risks.py`), the
  unfitted splay-band × range-front emission rule (`lane.py`) — all on the single pinned template.
* Reproduce: `python scripts/run_lane_bandrf.py canary --pixels 150000`,
  `… holdout --folds 0 --max-dots 40000 --channels local --wire-variant band_rf --rf-quantile 0.5 --redo`,
  `… emit --arm wire --baseline nnpu --wire-variant band_rf --rf-quantile 0.5 --mass 30000`.

## Limits, stated plainly

* The hold-out withholds whole catalogue components and strips their context, so it is **harder**
  than the competition task; its value is not a forecast of a leaderboard score.
* The propensity is unanchored: no public exhaustive-mapping index was found, so `e(x)` is a
  sensitivity analysis, not a calibrated quantity.
* The staged registry is a measured comparison, not a completeness certificate; the literal 3 px
  rule is degenerate here and is disclosed rather than reinterpreted away.
* Inputs are integrity-pinned mirrors (not organizer-authenticated) and the run card says so.
