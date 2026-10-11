# Candidate geological hypotheses — ranked by expected DTI gain vs implementation cost

Generated 2026-10-11 by the GEMSDOE65 lane. Every geological statement below is either (a) quoted
from a source that was fetched and read in this sandbox (links in `registry/sources.json`), or
(b) a measurement made on the hash-pinned rasters by a script in `scripts/`. Anything that is my
own inference is labelled **INFERENCE** and carries the mechanism that makes it falsifiable.

Protocol compliance: the top-ranked candidate was validated on the spatially blocked holdout
(8 cells = 4 quadrant blocks x 2 draws) **before** any weekly slot was considered, per the standing
brief. No slot was spent.

---

## Why these hypotheses exist at all

Two verified facts define the opportunity:

1. **The catalogue is incomplete in a terrain-correlated way.** Giddens & Faulds 2025 (SGP-TR-229,
   read in full, <https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Giddens.pdf>):
   *"with only ~25% of the study area mapped in sufficient detail (e.g., 1:24,000)"*, and step-overs
   are *"more commonly associated with range-front faults (~91.9%). There is potential bias in this,
   as step-overs along range-front faults are more easily identified due to steep topographic
   gradients."*
2. **Lidar is not the bottleneck; maps are.** Faulds 2026 (51st Workshop,
   <https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2026/Faulds.pdf>): *"Publicly available
   high-resolution Lidar now covers much of the GBR, but detailed geological maps include less than
   25% of the region."* Measured here: lidar covers **0.7537** of the scoring footprint.

**INFERENCE (the mechanism all five hypotheses share):** a fault that is physically present but
never mapped is *not* a random draw from all faults. It is preferentially a fault whose surface
expression is weak in the specific ways that a field geologist or a 1:24,000 mapper keys on —
low-relief, alluvium-covered, low-scarp-density, away from range fronts. Those are exactly the
terrain attributes available in the covariate stack. So "unmapped fault" is a *learnable class*,
and a model that predicts it directly targets the catalogue's blind spots rather than its
well-mapped parts. This is the whole reason the lane is a selection-bias (SAR) PU problem instead of
a segmentation problem.

**The named non-fault process that mimics it** (required by protocol rule 5): **alluvial and
eolian burial.** A basin floor covered by post-faulting sediment produces low relief, low curvature
variance and low lidar-derived scarp density — statistically indistinguishable from "mapped-less
because expression-less" — but contains fewer faults per unit area than the mapped uplands simply
because it is younger surface. Any hypothesis below that keys only on "flat and blank" will score
on buried alluvium, not on buried faults. Every candidate therefore pairs a *suppression* term
(why it was not mapped) with a *presence* term (why a fault is physically there anyway).

---

## Ranked candidates

Ranking score = expected DTI gain / implementation cost, where cost is measured in engineer-hours
inside this sandbox (2 CPU, ~2.8 GB RAM, chunked inference mandatory) and gain is measured against
the registry's own owner-reported band (0.2376–0.2778) and the 2026-10-04 leaderboard snapshot
(#1 = 0.3262), not against any projection.

### H-65-A — Step-over / relay-ramp corridors (RANK 1, validated on blocked holdout)

* **Layers used:** `training_features.tif` band 19 `det_elev_slope` (measured standardised mean
  difference between labelled and background: **0.482**, second strongest of 19 bands), band 5
  `iso_grav_anom_slope` (SMD **0.362**), band 3 `tmi_hg` (SMD **0.386**), plus the derived
  range-front mask (**441,499 px = 8.5%** of the footprint) and lidar coverage (**0.7537**).
* **Physical signature:** two en-echelon normal fault strands separated by a transfer zone. The
  relay ramp is a gently-dipping, topographically expressed surface between the strand tips, with
  systematic drainage deflection and a local gravity gradient step from the displaced basin fill.
* **Why it catches catalogue-missing faults:** verified — *">73% of right-stepping step-overs on
  N–NNE strands, ~58% on westerly-dipping faults"* and mean relay-ramp width **2.5 km** in the
  western Great Basin (Giddens & Faulds 2025). At 100 m pixels a 2.5 km ramp is 25 px wide, so the
  structure is resolvable but only if the *pair* is detected; a mapper working quadrangle-by-
  quadrangle records the two strands and misses the ramp between them, especially across a
  quadrangle boundary. **INFERENCE:** the highest-yield pixels are therefore the *inter-strand
  corridor*, not the strands themselves — and the strands are already in the catalogue (and, per the
  staff ruling in forum thread 11516, masked out of scoring anyway).
* **How it differs from the repo/template:** GEMSDOE32's best artifact (owner-reported 0.2778) is a
  smoothed-belief max-coverage emitter over a generic segmentation belief; it has no structural
  pairing operator and no explicit step-over geometry. Nothing in either sibling repo computes an
  inter-strand corridor field.
* **Expected gain:** moderate-to-high. The mechanism is documented, the discriminating bands are the
  two strongest in the stack, and the target pixels are provably outside the catalogue's masked
  core.
* **Implementation cost:** low-moderate (~1 day). Needs a strand-tip detector, a directional pairing
  search over the fault-component graph (already computed: catalogue = 60,988 px in 3,199
  8-connected components, median size 12), and a corridor field. No new data.
* **Holdout result:** this is the candidate that was actually built and validated this session. It is
  the SAR/propensity arm. **The gate was NOT met** — pooled HOLDOUT-DTI 0.06183 (SAR propensity-aware
  ERM) vs 0.06687 (nnPU SCAR baseline), Δ = −0.00504, 95% CI [−0.01015, −0.00111], wins 2/8 cells;
  top-propensity tercile Δ = −0.01107. Logged as a **negative result**. See the validity caveat in
  `registry/irregularities.json` IR-65-006: the holdout's truth is the withheld part of the same
  catalogue, which concentrates in *high*-propensity terrain, so it structurally penalises the
  reallocation this hypothesis is designed to perform. The instrument measured what it can measure;
  it did not confirm the thesis.

### H-65-B — Fault-intersection dilational nodes (RANK 2)

* **Layers used:** catalogue component graph (already built), band 16 `ieq_n100a15|seismic` (SMD
  **0.570**, the strongest single band), band 7 `geod_shearrate` (SMD **0.390**), derived
  `grad_det_elev`.
* **Physical signature:** where two fault systems cross, the local stress field is dilational;
  permeability is enhanced and there is a measurable seismic-velocity and geodetic-strain-rate
  anomaly at the node.
* **Why it catches catalogue-missing faults:** verified frequency — fault intersections are **26.1%**
  of known geothermal fault-system settings (Faulds 2026), second only to step-overs. An intersection
  node implies at least two strands; if either strand is unmapped at 1:24,000 scale, the node is
  absent from the catalogue even though its *signature* is present in the geophysics, which is
  acquisition-blind to map coverage.
* **How it differs from the repo:** no sibling repo builds a node field from the intersection of the
  *geophysical* lineaments; they use the catalogue's own geometry only.
* **Expected gain:** moderate. Fewer target pixels than H-65-A (nodes are sparse) but each is high
  confidence, and the DTI is a coverage-weighted kernel, so sparse-and-right beats dense-and-wrong.
* **Implementation cost:** moderate (~1–2 days). Requires a lineament extraction from the gravity/
  magnetic derivative bands (the two highest-SMD bands are both derivative fields, which is a good
  sign) and a crossing detector. No new data.

### H-65-C — Accommodation-zone transfer faults between adjacent ranges (RANK 3)

* **Layers used:** `log1p(depth_to_base_surf)` from the gravity-derived basin-fill proxy (measured
  Pearson r = **0.591** against the independent `basin_fill` covariate — corroboration that the
  proxy is real), band 19 `det_elev_slope`, DEM-derived relief.
* **Physical signature:** a transverse zone where the polarity of basin-range tilting alternates;
  expressed as a topographic step across the basin floor and a basement-depth discontinuity that is
  *oblique* to the dominant range trend.
* **Why it catches catalogue-missing faults:** verified frequency **6.8%** (Faulds 2026), and by
  construction these structures lie *in the basin*, i.e. under alluvium, i.e. exactly where 1:24,000
  mapping is thinnest. This is the purest "mapped-less because expression-less" candidate.
* **How it differs from the repo:** uses the gravity basement-depth field as the primary layer rather
  than as one band among nineteen, and requires a trend-obliquity test rather than a magnitude test.
* **Expected gain:** low-moderate, and it carries the **highest mimicry risk**: this is the
  hypothesis most exposed to the alluvial-burial non-fault process named above. A basement step can
  be a depositional surface.
* **Implementation cost:** moderate (~2 days). Needs a dominant-trend estimate per window and an
  obliquity map.

### H-65-D — Horse-tail terminations and splay fans at strand ends (RANK 4)

* **Layers used:** catalogue component endpoints (median component size 12 px — most components are
  small enough that their endpoints are computable exactly), `curv`, `grad_det_elev`.
* **Physical signature:** a propagating normal fault tip loses displacement into a fan of short
  splays; curvature variance rises locally while relief stays low.
* **Why it catches catalogue-missing faults:** verified — terminations are **16.7%** of known
  settings, and ~90% of known geothermal systems sit in four structural settings, horse-tailing
  terminations being one of them (Faulds 2026). Splays below 1:24,000 mapping resolution are
  systematically dropped.
* **Expected gain:** low-moderate. The splays are short, so the DTI kernel (R = 300 m = 3 px) will
  often be satisfied by an adjacent catalogue pixel — which earns *nothing*, because catalogue
  pixels are masked out of scoring (forum thread 11516).
* **Implementation cost:** low (~0.5 day). Cheapest candidate on the list; a reasonable control
  experiment rather than a primary bet.

### H-65-E — Pull-apart basins at releasing bends (RANK 5)

* **Layers used:** `basin_fill`, `log1p(depth_to_base_surf)`, `tmi_hg`, plan-view fault trace
  curvature from the catalogue graph.
* **Physical signature:** a rhomboid, locally deep basement depression with a strong magnetic-low
  fill, bounded by two en-echelon strike-slip-oblique strands.
* **Why it catches catalogue-missing faults:** verified frequency **2.3%** (Faulds 2026) — the rarest
  of the five settings, hence the smallest candidate pixel population.
* **Expected gain:** low, purely because of rarity; but the discriminant is sharp (a rhomboid deep
  basement body is hard to fake), so precision should be high.
* **Implementation cost:** high (~3 days) relative to its population. Ranked last on the
  gain/cost ratio.

---

## Summary table

| rank | id | expected gain | cost | new data needed | mimicry risk | holdout-validated |
|---|---|---|---|---|---|---|
| 1 | H-65-A step-over corridors | moderate-high | ~1 d | none | medium | **yes — gate FAILED, logged negative** |
| 2 | H-65-B intersection dilational nodes | moderate | ~1–2 d | none | low-medium | no |
| 3 | H-65-C accommodation-zone transfer faults | low-moderate | ~2 d | none | **high** | no |
| 4 | H-65-D horse-tail splay fans | low-moderate | ~0.5 d | none | medium | no |
| 5 | H-65-E pull-apart basins | low (rare) | ~3 d | none | low | no |

**Recommendation.** H-65-B is the best next experiment on gain/cost: it uses the strongest
discriminating band in the stack (band 16, SMD 0.570), its target pixels are provably outside the
masked catalogue core, and its mimicry exposure is lower than H-65-C's. H-65-D is the cheapest
possible control and should be run first if a fast sanity check is wanted.

---

## If new external data are needed: the specific free official source

No candidate above requires it — all five are computable from the restored, hash-pinned stack. The
one gap in the whole lane is the **propensity-scale anchor** (IR-65-001), and the free official
source that closes it is:

* **Nevada Bureau of Mines and Geology — MapInfo / digital geologic map inventory**,
  <https://nbmg.unr.edu/library/mapinfo.html> (NBMG is the official state geological survey; all
  products free). It carries the *scale* of every published quadrangle map, which is exactly the
  "exhaustively mapped at 1:24,000" index the brief asks for.
* **Confirming alternative, also free and official:** the **USGS National Geologic Map Database
  (NGMDB) Map Index**, <https://ngmdb.usgs.gov/maps/> — a per-quadrangle inventory of published
  geologic maps with scale, free, no login.
* **Obtainability from this sandbox: NOT obtainable.** `nbmg.unr.edu`, `usgs.gov` and `epsg.io` are
  all off the egress allowlist (measured, not assumed). Obtainability from a normal machine is high:
  both are public, no authentication, no rate limit of consequence. **Action for a human reviewer:**
  download the NBMG map-scale inventory, rasterise "mapped at >= 1:24,000" onto the competition grid,
  and re-run `python scripts/02_run_holdout.py --a-bar <measured mean propensity over mapped area>`.
  That converts the propensity sensitivity analysis into an identified estimate.
* Secondary free official source already in the stack: **USGS 3DEP 1 m DEM tiles** via the public
  TNM bucket `https://prd-tnm.s3.amazonaws.com/` (716 URLs pinned in `data/external/dem_links.json`)
  and **GeoDAWN** gravity/magnetics, DOI <https://doi.org/10.5066/P93LGLVQ>.

---

## What would falsify each hypothesis

* **H-65-A**: if a corridor field, evaluated against *organizer-confirmed* scores rather than the
  catalogue-hidden holdout, does not beat the nnPU baseline by more than its 95% CI width, the
  reallocation thesis is dead for this metric. One receipt settles it.
* **H-65-B**: if the extracted geophysical lineaments do not reproduce the catalogue's own traces
  where the catalogue exists (leave-one-cell-out agreement), the lineaments are noise and every node
  derived from them is noise.
* **H-65-C**: if basement-depth discontinuities are as frequent inside mapped alluvial fans as across
  range-bounding structures, the feature is a depositional surface and the hypothesis collapses.
* **H-65-D**: if splay-fan pixels fall within 3 px of catalogue pixels more often than chance, they
  are masked out of scoring and the hypothesis cannot earn DTI regardless of geological validity.
* **H-65-E**: if fewer than ~200 candidate pixels survive thresholding, the population is too small
  to move a coverage-weighted metric.
