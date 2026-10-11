# Tool provenance — what was reused, what was written here

**Review date:** 2026-10-11 UTC. Digests are sha256 of the file as it exists in this repository.

## Reused byte-identically from the shared template

The lane rule is *reuse, don't rebuild*. The three shared tools below are copied **verbatim**
from `buffedlizard55-lab/GEMSDOE32` (`src/gems32/`) into `src/gems65/` so this repository is
self-contained and auditable. Their upstream digests are recorded so any drift is detectable:

| this repo | upstream | sha256 (both) |
|---|---|---|
| `src/gems65/metric.py` | `GEMSDOE32/src/gems32/metric.py` | `74266e75e9aee763764cb9a495bda52a459ee56ef83abeeb63437c8261c1bb5e` |
| `src/gems65/holdout.py` | `GEMSDOE32/src/gems32/holdout.py` | `798793024584dad8a200ae457e3440dd1caad5e60770ce1a9f08a9ae6a136dbb` |
| `src/gems65/submission.py` | `GEMSDOE32/src/gems32/submission.py` | `3d6aea6b60d1dddf6d6bffc1a668ebd0e9833055f87ee6f78d2372aa54afd5b3` |

* `metric.py` — the official distance-weighted Tversky index (alpha 0.2, beta 0.8, 300 m
  triangular kernel), including the brute-force transcription used for unit verification.
* `holdout.py` — the spatially blocked whole-segment hide-and-recover evaluator (4 quadrants x 2
  draws, 15 px collar, 12 px domain erosion) plus the off-catalogue (SGMC) evaluation.
* `submission.py` — the 12-point DrivenData submission-format auditor and the paired
  `-zeros` / `-nan` writer.

## Written in this lane

| module | what it does |
|---|---|
| `src/gems65/grid.py` | pinned input verification, template geometry, footprint from the official sample raster, legal GeoTIFF writer with `outside='zeros'` / `'nan'`, independent read-back receipt |
| `src/gems65/features.py` | the five preregistered propensity covariates and the structural detector channels |
| `src/gems65/propensity.py` | SAR-EM (Bekker & Davis, PMLR v94, 2018) with the `c = E_{y=1}[e]` anchoring constraint |
| `src/gems65/pu.py` | the exact propensity-aware empirical risk (Bekker, Robberechts & Davis, arXiv:1809.03207) with the Kiryo et al. non-negative guard and ramp-up |
| `src/gems65/emission.py` | dispersed credit map and greedy maximum-coverage emission |
| `src/gems65/registry.py` | prior-raster registry, Spearman rank correlation and 3-px dot-overlap lane-drift check |

## Data provenance

The three official rasters were obtained from the owner-maintained bridge mirror
`buffedlizard55-lab/GEMSDOE` → `data/bridge/` (manifest:
https://github.com/buffedlizard55-lab/GEMSDOE/blob/main/data/bridge/manifest.json), which pins the
official DrivenData data-tab / Dropbox mirror URLs and the sha256 of each file. The feature stack
is shipped in five 94,371,840-byte parts; the reassembled file's sha256 matches the manifest pin
exactly. No file was downloaded from `drivendata.org` (that host is not reachable from this
sandbox, and the data tab requires authentication in any case).

External auxiliary data, both official and public domain:

* `data/external/derived_sgmc_faults_100m_u8.tif` — USGS SGMC state geologic-map compilation
  rasterised onto the competition grid. Source: `https://mrdata.usgs.gov/geology/state/shp/NV.zip`
  and `.../CA.zip`. Used only as an off-catalogue truth proxy.
* `data/external/dem1m_high_prior_openness_lrm.npz` — topographic-openness and local-relief-model
  statistics from eight official USGS 3DEP 1 m EarthMRI DEM tiles (NV_WestCentral_EarthMRI_2020_D20,
  `https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/NV_WestCentral_EarthMRI_2020_D20/TIFF/`).
  Used only as the lidar-coverage propensity covariate.
