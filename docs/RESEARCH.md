# Research design and score-provenance assessment

**Review date:** 2026-10-11 UTC. This document records verified source claims, project hypotheses, and unknowns separately. It is not a model result.

## What the competition measures

The official task asks for predictions of **geological faults indicative of geothermal resources**, not a direct map of geothermal vents. The organizer describes a distance-weighted Tversky metric with alpha 0.2, beta 0.8, and a 300 m triangular support kernel. False negatives are weighted more heavily than false positives, and nearby pixels receive distance credit. That provides a reason to test spatial support and calibration; it is not evidence that a dense or sparse raster is geologically correct or will score well.

The output contract is one float32 GeoTIFF band on the official template grid, EPSG:32611, at 100 m, with exact dimensions/bounds/transform, values in `[0,1]` within the footprint, and null/NaN only outside. Exact grid details must come from the authenticated official sample. These format requirements cannot be verified or approximated from a different file. See the [official problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) and [submission guide](SUBMISSION_GUIDE.md).

## Why selection bias is a defensible research question

Giddens & Faulds (2025, SGP-TR-229) report that about 91.9% of their identified Great Basin step-overs are associated with range-front faults and explicitly warn that steep topographic gradients can make those step-overs easier to identify. Their methods state that only about 25% of their approximately 499,178 km² study area was mapped in sufficient detail (e.g. 1:24,000). These are study-specific statements about an inventory of step-overs and the INGENIOUS study area. They do not establish the same propensity function, map coverage, or exhaustive-mapping rate for the competition footprint.

A selection model can be written `e(x)=P(S=1 | Y=1, X=x)`, where `Y=1` denotes a true fault and `S=1` denotes its inclusion in the labelled catalogue. The observed positive-label rate satisfies `P(S=1 | X=x) = P(Y=1 | X=x) × e(x)`. Without additional restrictions, fault prevalence and mapping propensity are confounded: a low label rate may mean fewer faults, lower detection, or both.

Bekker & Davis (2018) formulate Selected At Random learning when label propensity depends on observed attributes and propose SAR-EM. Bekker, Robberechts & Davis (2019) describe empirical-risk correction that incorporates the labeling mechanism and discuss incomplete knowledge of it. Neither paper makes absolute geological propensity identifiable from arbitrary PU data. The covariate set, assumptions, anchoring, and sensitivity range must be declared. If no independent exhaustive-coverage anchor is proven, report propensity as sensitivity analysis, not a calibrated probability map.

## Proposed lane and hypotheses

The first experiment is a matched comparison, not an assumed win:

- Estimate label propensity using local relief, slope, locally verified LiDAR/DEM-source coverage, gravity-derived basin-fill proxy, and distance to an independently mapped range front.
- Use SAR-EM and the Bekker–Robberechts–Davis propensity-aware empirical risk with inverse weights clipped at 10. Treat that cap as a protocol choice, not a finding from the papers.
- Compare against nnPU on identical spatially blocked folds and budget. Withhold whole fault segments with a buffer; derive all catalogue-based features from visible faults only and mask visible-fault pixels exactly.
- Run each feature alone as a leakage canary; AUC greater than 0.90 is a fail until explained.
- Report pooled DTI with evaluator version, withheld-positive count, paired 95% CI, and the highest-propensity tercile. Promotion requires beating both the current holdout best and matched nnPU overall, without losing in the highest-propensity tercile.

Four within-lane candidates and their costs, signatures, and non-fault mimics are ranked in [`HYPOTHESES.md`](HYPOTHESES.md) and the site's [hypothesis page](hypotheses.html). Global novelty is not established: prior sibling work includes SAR/nnPU and PU-proxy experiments, and the full sibling code/history has not been inventoried.

## Candidate covariates and coverage limits

### Relief, slope, and DEM/LiDAR coverage

Giddens & Faulds describe using one-meter GeoDAWN LiDAR over parts of western Nevada and 10-meter 3DEP DEM elsewhere in their study area. This supports testing whether survey/source availability affects fault visibility, but does not prove which source covers each competition pixel. Build a spatially explicit source-coverage layer only from authoritative metadata, with acquisition date, resolution, and no-data recorded. Do not infer coverage from terrain values alone.

### Quadrangle mapping effort

USGS provides a public 7.5-minute map-index service and NGMDB map-search/catalogue records. The index shows map-frame polygons, not exhaustive geologic mapping. Publication scale/footprint records alone do not prove that every fault was mapped. The approximately 25% value in Giddens & Faulds describes their study area and mapping-detail threshold; it is not a competition-wide coverage estimate or a sufficient propensity anchor. Until individual map extents, scale, completeness, and overlap are audited against the exact template footprint, keep propensity scale unanchored and report sensitivity.

### Gravity and basin fill

USGS metadata for DOI [10.5066/P13BAFSV](https://doi.org/10.5066/P13BAFSV) describes a gravity-based regional depth-to-basement surface in a Great Basin hydrogeologic release, with model nodes at one-mile spacing and coverage predominantly in eastern Nevada and western Utah. The release is obtainable and CC0, but this repository did not download it, test overlap with the northwestern GeoDAWN footprint, or audit its grid/units. A broad bounding box is not proof of pixel coverage. Treat it as a conditional research lead. Prefer the authorized competition-provided gravity bands if present in the shared feature stack; inspect actual metadata first.

Non-fault mimics include lithologic/density contacts, basin geometry, landslide scarps, erosional/drainage breaks, roads/cultural lineaments, and survey/mapping effort correlated with population, access, or geologic interest. A propensity model can absorb geological prevalence if these dependencies are not examined.

## H33-2-B2 and other score claims

The user associates a named GEMSDOE32 H33 file with a public score. The inspected [GEMSDOE32 page](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html) labels the artifact “UNSCORED”; its [manifest entry](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/docs/downloads/submissions_manifest.json) has `receipt: null`, and [PR #9](https://github.com/buffedlizard55-lab/GEMSDOE32/pull/9) describes an owner-reported projection/development arm. These records do not provide an organizer receipt tying that TIFF to a score.

The official leaderboard is participant-level public context and does not identify uploaded TIFF filenames. Because the [DrivenData Terms of Use](https://www.drivendata.org/termsofuse/) prohibit automated monitoring/copying and manual monitoring/copying without prior written consent, this project does not store or reproduce leaderboard rows. No written permission or authorized public API is established. The accurate answer to “why did this file get that score?” is **unknown; the file-to-score premise is not verified**. Any explanation would be speculation.

Values and dates in the user-supplied history remain unverified unless supported by an authorized current source and a receipt tied to a specific file. Future-dated entries are not current evidence. No prior TIFF is copied into this repository.

## Evidence boundary and current result

No experiment, local holdout score, confidence interval, feature-only AUC, propensity estimate, surface correlation, dot overlap, pixel-agreement check, validation result, or organizer receipt exists for this repository. Those fields remain null/`NOT RUN` in the canonical [`data/run-card.json`](data/run-card.json). See [`SOURCES.md`](SOURCES.md), [`IRREGULARITIES.md`](IRREGULARITIES.md), and [`STATUS.md`](STATUS.md).

**Project verdict: negative / blocked.** The necessary data, shared evaluator/writer/validator, and prior-raster registry are absent. Do not create, offer, download, or submit a TIFF. No weekly slot was used.
