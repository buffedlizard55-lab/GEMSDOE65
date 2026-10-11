# Five new geological hypotheses for the DOE GEMS Prize (competition 306)

Date 2026-10-11 · lane `GEMSDOE65` (selection-bias-aware PU learning under SAR) ·
author: autonomous agent run, no human input · budget: 3 experiments / 2 h.

Every hypothesis below states the **layer** (what physical field is used), the
**signature/transform** (how it becomes a score), **why it catches faults that the
USGS QFaults / INGENIOUS catalogue does not contain**, **how it differs from what
the sibling repositories already did**, the **free official source**, and whether
that source is **obtainable from this sandbox**. They are ranked by expected DTI
gain per unit of implementation cost.

The decisive measurement behind all of them is the **two-inventory differential**
(`evidence/mapping_bias_two_inventory.json`, MEASURED, this repo): comparing the
competition catalogue against the mirrored state-geologic-map fault inventory
(`sgmc_faults_100m.tif`, 59,012 pixels more than 300 m from any catalogue pixel)
gives, as AUCs of a single covariate separating "in the catalogue" from "mapped by
the state but absent from the catalogue":

| covariate | bias AUC (catalogue vs state-map-only) | AUC vs state-map-only truth | AUC vs catalogue |
|---|---|---|---|
| `depth_to_base_surf` | **0.6935** | 0.3290 | — |
| `iso_grav_anom_slope` | 0.6101 | 0.4211 | — |
| `lidar_cover` | 0.5778 | 0.4419 | 0.5205 |
| `grav_basin_fill` | 0.3446 | 0.6175 | 0.4593 |
| `dist_range_front` | 0.3391 | 0.6440 | 0.5064 |
| `slope` | 0.2546 | 0.7617 | 0.5577 |
| `relief_local` | 0.2464 | **0.7740** | 0.5633 |
| `height_above_base` | 0.2011 | 0.7687 | — |

Read it as: **the catalogue over-represents deep-basin-fill, low-relief,
low-slope ground far from the range front; the state geologic maps over-represent
exposed, high-relief, steep ground near the range front.** Both are *fault* maps
of the same terrain. That single differential is the observable form of selection
bias, and it is what a SAR (selected-at-random *given covariates*) model is built
to exploit. Note it is the **inverse** of the naive expectation ("steep scarps are
easy to see, so they must be over-mapped") — the catalogue is a
geophysics-informed compilation carrying many *Inferred* basin-margin faults,
while state geologic maps are bedrock-exposure maps.

---

## H65-1 — Two-inventory propensity (implemented; top candidate) — rank 1

* **Layer:** the five pinned covariates (local relief, slope, gravity-derived
  basin-fill proxy, LiDAR coverage, distance to the range front) plus a *second
  public fault inventory* used as the reference population.
* **Signature/transform:** fit `q(x) = P(in catalogue | in catalogue ∪ state-map-only, x)`
  by logistic regression on the two inventories' pixels, then invert
  `q = e/(e + c(1-e))` to
  `e(x; c) = c·q(x) / (1 − q(x) + c·q(x))`.
  `c` is the completeness of the reference inventory — the single documented
  sensitivity parameter. Rank the field by `P(y=1|x)·(1 − e(x))` and train with the
  propensity-aware empirical risk of Bekker, Robberechts & Davis (arXiv:1809.03207),
  weights `w = min(1/e, 10)`, `v = min((1−e)/e, 10)`, normaliser `ρ = P(s=1)` from
  population counts.
* **Why it catches catalogue-missing faults:** `1 − e(x)` is large exactly where
  the catalogue under-samples relative to an independent inventory of the *same*
  physical objects — measured here as exposed, high-relief, steep, near-range-front
  ground (bias AUCs 0.20–0.34). An expert panel working from 1 m LiDAR finds
  scarps there; a geophysics-inferred compilation does not. The family's own
  ladder says the prize is in *re-ranking the same mass*, not in adding mass
  (`60GEMSDOE/docs/research/why-02778-and-what-beats-it-2026-10-11.md`,
  OWNER-REPORT: mean credit 0.135/dot = 2.4× break-even at DTI 0.2778, so raising
  credit/dot to 0.150 ≈ 0.30 and to 0.19 ≈ 0.36).
* **Differs from the repo family:** no sibling lane used a *second inventory* as a
  propensity reference. `60GEMSDOE` used distance-to-catalogue, trace morphology,
  multiline corroboration and ring-peel geometry; `61GEMSDOE` used LiDAR scarp
  descriptors. Those are all *positive-evidence* layers. This one is a
  *selection-model* layer: it changes the risk functional and the ranking, not the
  features.
* **Free official source:** state geologic map fault traces via the mirrored
  `sgmc_faults_100m.tif` already in this sandbox (public-repository derivative,
  hash-pinned); QFaults/INGENIOUS via
  <https://www.usgs.gov/programs/earthquake-hazards/faults> and
  <https://gdr.openei.org/submissions/1391> (INGENIOUS, DOI 10.15121/1881483).
* **Obtainable here:** yes — both inventories are local and hash-pinned. Verified
  in this run: rasterising `trace_segments_utm11.csv` (1,126 QFaults/INGENIOUS
  lines, 84,268 of 84,331 segments inside the grid) covers **89.25 %** of the
  catalogue at median distance **0 px** (p90 1 px), so the catalogue *is* the
  QFaults/INGENIOUS compilation (`evidence/catalogue_identity.json`).
* **Cost:** low (one logistic fit per fold). **Expected gain:** the whole lane.

## H65-2 — LiDAR-coverage-conditional detectability of the *final* label set — rank 2

* **Layer:** `lidar_cover` from the official 19-band stack (12-band quantised
  LiDAR scarp descriptors; 0 = no LiDAR). Measured: LiDAR is valid over 3,894,460
  px = 31.72 % of the grid = **75.37 % of the scored footprint**.
* **Signature/transform:** treat LiDAR presence as a *detectability* multiplier for
  the panel that produces the private expert truth, not as a fault predictor
  (measured AUC vs catalogue 0.5205 ≈ random, so it carries almost no direct
  fault signal). Multiply the emitted field by a monotone function of coverage and
  spend budget preferentially in covered ground; in uncovered ground emit only
  where two independent lines of evidence agree.
* **Why it catches missing faults:** the final-round label set is an expert panel's
  map. In the 24.6 % of the footprint with no 1 m LiDAR the panel must fall back on
  aerial imagery and geophysics, which is precisely where *both* public inventories
  disagree with each other most (state-map-only pixels are slightly **more** likely
  in uncovered ground: AUC 0.4419 < 0.5). Disagreement between inventories is the
  highest-yield place to put a dot.
* **Differs from the repo family:** `61GEMSDOE` used LiDAR scarp *descriptors* as
  positive evidence and documented 10 failed tiles of 716 and a 1–2 m datum offset.
  This hypothesis uses coverage as an *uncertainty* variable in the emission rule.
* **Free official source:** USGS 3DEP <https://www.usgs.gov/3d-elevation-program>,
  staged products at `s3://prd-tnm/StagedProducts/Elevation/1m/` (the family's OCR
  of the official DEM-links PDF matched 722 tile/project pairs, dominated by
  `NV_WestCentral_EarthMRI_2020_D20` (556), `NV_EastCentral_2021_D21` (115),
  `CA_SierraNevada_B22` (22)).
* **Obtainable here:** the quantised layer is local; the raw 1 m tiles are **not**
  reachable from this sandbox (`usgs.gov` and the Dropbox mirrors return HTTP 000).
  Reported as a limitation, not assumed away.
* **Cost:** low. **Expected gain:** medium; it mostly re-allocates budget.

## H65-3 — Range-front structural inheritance, done properly — rank 3

* **Layer:** a real range-front / basin-margin trace, not a proxy. This run
  compared four operationalizations (`evidence/range_front_variants.json`):
  A = 50 m isoline of `det_elev` above a 5 km local minimum (160,275 px, bias AUC
  **0.6609**), B = toe-of-front (87,865 px, 0.5962), C = 30–250 m + slope ≥ 0.08
  (231,990 px, 0.6178), D = basin-edge (64,060 px, 0.6202). Variant A was kept
  because it carries the two-inventory differential best, and it is documented as a
  **proxy of limited geomorphic fidelity**.
* **Signature/transform:** distance-to-front as a *covariate inside the propensity*
  (already done) plus, in the upgrade, a front-parallel anisotropy term: emit along
  strike, not across it, using `gems57.network.segments`.
* **Why it catches missing faults:** basin-margin normal faults are the dominant
  Quaternary structure in this extensional province; the catalogue's distance
  distribution to the proxy front is shifted *farther* than the state maps'
  (stored `dist_range_front` AUC vs state-map-only 0.6440 vs bias AUC 0.3391),
  i.e. the catalogue systematically omits the front-proximal segment population.
* **Differs from the repo family:** `60GEMSDOE` H70/H71 worked on
  mapped-but-uncatalogued *structures*; nothing in the family built a range-front
  surface.
* **Free official source:** 10 m/1 m DEM (3DEP, above) + GSRM v2.1 strain rate
  (already a band in the official stack) + GeoDAWN ScienceBase item
  `657e1d85d34e23d3533209f7`.
* **Obtainable here:** partially — DEM-derived bands are in the stack; raw 3DEP is not.
* **Cost:** medium. **Expected gain:** medium.

## H65-4 — En-echelon stepover / relay-ramp gaps — rank 4

* **Layer:** catalogue trace geometry itself (segment endpoints, stepovers,
  hard-linked vs soft-linked tips) via `gems57.network.segments`.
* **Signature/transform:** score the *gap* between two mapped segment tips whose
  azimuths are within ~20° and whose separation is 300–1500 m; emit one dot per
  relay ramp.
* **Why it catches missing faults:** Quaternary normal-fault systems in this
  province grow by linkage; a relay ramp between two mapped segments is a real,
  mappable fault that a compilation drawn from older 1:250,000 sheets routinely
  leaves as two disjoint traces. The catalogue is 1-px-wide thin lines
  (3×3 erosion leaves 24 of 60,988 px), 3,199 components, median 12 px, max 360 px
  — i.e. it is *fragmented*, which is exactly the precondition for this hypothesis.
* **Differs from the repo family:** `h19-4-multiline-corroborated` counted
  corroborating lines; this scores *unmapped linkage geometry between* them.
* **Free official source:** QFaults (above) + the family's rasterised
  `trace_segments_utm11.csv` (local, verified).
* **Cost:** medium. **Expected gain:** medium-high but narrow (few thousand pixels
  of candidate space), so it cannot carry a full 38,000-dot budget alone.

## H65-5 — Isostatic-residual gradient lineaments (buried range fronts) — rank 5

* **Layer:** `iso_grav_anom_slope` (isostatic residual gravity gradient, from
  `mrdata.usgs.gov/gravity/isostatic/`).
* **Signature/transform:** ridge/lineament extraction on the gradient magnitude,
  restricted to basin fill (`grav_basin_fill` high, `depth_to_base_surf` high).
* **Why it catches missing faults:** a buried range front has no surface expression
  but a sharp basement-depth discontinuity. This is the *complement* of H65-1: the
  catalogue over-represents exactly this environment (bias AUC 0.6935 for
  `depth_to_base_surf`, 0.6101 for the gradient), so a panel with LiDAR will
  **not** confirm many of them, while a panel with gravity will. High variance,
  and it fights the H65-1 ranking, so it is ranked last despite being the
  strongest single bias carrier.
* **Free official source:** USGS isostatic gravity <https://mrdata.usgs.gov/gravity/isostatic/>,
  DOI 10.5066/P9MQRCBY / 10.5066/P9TWT2LU.
* **Obtainable here:** as bands in the official stack; `mrdata.usgs.gov` unreachable
  from the sandbox.
* **Cost:** medium. **Expected gain:** low-medium, direction uncertain.

---

## Ranking summary (expected DTI gain ÷ implementation cost)

| rank | hypothesis | expected gain | cost | obtainable in-sandbox | status in this run |
|---|---|---|---|---|---|
| 1 | H65-1 two-inventory propensity | high (re-ranks all 38,000 dots) | low | yes, hash-pinned | **implemented + gated** |
| 2 | H65-2 LiDAR-conditional detectability | medium (budget re-allocation) | low | layer yes, raw tiles no | covariate in the model; emission rule not implemented |
| 3 | H65-3 real range front | medium | medium | partial | proxy variant A implemented as a covariate |
| 4 | H65-4 stepover/relay gaps | medium-high but narrow | medium | yes | not implemented (budget cap) |
| 5 | H65-5 gravity lineaments | low-medium, sign uncertain | medium | bands yes | measured, deliberately not used for ranking |

## What was validated before any submission slot was touched

The top candidate was validated on **two** spatially-blocked instruments built with
the shared, hash-pinned evaluator (`gems57.evaluate_holdout`, version
`gems57-pooled-hide-v2`, official α=0.2, β=0.8, R=300 m):

* **I1 hide-and-recover** — `gems57.holdout.buffered_component_draw(seed=20,
  hide_frac=0.20, buffer_px=3)`: whole 8-connected catalogue components withheld,
  3 px feature-context collar removed, nearest visible catalogue pixel 3.162 px
  from withheld truth, 11,321 withheld positive pixels over 4 folds
  (NW 1,923 / NE 2,367 / SW 3,781 / SE 3,250).
* **I2 state-map-only** — truth = 59,012 mapped fault pixels more than 3 px from
  the catalogue, scored leave-one-quadrant-out so the propensity anchor never sees
  the pixels it is scored on.

Leakage canary (`evidence/leakage_canary.json`, MEASURED): no single covariate
reaches AUC 0.90 against withheld truth. Worst = `dist_to_visible_catalogue`
0.7548 (the legitimate control signal), then `relief_local` 0.5665, `slope` 0.5636,
`lidar_cover` 0.5329, `dist_range_front` 0.5064, `grav_basin_fill` 0.4593.

**No submission slot was spent by this session**; promotion is a separate selector
step, per the standing instruction.
