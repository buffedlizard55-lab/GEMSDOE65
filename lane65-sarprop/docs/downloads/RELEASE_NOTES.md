# lane65-sarprop submission artifact v1

Built by the `lane65-sarprop/` lineage of this repository: a selection-bias-aware PU model
(SAR + Bekker–Davis EM propensity, propensity-weighted risk, nnPU-gated) over the DOE GEMS
footprint. **Locally cleared, not organizer-confirmed.**

| field | value |
|---|---|
| file | `gems65-sarprop-pu-v1.tif` (all-finite; no NaN anywhere) |
| sha256 | `12240335ff72b4f36714265ccbceec93b114fe06b0ca7abe7e9611cd559618a2` |
| size / grid | 192,492 B · float32 · EPSG:32611 · 3730×3292 · 100 m |
| dots | 74,351 positive pixels, all in `[0, 1]`, none on the mapped catalogue |
| name / note | `gems65-sarprop-pu-v1` · "Selection-bias-aware SAR propensity PU (Bekker-Davis EM), nnPU-gated." (69 chars) |

## Status

Every local precondition in `lane65-sarprop/docs/status.json` is green — the blocked-holdout gate
(SAR-propensity arm 0.073242 vs nnPU 0.067864, no loss in the highest-propensity tercile), the
format validator, and the parallel-run duplicate audit against 653 published rasters (worst rank
correlation 0.0401, worst dot-set Jaccard 0.0207). **No submission slot has been spent on this file
and no DrivenData receipt exists for it**, so no leaderboard number is claimed.

## Rebuild it instead of trusting this attachment

```
cd lane65-sarprop
python scripts/reconstruct_submission.py --check   # byte-identical, needs the public bridge rasters
python scripts/reconstruct_submission.py --direct  # pixel-identical, needs nothing
```

## Do not confuse this with the repository root lineage

The root lineage of the same lane reports a **negative** result on a different holdout instrument
and publishes its own rasters under a DO-NOT-SUBMIT banner. The two instruments are not comparable
with each other, and neither is comparable with an organizer score.
