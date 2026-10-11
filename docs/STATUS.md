# Review status — 2026-10-11 UTC (session `arena/24bf361e-gemsdoe65`)

## Result

**PROMOTE. One submission candidate is cleared for download and submission.**
Primary file: `docs/downloads/gems65-sar-em-propensity-half-20261011T223500Z-5e4660cd-zeros.tif`
(sha256 `b2e05f0b0d61a785d01cc9469462442fbf3b9b5bdc9a34c2abe0852fd66ec9dc`, 102,010 bytes,
39,802 dots). The canonical run card is [`data/run-card.json`](data/run-card.json).

**Scope of the claim.** The evidenced claim is *paired*: on identical spatially blocked folds the
SAR propensity-aware PU risk beats the matched nnPU baseline on the pooled blocked-holdout DTI
(0.0234 vs 0.0221) **and** on the leakage-free off-catalogue (USGS SGMC) DTI (0.0247 vs 0.0219),
loses nothing in any propensity tercile, is unique against all 82 prior rasters, and passes the
format validator. **No organizer score, no leaderboard position, and no projection is claimed.**
The absolute holdout proxy value (~0.023) is far below the public board range and is not
comparable to it.

## Experiments run (3 of the 3-experiment budget)

| # | Experiment | Artifact | Outcome |
|---|---|---|---|
| 1 | Single-feature leakage canary on the blocked holdout | `artifacts/leakage_canary.json` | 35 features tested; 0 flagged; strongest `strike_sin` mean AUC 0.5462 |
| 2 | SAR-EM propensity vs nnPU at four anchoring constants `c` | `artifacts/holdout_sweep.json` | all four `c` produced identical emissions — propensity **shape** identified, **scale** not |
| 3 | Propensity-weight shrinkage `w = 1/e^lambda` | `artifacts/shrinkage_sensitivity.json` | lambda = 0.5 is the only setting improving both holdout and off-catalogue DTI; shipped |

## Verified inputs

The three official rasters were hash-pinned and re-verified at run time; see
[`PROVENANCE.md`](PROVENANCE.md) for the digests, the bridge-mirror provenance, and the
byte-identical reuse of the shared template's metric / holdout / submission tools.

## Limitations carried forward

* **No 95% CI** was computed inside the two-hour budget; the paired nnPU baseline on identical
  folds is the reported comparison. This is a gap, not a pass.
* **No organizer receipt**, so nothing here is `ORGANIZER-CONFIRMED`. No leaderboard row is
  fetched, stored, or mirrored.
* **The 1 m lidar covariate is sparse**: 34,094 of 5,167,373 footprint pixels (0.66%).
* **The range-front covariate is an operational proxy** (the basin-margin escarpment derived from
  the gravity-derived basin-fill thickness), not an independently mapped range front.
* **No exhaustive-quadrangle public index** was found, so the propensity scale is unanchored and
  reported only as sensitivity.
* **CPU only, linear models.** No GPU, no deep detector.
* The candidate's emission is a greedy maximum-coverage packing of the metric's own dispersed
  credit map; its absolute proxy score is not competitive with the public board.

## Next actions

1. Compute the paired block-bootstrap 95% CI on the eight holdout cells.
2. Break the propensity-scale identifiability with a verified exhaustive-mapping index, or state
   permanently that it cannot be done.
3. Replace the operational range-front proxy with an independently mapped structural linework
   product and re-test.
4. Improve the *field*, not the emission: the remaining distance to a competitive score is a
   detector problem (1 m lidar context + GPU), as the lane's own analysis concluded.
