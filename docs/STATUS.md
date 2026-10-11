# Status — GEMSDOE65 lane

**Review date:** 2026-10-11 UTC · **Branch:** `arena/263a33f5-gemsdoe65` · **Source of truth for the decision:** [`run-card.json`](data/run-card.json) → `verdict.one_line` (rendered at the top of [`index.html`](index.html)).

## What runs today

| Step | Command | Artifact |
|---|---|---|
| Input pins | `python3 scripts/restore_inputs.py --check` | `evidence/input_pins.json` (6 SHA-256 pins) |
| Registry index | `python3 scripts/build_registry_index.py --check` | `data/registry/registry_index.json` (62 rasters, fail-closed) |
| Leakage canary | `python3 scripts/run_lane.py canary` | `evidence/lane_canary.json` |
| Blocked hold-out | `python3 scripts/run_lane.py holdout --folds 0` | `evidence/lane_holdout.json` + per-fold cache |
| Emission | `python3 scripts/run_lane.py emit` | `evidence/run_card.json`, `docs/downloads/*.tif` |
| Site render | `python3 scripts/build_site.py` | `docs/index.html` status block, `docs/data/status.json` |
| Tests | `python3 -m unittest discover -s tests -v` | 25 tests, no network, no competition rasters needed |

## The result (2026-10-11)

| arm | pooled blocked-hold-out DTI | 95 % CI |
|---|---|---|
| `nnpu` (baseline) | 0.00614 | [0.00096, 0.01189] |
| `prop` (SAR propensity-weighted, weights clipped at 10) | 0.00790 | [0.00265, 0.01539] |
| **`wire` (declared splay-band × range-front rule)** | **0.01646** | **[0.01201, 0.02113]** |

Evaluator `gems57-pooled-hide-v2`, four folds, 11 321 withheld positives, 146 spatial clusters,
paired bootstrap. Mandated paired comparison `prop − nnpu` = **+0.00176, CI [−0.00596, +0.01112]**
→ a **null** (no demonstrated improvement). `wire − nnpu` = +0.01033, CI [+0.00324, +0.01751].
Top-propensity-tercile mean DTI: `wire` 0.0266 vs `nnpu` 0.0034 → the tercile gate does not lose.

Shipped candidate (unique name, one click, 84 077 bytes):
`docs/downloads/gems65-h65-1-sarpu-bandrf-22726dots-64c0fa71-zeros.tif`
(sha256 begins `f3d964fb3e6932c8`), plus a diagnostics NaN-encoding of the same array.
Verdict: **`DOWNLOAD AND SUBMIT`** — with the literal overlap rule reported as degenerate
(IR-65-022) and the discriminating uniqueness tests all passing.

## The instrument, in one table

| Element | Value |
|---|---|
| Grid | 3 730 × 3 292, 100 m, EPSG:32611, origin (243 350, 4 508 550) |
| Template footprint (used for every shipped file) | 5 167 373 finite cells; 7 111 787 NaN |
| Catalogue positives | 60 988 px (identical count in the label raster and in the template's ones) |
| Hold-out design | whole 8-connected catalogue components withheld, one global draw per seed, 3 px feature collar, label-blind quadrants |
| Metric | DTI with α = 0.2, β = 0.8, 300 m triangular kernel, max-over-kernel (`src/gems57/metric.py`, verified against a brute-force transcription) |
| Folds | NW, NE, SE, SW (whole quadrants eroded by the template's boundary buffer) |
| Arms | `nnpu` (baseline), `prop` (SAR propensity-weighted, weights clipped at 10), `wire` (declared unfitted rule) |
| Emission | monotone percentile-rank sharpening (power 3), mass-matched to the assumed positive count, then the shared marginal-bar dot allocator — identical protocol for every arm |

## Known limitations (carried forward deliberately)

1. **Unanchored propensity.** No public index of exhaustively mapped quadrangles was found, so e(x) is reported as a sensitivity analysis, never as a calibrated probability.
2. **Near-constant propensity.** With the five declared covariates the fitted e(x) spans p10–p90 = 0.838–0.849, so the SAR weighting is close to the identity (IR-65-015).
3. **Harder-than-competition hold-out.** The withheld component loses its neighbourhood context, so a hold-out value understates what the same rule can do on the organizer's private set. It is not a leaderboard forecast.
4. **Owner-mirrored inputs.** Integrity-pinned, not organizer-authenticated (the competition data tab is login-walled).
5. **No organizer score exists for any file here** until a submission is made; this repository never writes a projection as a score.

## Next session, in priority order

1. Re-run `holdout` (resumable) and confirm the pooled numbers are unchanged by code edits; check `implementation_sha256` in the pooled summary.
2. Add a mapping-effort anchor (per-quadrangle USGS/NBMG publication density, or the 1 m lidar acquisition index) to turn the propensity into something that can be called calibrated.
3. Test the declared wire rule's band against a second instrument: withhold whole *quadrangles* rather than components, which stresses the range-front term differently.
4. Only then consider spending the single submission slot; the run card's `verdict.download_cleared` remains the gate.
