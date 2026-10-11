# Geothermal vent / fault-hosted permeability science — reusable knowledge base

Written 2026-10-11 for the GEMSDOE65 lane and intended to be reused by later lanes in this repo
family. **Citation discipline:** a statement is either **V** (verified — read from a source fetched
in this sandbox, link given), **M** (measured — computed from the hash-pinned rasters by a script in
`scripts/`), or **I** (inference — my own reasoning, always with the mechanism that makes it
falsifiable). Nothing here is recalled from training data without one of those labels.

---

## 1. What a geothermal "vent" is in this competition's sense

The competition does not ask for vents, hot springs or fumaroles. It asks for **fault traces that
were not already known** — pixels of unmapped fault. **V** The scoring index (Deep Fault Detection
Index, DTI) is a coverage-weighted kernel score with R = 300 m: a prediction earns credit only if it
lands within 300 m of withheld truth, and known USGS/INGENIOUS fault pixels are **masked out of
evaluation**, so mass placed on an already-known fault earns neither TP nor FP
(<https://community.drivendata.org/t/11516>, S02).

**I — the operative consequence:** the task is *permeability-structure discovery under a coverage
constraint*, not vent discovery. Geothermal vent science matters here only because vents are the
surface expression of the structures being sought: a vent tells you a fault is hydraulically live,
and a live fault is what the hidden truth is made of. Any feature that predicts "fault" but not
"fault with a thermal expression" is spending budget on structures the label set is biased toward
including.

---

## 2. Why faults host geothermal systems (the physics, and which layer sees it)

| mechanism | physical content | layer that observes it | status |
|---|---|---|---|
| Dilational damage zone | normal-fault slip creates a fracture-dense damage zone with permeability orders of magnitude above host rock | `curv`, `grad_det_elev`, lidar scarp-density bands | **I** (standard structural-permeability reasoning; no source fetched here states the magnitude, so no number is quoted) |
| Step-over / relay-ramp transfer | en-echelon strands transfer slip through a ramp; the ramp is a zone of distributed deformation and high fracture density | DEM relief, `det_elev_slope` | **V** — Giddens & Faulds 2025 quantify it: mean relay-ramp width **2.5 km** in the western Great Basin; **39.7%** of step-overs there, **51.8%** right-stepping (<https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Giddens.pdf>) |
| Intersection nodes | crossing fault systems produce a locally dilational stress field | band 16 `ieq_n100a15|seismic` (SMD **0.570** — the strongest discriminating band **M**), band 7 `geod_shearrate` (SMD **0.390** **M**) | **V** for frequency (**26.1%** of settings, Faulds 2026), **M** for layer strength |
| Basin-fill contrast | displacement of the basement produces a gravity gradient; sediment fill is a thermal blanket and a magnetic low | band 5 `iso_grav_anom_slope` (SMD **0.362** **M**), band 3 `tmi_hg` (SMD **0.386** **M**), `log1p(depth_to_base_surf)` | **M** — the gravity-derived `basin_fill` proxy correlates r = **0.591** with the independent `log1p(depth_to_base_surf)` covariate (`evidence/covariates.json`) |
| Range-front focusing | the range-bounding fault is where uplift, erosion and fluid flow concentrate | derived range-front mask: **441,499 px = 8.5%** of footprint **M** | **V** — *">73% of right-stepping step-overs on N–NNE strands, ~58% on westerly-dipping faults"*; step-overs *"more commonly associated with range-front faults (~91.9%)"* (Giddens & Faulds 2025) |

---

## 3. The structural taxonomy and its frequencies (all verified)

**V** — Faulds 2026, 51st Workshop on Geothermal Reservoir Engineering
(<https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2026/Faulds.pdf>), fault-system (FSS) setting
frequencies for known Great Basin geothermal systems:

| setting | share of known systems | pixel-scale implication at 100 m |
|---|---|---|
| step-overs / relay ramps | **39.6%** | ramp width 2.5 km = ~25 px, resolvable but needs *pair* detection |
| fault intersections | **26.1%** | node is 1–3 px; precision-critical, population sparse |
| terminations (incl. horse-tailing) | **16.7%** | splay fans are sub-mapping-resolution by definition |
| accommodation zones | **6.8%** | transverse, in-basin, highest burial-mimicry risk |
| pull-aparts | **2.3%** | rhomboid deep basement body; rare but sharp discriminant |

**V** — *~90% of known systems lie in four structural settings* (horse-tailing terminations,
step-overs/relay ramps, intersections, accommodation zones). **I:** that is a prior over where the
withheld truth is, and it is the single most actionable number in this document — it says roughly
9 in 10 hidden faults sit in one of four geometries, three of which are *junction* geometries rather
than *strand* geometries. Junctions are precisely what a per-quadrangle 1:24,000 mapper drops,
because a junction between two quadrangles belongs to neither.

---

## 4. Why the catalogue is biased — and the direction of the bias

**V** — Giddens & Faulds 2025, verbatim: *"with only ~25% of the study area mapped in sufficient
detail (e.g., 1:24,000)"*; *"There is potential bias in this, as step-overs along range-front faults
are more easily identified due to steep topographic gradients"*; *"The greatest limitation to this
project was available data. High resolution LiDAR was only available for portions of the study area."*

**V** — Faulds 2026, verbatim: *"Publicly available high-resolution Lidar now covers much of the GBR,
but detailed geological maps include less than 25% of the region."*

**M** — lidar coverage of the competition footprint = **0.7537**; range-front pixels = **8.5%** of
footprint.

**I — the direction of the bias, stated so it can be attacked:** the catalogue over-represents
faults with **strong topographic expression at range fronts**, and under-represents faults that are
(i) in basins under alluvium, (ii) at junctions between mapped quadrangles, (iii) low-relief splays.
This is *not* the "missing completely at random" assumption that standard PU learning (SCAR) makes,
and it is *not* even "selected at random" (SAR) in the strict sense unless the selection depends only
on covariates — which is exactly what the SAR propensity model assumes: `e(x) = P(labelled | fault, x)`
depends on terrain `x`, not on the fault's identity. **V** for the definition (Bekker & Davis 2018,
Definition 1, PMLR 94:8–22).

**I — and the measurement-validity trap that follows, which is the most important lesson in this
document:** if selection favours high-relief range-front terrain, then the *withheld part of the same
catalogue* also favours high-relief terrain. So a holdout built by hiding catalogue pixels measures
performance on **high-propensity** truth, while the hypothesis being tested is that gains live in
**low-propensity** terrain. The instrument is biased against the thesis by construction. This was
observed, not predicted: the SAR arm's deficit concentrated in the top-propensity tercile
(Δ = −0.01107) while the pooled deficit was −0.00504. Recorded as `IR-65-006`.

**Reusable rule for future lanes:** *never validate a selection-bias hypothesis against a holdout
carved out of the biased selection itself.* Either (a) anchor truth in an independent compilation, or
(b) stratify the report by estimated propensity and read the low-e stratum as the primary result, or
(c) spend one organizer-confirmed receipt and treat it as the only real measurement.

---

## 5. The propensity model — what it is and what it is not

**V** — Bekker & Davis 2018 (<https://proceedings.mlr.press/v94/bekker18a.html>) and Bekker,
Robberechts & Davis 2019 (<https://arxiv.org/abs/1809.03207>):

* **Definition 1.** `e(x) = Pr(s = 1 | y = 1, x)` — the probability a positive is *labelled*, given
  its covariates.
* **Definition 2.** The propensity-weighted risk is unbiased for the fully-supervised risk: a
  labelled example contributes weight `1/e_i` to the positive loss and a *copy* with weight
  `1 − 1/e_i` to the negative loss; an unlabeled example contributes the negative loss with weight 1.
  **No class prior appears.** (Verbatim formula transcriptions are in `src/gems65/pu.py`'s docstring.)
* **Proposition 5.** Bias in the propensity estimate only matters *on positives* — so propensity
  accuracy in regions with no faults is irrelevant. This is why the propensity model is allowed to be
  much simpler than the classifier.
* **Section 5.1.** `e` must depend on a *strictly smaller* covariate subset `x_e` than the
  classifier, or the propensity is not identifiable. Strata reduction is suboptimal for continuous
  `x_e`. **Design consequence here:** propensity design = `[1, z(5 covariates), z(4 continuous)^2]`;
  classifier design = all 23 features (19 bands + relief + curvature + 2 gravity-gradient terms).
* **Section 2.** The propensity *scale* is not identified from PU data alone. **V** — hence IR-65-001
  and the `a_bar` sensitivity sweep {0.15, 0.25, 0.32, 0.50}, with 0.25 pre-registered from the
  peer-reviewed ~25% detailed-mapping share.
* `R̂_exp` (the "expected" variant) is degenerate — **do not use it**.
* Reference software: <https://dtai.cs.kuleuven.be/software/sar>. Paper's own experiments use sklearn
  logistic regression as base learner with propensities generated in `p_low = 0.2` to `p_high = 0.8`.

**M — what the fitted model actually produced** (`evidence/submission_build.json`): propensity
range **[0.0124, 0.4446]**, mean over labelled positives matching the anchor, Horvitz–Thompson
prevalence **π = 0.0509**, **2.0%** of weights clipped at 10.

**I — interpretation of the propensity range:** `e` never reaches the paper's `p_high = 0.8`. In this
catalogue even the most strongly selected terrain labels fewer than half its faults, which is
consistent with <25% detailed map coverage and *inconsistent* with any assumption that well-mapped
terrain is exhaustively mapped. **This is the single most useful reusable finding in this document:**
do not treat any part of the Great Basin catalogue as complete.

**M — belief transform used for emission:** posterior belief that a pixel is an *unlabelled* fault =
`f(1−e) / (1 − f·e)` where `f = P(y=1|x)`. Pixels with high `e` are discounted, because a fault there
would probably already be in the catalogue (and is masked out of scoring anyway).

---

## 6. Metric algebra (all brute-force verified to 1e-9 in `tests/test_metric.py`)

With α = 0.2, β = 0.8, R = 3 px, kernel `k(d) = (1 − d/R)₊`:

```
T = TP_w = Σ_g max_{x: d(x,g) ≤ R} p(x) k(d(x,g))
S = Σ_x p(x)                      (emitted mass)
M = Σ_x p(x) · max_g k(d(x,g))     (mass-weighted kernel coverage)
K = |G|                            (number of withheld truth pixels)
FN_w = K − T                       (exact algebraic identity)
FP_w = S − M
DTI  = T / (α(T + S − M) + βK)
```

* For well-separated dots `M = T`, so `T + FP_w = N` (dot count) and **`DTI = T / (0.2 N + 0.8 K)`**.
* A dot pays **iff** its realised kernel credit `> 0.2 · DTI` (0.0520 at DTI 0.26; 0.0556 at 0.2778;
  0.0652 at 0.3262).
* **M** Registry evidence: across 15 prior-submission rasters, owner-reported score **decreases
  monotonically with dot count** (0.2778 @ 37,654 dots … 0.2376 @ 40,000 … 0.2600 @ 44,090). Fitting
  one common credit-per-dot across the two best points gives a *negative* K, so the 0.2778 gain came
  from **pruning low-credit dots**, not from adding mass.
* **I** — the marginal-value rule is the whole strategy: at ~44,090 px of mass, reaching 0.3262 needs
  T to go from ~3,937 to ~4,939, i.e. **+25% more true detections at the same budget**. This is a
  **detector problem, not an emission problem**. No amount of smoothing, thinning or kernel tuning
  substitutes for it.

---

## 7. Submission-format failure modes (both engineered out here)

**M/V** — the official contract: same CRS as the training data (**EPSG:32611**), same resolution
(**100 m**), *"same bounds as the training data, and data outside the bounds is null or nan"*,
*"a single layer with datatype of 32-bit float (float32) with values between 0 and 1"*.

Two mechanisms produce the user-reported rejection **"Predicted values must be in range [0, 1]"**:

* **M1 — float32 sentinel inside the footprint.** `training_features.tif` declares nodata as
  `−3.4028234663852886e+38` (float32 minimum, *not* NaN). Measured: **3,061–3,073** sentinel
  band-pixels per band lie **inside** the 5,167,373-px scoring footprint. A pipeline that does not
  replace them ships −3.4e38.
* **M2 — footprint mask mismatch.** Deriving the footprint from band 1 (`!= sentinel`) gives
  5,165,852 px — **1,521 px smaller** than the template's — which strands scored pixels as NaN. NaN
  fails any `((v >= 0) & (v <= 1)).all()` check.

Fix (in `src/gems65/submission.py`, applied to every arm): footprint read from the pinned
`sample_submission.tif`; every in-footprint output pixel a finite float32 in [0,1]; median-filled
covariates inside the footprint (otherwise `np.median` silently returns NaN and you get a NaN design
matrix and DTI 0.0 **with no exception**); two variants written — `-nan` (official literal reading)
and `-zeros` (also passes a naive whole-array range check). Both verified by an independent 14-point
re-read in `scripts/validate_submission.py`.

---

## 8. Known-defective artifact (do not reproduce)

**M** — `gems32-h19-5-smoothmaxcov-44090.tif`: **25,485 / 44,090 dots (57.8%) lie off its own belief
field**, owner-reported score **0.01632**. An emitter that does not respect its own ranking destroys
the signal. Every emitter in this repo asserts agreement between the emitted dots and the belief
field before writing.

---

## 9. Reusable operating rules extracted from this lane

1. **Fix shared-tool bugs in the shared module, never in a fork.** Two critical bugs found here
   (`IR-65-002` eligibility dilation, `IR-65-003` positional tie-breaking Spearman) were silent — no
   exception, plausible-looking output, and each would have killed the lane on a false signal.
2. **Distrust any rank correlation computed on sparse rasters.** `argsort(argsort(x))` breaks ties by
   array position; on 99.3%-zero fields it returns ρ ≈ 0.97 for *independent* fields. Use
   `scipy.stats.rankdata(method="average")`. Measured: buggy 0.9717 vs correct 0.0000.
3. **Check that an EM log-likelihood increases.** Here it *decreased* monotonically (−0.483 → −0.612)
   because the initialisation deviated from the paper. A degenerate fixed point looks like
   convergence if you only watch the delta.
4. **Run a leakage canary before trusting any holdout number.** Each feature alone on the holdout;
   AUC > 0.90 = leakage until proven otherwise. Measured max here: **0.5738** over 28 features —
   clean, which is why the negative result is credible rather than an artifact.
5. **Label every number's evidence class.** HOLDOUT-DTI (proxy), MIRROR-DTI (instrument),
   OWNER-REPORT (unverified receipt), ORGANIZER-CONFIRMED (only from a submission-page receipt). All
   15 registry scores are OWNER-REPORT; **zero** numbers in this repo are ORGANIZER-CONFIRMED.
6. **Calibrate the instrument before trusting it.** `scripts/05_holdout_calibration.py` scores nine
   owner-reported-live rasters on the same blocked cells and reports Spearman(holdout, live). If that
   correlation is weak, holdout deltas are noise.
7. **A negative result that survives its own sensitivity sweep is a real result.** No `a_bar` in
   {0.15, 0.25, 0.32, 0.50} made the SAR arm pass, so the gate failure is not an artifact of the one
   unidentified nuisance parameter.
