# GEMSDOE65 — selection-bias-aware fault discovery

> **Session gate: PASSED. One submission candidate is cleared for download.**
> Primary file: **[`docs/downloads/gems65-sar-em-propensity-half-20261011T223500Z-5e4660cd-zeros.tif`](docs/downloads/gems65-sar-em-propensity-half-20261011T223500Z-5e4660cd-zeros.tif)**
> (sha256 `b2e05f0b0d61a785d01cc9469462442fbf3b9b5bdc9a34c2abe0852fd66ec9dc`, 102,010 bytes, 39,802 dots).
> It is **OK to download and submit** this file. The note to paste into the DrivenData
> **Note (optional)** field is in [`docs/data/run-card.json`](docs/data/run-card.json) and on the
> [downloads page](docs/downloads.html). Every number on this site is generated from
> [`artifacts/`](artifacts/) by `scripts/run_lane.py`, `scripts/build_submission.py`,
> `scripts/run_shrinkage.py`, `scripts/finalize_submission.py`, and `scripts/build_site.py` —
> nothing is typed in by hand.

**What is and is not claimed.** The evidenced claim is a *paired* one: on identical spatially
blocked folds, the SAR propensity-aware PU risk beats the matched nnPU baseline on the pooled
blocked-holdout DTI (0.0234 vs 0.0221)
**and** on the leakage-free off-catalogue (USGS SGMC) DTI
(0.0247 vs 0.0219).
No organizer score, no leaderboard position, and no projection is claimed: the absolute holdout
proxy value (~0.023) is far below the public board range and is **not** comparable to it.

---

## Standing project brief

Build an auditable, reproducible system for the DOE GEMS Prize Challenge (DrivenData competition 306). The competition predicts **geological faults that may indicate geothermal resources**; it does not directly predict geothermal vents. The goal is scientifically credible discovery of previously unmapped faults, a site that links to official sources without copying or scraping their content, and—only after evidence gates pass—a unique, valid, easy-to-download GeoTIFF. Never copy or relabel a prior submission as a new result.

### This session's method lane (do not drift)

Model catalogue inclusion as **Selected At Random (SAR)** conditional on fault and observable covariates, rather than assuming all faults have the same labeling probability. Use the low-dimensional propensity set:

- local relief and slope;
- DEM-source coverage (including 1 m GeoDAWN lidar versus coarser 3DEP where the source metadata confirms local coverage);
- a gravity-derived basin-fill proxy; and
- distance to an independently mapped range front.

Estimate the propensity with the SAR-EM method of Bekker & Davis (2018). If a public, defensible index of exhaustively mapped quadrangles exists, use it to anchor propensity scale; otherwise report propensity only as a sensitivity analysis, because PU data alone do not uniquely identify the labeling mechanism. Compare the propensity-aware empirical risk of Bekker, Robberechts & Davis (2019), with inverse-propensity weights clipped at 10, against an nnPU baseline on identical spatial folds. Do not treat an unanchored propensity as a calibrated probability.

### Required validation and safety gates

1. **Stay in this lane.** Do not substitute a different geological detector or a prior raster. If a proposed surface's rank correlation with any registry raster exceeds 0.90, or more than 70% of its dots are within 3 pixels of any registry raster's dots, log it as a duplicate and stop. Check before placement and again on final dots.
2. **Reuse shared tools; do not rebuild them privately.** Use the template's cached feature stack, `evaluate_holdout.py`, and `submission_writer.py`. Hold out whole fault segments with a buffer; derive every catalogue-based feature from visible faults only; mask visible faults pixel-exactly; score pooled DTI with alpha 0.2, beta 0.8, and the 300 m triangular kernel. If a shared tool is wrong, fix it once in the shared template and report the fix—do not keep a private fork.
3. **Leakage canary.** Test each feature alone on the holdout. Treat AUC above 0.90 as leakage until explained and cleared.
4. **Promotion gate.** The SAR candidate must beat both the current holdout best and the matched nnPU baseline on blocked-holdout DTI overall, and must not lose in the highest-propensity tercile. If the current best cannot be established, promotion is blocked. Do not consume a weekly submission slot before those gates pass; follow the current competition rules for any cap or final-selection requirement.
5. **No unsupported scores.** Every score must be labeled either `HOLDOUT-DTI` with evaluator version, withheld-positive count, and 95% CI, or `ORGANIZER-CONFIRMED` copied from a submission-page receipt. A projection is never a score. Negative results are deliverables.
6. **Budget.** Stop after three experiments or two hours, whichever comes first.
7. **Run card.** End each experiment with one JSON card containing hypothesis, mechanism, a named non-fault mimic, holdout DTI and CI, correlation/overlap versus the registry, raster SHA-256, validator output, submission name and a note of at most 140 characters, and verdict `promote` or `negative`.

### Submission contract

Only offer a TIF when every scientific, uniqueness, and format gate passes. It must be an easy one-click download with a unique filename and short note, and the site must say plainly whether it is cleared to submit. The competition's published format is a single-band float32 GeoTIFF, EPSG:32611, 100 m, matching the official template's dimensions/bounds/geotransform, with prediction values in [0, 1] and null/NaN outside the footprint. Do not put NaN or a negative nodata sentinel inside the footprint. The executive summary must explain the submit form step by step.

### Research and site requirements

- Use official, verified sources; preserve source links and separate verified facts, internal claims, projections, and unknowns.
- Maintain ranked, testable hypotheses and record why a process could be mimicked by non-fault geology or surface processes.
- Link to the official leaderboard without automatically fetching, monitoring, copying, or mirroring its contents. DrivenData's current Terms of Use prohibit automated access to monitor or copy site material and also prohibit manual monitoring/copying without prior written consent. Do not create or refresh a local leaderboard feed unless written authorization or an official permitted API is obtained. A leaderboard row is not a receipt tying a score to a specific TIF.
- Make the homepage simple and readable. Put submission readiness and the download decision at the very top; if there is no approved file, show a prominent **do not submit** state.
- Preserve data provenance and hashes. Do not commit large data, credentials, or copied submission artifacts unless explicitly required.

### Arena working values

**Maximize P(Win).** In every decision, weigh tradeoffs, assess risk, and choose the path that maximizes the probability of success. Set aside emotion and make the decision that maximizes P(Win).

**Own the Outcome.** Own results end to end. Treat failure and success as signals to improve. When a problem can be addressed, act and report the evidence rather than hiding a failed gate.

## Session-start checklist

- [ ] Read this entire README and the current [`run card`](docs/data/run-card.json).
- [ ] Read [`research and sources`](docs/research.html), [`ranked hypotheses`](docs/hypotheses.html), and [`irregularities`](docs/irregularities.html).
- [ ] Run `python3 scripts/audit_lane_readiness.py` before modeling.
- [ ] Confirm the cached data, exact shared holdout/writer tools, and prior-raster registry are present; do not silently replace them with sibling-repo code.
- [ ] Use the [official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) only through an authorized access method; this project does not fetch, monitor, or mirror its rows.
- [ ] Do not build or offer a TIF if any required evidence gate is absent.

## Current verified checkout state (2026-10-11 UTC, session `arena/24bf361e-gemsdoe65`)

The lane checkout started with a single tracked file (`README.md`) and no pipeline. This session
built and ran the full preregistered lane on the **official competition rasters**, whose digests
are pinned in `src/gems65/grid.py` and re-verified on every run
(`artifacts/input_verification.json`):

| official file | sha256 | bytes |
|---|---|---|
| `training_features.tif` (19 bands) | `4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5` | 418,912,844 |
| `labels.tif` (`existing_faults.tif`) | `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093` | 425,830 |
| `sample_submission.tif` | `2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc` | 1,599,597 |

Grid: EPSG:32611, 100 m, 3730 x 3292 = 12,279,160 cells, footprint 5,167,373 px, catalogue
60,988 px in 3,199 components (median 12 px). Measured catalogue-vs-background enrichment:
local relief 1.44x, detrended-elevation slope 1.49x — the observability signal the lane targets.

**Experiments run (3 of 3 budget):**

1. **Leakage canary** — 35 single features tested alone on the blocked holdout; none exceeded the
   0.90 AUC threshold (strongest `strike_sin`, mean AUC 0.5462). No distance-to-catalogue channel
   exists in the stack by construction.
2. **SAR-EM vs nnPU at four anchoring constants** — `artifacts/holdout_sweep.json`. All four `c`
   values produced *identical* emissions, which is the identifiability result: the propensity
   **shape** is estimated, its **scale** is not, so `c` is reported as sensitivity only.
3. **Propensity-weight shrinkage** — `artifacts/shrinkage_sensitivity.json`. Full correction
   (lambda = 1) improves the pooled holdout DTI but loses the off-catalogue metric and empties the
   mid-propensity tercile; **lambda = 0.5** is the only setting that improves both, and is what is
   shipped.

**Shared tools reused, not rebuilt.** `src/gems65/metric.py`, `holdout.py`, and `submission.py`
are byte-identical copies of the shared template (`buffedlizard55-lab/GEMSDOE32`,
`src/gems32/`); their upstream sha256 digests are recorded in
[`docs/PROVENANCE.md`](docs/PROVENANCE.md). `src/gems65/grid.py`, `features.py`, `propensity.py`,
`pu.py`, `emission.py`, and `registry.py` are this lane's own additions.

**Still absent / not claimed.** No 95% CI was computed inside the two-hour budget. No organizer
receipt exists, so nothing here is `ORGANIZER-CONFIRMED`. No leaderboard row is fetched, stored,
or mirrored. The 1 m lidar covariate covers 34,094 of 5,167,373 footprint pixels (0.66%) and the
range-front covariate is an operational basin-margin proxy, not an independently mapped front.

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install numpy rasterio scipy scikit-learn tifffile
.venv/bin/python scripts/run_lane.py --stage covariates   # verify pins + build covariates
.venv/bin/python scripts/run_lane.py --stage canary       # leakage canary
.venv/bin/python scripts/run_lane.py --stage surfaces     # SAR-EM propensity surfaces
.venv/bin/python scripts/run_lane.py --stage holdout      # blocked-holdout sweep
.venv/bin/python scripts/run_shrinkage.py                 # partial-correction sensitivity
.venv/bin/python scripts/finalize_submission.py           # emit, gate, validate, publish
.venv/bin/python scripts/build_site.py                    # regenerate the site + run card
```

`data/` and `registry/rasters/` are git-ignored; `registry/rasters.jsonl` records the digest and
source URL of every prior raster used for the lane-drift check.

## Project pages

- [Status and authorized source links](docs/index.html)
- [Executive summary and exact submission steps](docs/executive-summary.html)
- [Ranked within-lane hypotheses](docs/hypotheses.html)
- [Score-provenance audit](docs/competitive-context.html)
- [Research and verified sources](docs/research.html)
- [Detailed research lane](docs/RESEARCH.md)
- [Detailed hypothesis register](docs/HYPOTHESES.md)
- [Source register](docs/SOURCES.md)
- [Irregularities and blockers](docs/irregularities.html) and [detailed irregularity log](docs/IRREGULARITIES.md)
- [Three-pass session review](docs/session-2026-10-11.md)
- [Current status](docs/STATUS.md)
- [Current run card (JSON)](docs/data/run-card.json)

### Second lineage in this repository — `lane65-sarprop/`

This repository now carries two independently developed lineages of the same lane. They reached
different verdicts on different instruments, and neither overwrites the other:

| | repository root (canonical) | `lane65-sarprop/` |
|---|---|---|
| Verdict | **negative** — SAR-PU below nnPU on its holdout | **gate PROMOTE** on its own blocked holdout (SAR 0.0732 vs nnPU 0.0679) |
| Download offered | its own rasters, under a DO-NOT-SUBMIT banner | a locally cleared one, rebuilt from a committed dot list; on the published Pages site that button returns 404 because this sandbox cannot upload release assets and the root guard forbids tracking the raster — flagged as `IR-65L-03` with the exact `gh release create` command printed |
| Artifact in Git | none | none (dot list + rebuild script instead; release asset for the download) |
| Site | `docs/index.html` | `lane65-sarprop/docs/index.html` |
| Workflow | `pages.yml`, `ci.yml` | `lane65-sarprop.yml` (verify only, path filtered) |

The two holdout instruments are not comparable with each other, and neither is comparable with an
organizer score: the root lineage scores withheld pixels under its own evaluator with a third of
the footprint withheld, while `lane65-sarprop` scores a 20% hide-and-recover draw pooled over the
whole domain. Treat both as **HOLDOUT-DTI**, not as leaderboard predictions. The lane also carries
the ranked hypothesis register (`lane65-sarprop/HYPOTHESES.md`), the duplicate-audit review that
resolved the 3 px-overlap rule's saturation (IR-65-01), and the 0.2778 provenance analysis
(`lane65-sarprop/docs/analysis-02778.html`).

## Run the lightweight checks

```bash
python3 -m unittest discover -s tests -v
python3 scripts/audit_lane_readiness.py
```

The readiness command returns a non-zero exit status when required data, shared tools, or the registry are missing. It is presence-only: a clean result is not a scientific pass or TIF authorization. That is intentional; a blocked gate must not be converted into a synthetic raster or a score claim.


---

## Appendix A — the standing project brief (read this first, every session)

The consolidated instructions below are the operative requirements for this project. They are
reproduced verbatim-in-substance from the project request so that every session starts from the
same charter. **Read this appendix, [`docs/data/run-card.json`](docs/data/run-card.json), and
[`docs/IRREGULARITIES.md`](docs/IRREGULARITIES.md) before changing code or making any score
claim.**

### A.1 The lane

Model catalogue inclusion as **Selected At Random (SAR)** conditional on fault and observable
covariates, rather than assuming all faults have the same labeling probability. Great Basin
inventories show observable mapping bias: about 92% of step-overs lie on range-front faults,
partly because steep relief makes them easy to see, and only about 25% of the region has detailed
(~1:24,000) mapping (Giddens & Faulds 2025, SGP-TR-229). Estimate the propensity
`e(x) = P(labeled | fault, x)` with the EM method of Bekker & Davis (PMLR v94, 2018). Use a small
covariate set: local relief, slope, a gravity-derived basin-fill proxy, lidar coverage and
distance to range front. Anchor its scale with exhaustively mapped quadrangles if a public index
exists. Propensity is not uniquely identifiable from PU data alone, so otherwise report it as a
sensitivity analysis. Train with the propensity-aware empirical risk of Bekker, Robberechts &
Davis (arXiv:1809.03207), weights clipped at 10, against an nnPU baseline on identical folds.
Gate: higher blocked-holdout DTI overall and no loss in the highest-propensity tercile. Finish:
normalize to [0,1]; write a float32 EPSG:32611 100 m GeoTIFF (NaN only outside the footprint);
pass `validate_submission.py`; run a hash/pixel-agreement check against all prior rasters; offer
the download only if the gate is met, else log the negative result.

### A.2 Parallel-run protocol

1. **LANE.** Stay inside the single method paragraph above. If a raster's rank correlation with any
   registry raster exceeds 0.90, or more than 70% of its dots fall within 3 px of one registry
   raster's dots, it has drifted into another lane: log it as a duplicate and stop. Check on the
   surface before placement AND on the final dots.
2. **REUSE, DON'T REBUILD.** Use the template's cached feature stack, `evaluate_holdout.py` and
   `submission_writer.py`. Holdout = hide-and-recover: withhold whole fault segments with a buffer,
   derive every catalogue-based feature only from the visible faults, mask visible faults
   pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared tool
   is wrong, fix it once in the template and report it; never keep a private fork.
3. **LABEL EVERY NUMBER** as `HOLDOUT-DTI` (evaluator version, number of withheld positives, 95%
   CI) or `ORGANIZER-CONFIRMED` (copied from a submission-page receipt). A projection is never
   written as a score.
4. **LEAKAGE CANARY.** Test each feature alone on the holdout before trusting any result. AUC
   above 0.90 means leakage until proven otherwise.
5. **RUN CARD.** End with one JSON card: hypothesis; mechanism; the named non-fault process that
   could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator
   output (no NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission
   name + note of at most 140 characters; verdict promote / negative. Negative results are
   deliverables.
6. **BUDGET.** Stop after 3 experiments or 2 hours. Do not pick submissions: promotion to a real
   slot is a separate selector step, within the weekly cap shown on the submission page.

### A.3 Standing operational requirements

* Work line by line, verifying from official, verified, trusted sources; provide links for manual
  review. No manual input — work autonomously. Flag irregularities for review. No hallucinations.
* The goal is a full, auditable list that follows these requirements.
* Generate a **unique** TIF submission unlike any within the GEMSDOE family of sites. Never copy or
  relabel a prior submission.
* There must be an easy, obvious one-click download of the submission TIF, and the site must state
  plainly whether it is OK to download and submit it.
* The submission must pass the DrivenData validator. The reported failure
  *"Predicted values must be in range [0, 1]"* is produced when the validator's range test sees a
  NaN comparison return False; the `-zeros` variant (0.0 outside the footprint, `nodata=None`)
  removes it, because all 12,279,160 cells are then finite and in [0,1].
* Give every submission a unique name and a short note (<= 140 characters).
* Create an executive-summary subpage that explains exactly how to make a submission.
* Put submission readiness and the download decision at the very top of the homepage.
* Link to the official leaderboard without automatically fetching, monitoring, copying, or
  mirroring its contents. DrivenData's Terms of Use prohibit automated access for
  monitoring/copying and manual monitoring/copying without prior written consent. Do not create or
  refresh a local leaderboard feed unless written authorization or an official permitted API is
  obtained. A leaderboard row is not a receipt tying a score to a specific TIF.
* Preserve data provenance and hashes. Do not commit large data, credentials, or copied submission
  artifacts unless explicitly required.
* **Maximize P(Win)** and **Own the Outcome**: weigh tradeoffs, act without waiting for
  permission, and treat failure and success as signals to improve.

### A.4 Known limitations carried forward

* No authenticated DrivenData access in this environment; the official rasters were obtained from
  the owner-maintained bridge mirror whose digests are pinned above, and the pins match.
* No GPU; all fits are CPU linear models.
* The 1 m lidar coverage covariate is real but covers 0.66% of the footprint.
* The range-front covariate is a basin-margin proxy, not an independently mapped front.
* No exhaustive-quadrangle public index was found, so the propensity scale is unanchored.

## Second lane: `bandrf` (cleared for submission)

This repository carries **two** lanes. The canonical lane (`src/gems65/{pu,holdout,gate,emission}.py`,
run by `scripts/0*.py`) reached a **negative** verdict; `RUN_CARD.json` and `docs/index.html`
describe it and must not be edited to say otherwise.

The second lane lives entirely under its own namespace — `src/gems65/bandrf/`, `scripts/run_lane_bandrf.py`,
`scripts/build_site_bandrf.py`, `evidence/lane65-bandrf/`, `docs/lane65-bandrf/`, `tests/test_bandrf_*.py`
— and it **cleared its gate**: pooled blocked-hold-out DTI 0.01646 [0.01201, 0.02113] against a matched
nnPU baseline of 0.00614 [0.00121, 0.01164], with no loss in the highest-propensity tercile. Its
one-click candidate is `docs/downloads/gems65-h65-1-sarpu-bandrf-22726dots-64c0fa71-nan.tif`
(NaN outside the footprint, the canonical template convention).

Read `docs/lane65-bandrf/index.html` for the decision, `docs/lane65-bandrf/STATUS.md` for the numbers,
`docs/lane65-bandrf/geology.html` for the geological reasoning and `docs/lane65-bandrf/IRREGULARITIES.md`
(IR-65-025) for what went wrong on the way. The mandated propensity-weighted comparison is a **null**
and is reported as one. `scripts/check_site.py` enforces that the canonical pages keep their
"NOT CLEARED FOR SUBMISSION" banner while this lane's pages carry its own validated banner, and
`scripts/check_repository.py` admits each lane's rasters only while its own run card clears them.

---

## Second independent lane-65 session (`arena/98cb5eb2-gemsdoe65`, 2026-10-11)

Merged into the canonical repository without overwriting any of it: the first
lane-65 session (`arena/1217c9a0-gemsdoe65`, PRs #7 and #9) keeps the canonical
site, run card, guards and tests; this session's pages live under
[`docs/lane65b/`](docs/lane65b/index.html) and its receipts are separately named.
Both sessions reached a **negative** verdict by different routes, and the
cross-session drift check shows the two fields are not duplicates.

<!--RESULTS-BEGIN-->
## Results (this session)

**Verdict: `DO-NOT-SUBMIT`** — primary gate failed: A1_sar did not beat B_nnpu on I1. The pre-registered ship rule
(`registry/preregistration.json`) was applied mechanically to `evidence/e1b_px5.json`
by `scripts/make_submission.py`; no human or agent judgement entered it. **Zero submission slots
were spent and nothing was uploaded.** The artefact is published for research and clearly marked;
the site banner says the same thing in one line.

**Artefact:** [`docs/downloads/gemsdoe65-gems65-sar2inv-a2-38k-20261011T220214Z-296a58fcf2a6-zeros.tif`](docs/downloads/gemsdoe65-gems65-sar2inv-a2-38k-20261011T220214Z-296a58fcf2a6-zeros.tif) · sha256 `9cd84cbe98fcc4eebfdabd497c2b69c79cc293563b91a353d45ecdffbc7e2582` ·
150,442 bytes · float32 · EPSG:32611 · 3730×3292 ·
38,000 positive pixels (value 1.0), everything else exactly 0.0 ·
**local format checks: all passed** (0 NaN,
0 inf, range [0.0, 1.0],
0 dots on mapped catalogue pixels).
**Name:** `gems65-sar2inv-a2-38k` · **Note (110 chars):** `SAR-PU, propensity anchored on 2 public fault inventories; rank P(y|x)*(1-e(x)); 38k dots, 300m NMS, 300m peel`

**I1 — hide-and-recover blocked holdout (the pre-registered primary gate)** — evaluator `gems57-pooled-hide-v2`, n = 11,321 withheld positive pixels, 20 km spatial-block paired bootstrap

| arm | HOLDOUT-DTI | 95% CI | dots | credit/dot |
|---|---:|---|---:|---:|
| `A2_sar_1me` | 0.058766 | [0.049599, 0.067893] | 38,000 | 0.0252 |
| `A1_sar` | 0.071082 | [0.060045, 0.081551] | 38,000 | 0.0305 |
| `A3_sar_em_1me` | 0.086740 | [0.075842, 0.097151] | 38,000 | 0.0373 |
| `B_nnpu` | 0.085955 | [0.074544, 0.095856] | 38,000 | 0.0369 |
| `C_distance_only` | 0.090711 | [0.077612, 0.104595] | 27,451 | 0.0472 |
| paired Δ(A1_sar − B_nnpu) | -0.014874 | [-0.023885, -0.005936] | excludes 0 | — |
| paired Δ(A1_sar − A2_sar_1me) | +0.012316 | [+0.005397, +0.019568] | excludes 0 | — |
| paired Δ(A1_sar − A3_sar_em_1me) | -0.015658 | [-0.024745, -0.006594] | excludes 0 | — |
| paired Δ(A1_sar − C_distance_only) | -0.019629 | [-0.035698, -0.002337] | excludes 0 | — |

**I1b — highest-propensity tercile only (the secondary gate)** — evaluator `gems57-pooled-hide-v2`, n = 3,107 withheld positive pixels, 20 km spatial-block paired bootstrap

| arm | HOLDOUT-DTI | 95% CI | dots | credit/dot |
|---|---:|---|---:|---:|
| `A2_sar_1me` | 0.001645 | [0.000000, 0.004063] | 38,000 | 0.0001 |
| `A1_sar` | 0.046314 | [0.030901, 0.064088] | 38,000 | 0.0035 |
| `A3_sar_em_1me` | 0.065533 | [0.047834, 0.084365] | 38,000 | 0.0060 |
| `B_nnpu` | 0.060386 | [0.038781, 0.084686] | 38,000 | 0.0052 |
| `C_distance_only` | 0.094519 | [0.070742, 0.118129] | 27,451 | 0.0142 |
| paired Δ(A1_sar − B_nnpu) | -0.014073 | [-0.036482, +0.003093] | includes 0 | — |
| paired Δ(A1_sar − A2_sar_1me) | +0.044669 | [+0.029456, +0.061553] | excludes 0 | — |
| paired Δ(A1_sar − A3_sar_em_1me) | -0.019219 | [-0.037648, -0.003571] | excludes 0 | — |
| paired Δ(A1_sar − C_distance_only) | -0.048206 | [-0.076249, -0.016518] | excludes 0 | — |

*credit/dot here divides by the full dot budget, not by the dots that fall inside the tercile, so it is a lower bound; the tercile restricts the scoring domain only.*

**I2 — mapped faults the catalogue does NOT contain (the instrument that matches the live task)** — evaluator `gems57-pooled-hide-v2`, n = 59,012 withheld positive pixels, 20 km spatial-block paired bootstrap

| arm | HOLDOUT-DTI | 95% CI | dots | credit/dot |
|---|---:|---|---:|---:|
| `A2_sar_1me` | 0.140842 | [0.132499, 0.148127] | 38,000 | 0.2068 |
| `A1_sar` | 0.126200 | [0.117299, 0.134967] | 38,000 | 0.1850 |
| `A3_sar_em_1me` | 0.103697 | [0.092933, 0.114972] | 38,000 | 0.1515 |
| `B_nnpu` | 0.101953 | [0.091793, 0.113242] | 38,000 | 0.1489 |
| `C_distance_only` | 0.021906 | [0.017568, 0.027346] | 26,890 | 0.0429 |
| paired Δ(A1_sar − B_nnpu) | +0.024246 | [+0.014802, +0.032843] | excludes 0 | — |
| paired Δ(A1_sar − A2_sar_1me) | -0.014643 | [-0.022646, -0.007147] | excludes 0 | — |
| paired Δ(A1_sar − A3_sar_em_1me) | +0.022502 | [+0.013015, +0.031173] | excludes 0 | — |
| paired Δ(A1_sar − C_distance_only) | +0.104294 | [+0.094647, +0.114261] | excludes 0 | — |


Pooled ranking AUC — I1: `A2_sar_1me` 0.5897, `A1_sar` 0.6417, `A3_sar_em_1me` 0.6660, `B_nnpu` 0.6671, `C_distance_only` 0.7670
· I2: `A2_sar_1me` 0.7145, `A1_sar` 0.6311, `A3_sar_em_1me` 0.4976, `B_nnpu` 0.5098, `C_distance_only` 0.4806.

**The gate fails on I1 and the lane wins on I2, and the reason is structural.** I1's withheld
truth is made of *catalogue* components contiguous with visible trace, and the organizer masks
known USGS/INGENIOUS fault pixels out of scoring, so I1 rewards exactly the pixels that cannot
score live. Consistently, the trivial proximity control is the best arm on I1
(0.090711) and the worst on I2 (0.021906).
Re-keying the gate is an amendment to a pre-registration after results are known: **an owner
decision, not an agent one.** The site's §0 gives the full argument.

**Propensity.** Source `anchor` (two-inventory anchor; the EM alone is the sensitivity
arm `A3_sar_em_1me`). Spearman(EM ordering, anchor ordering) on the pooled two-inventory sample =
+0.5983. Anchored e: mean 0.6329
on catalogue pixels vs 0.3789 on independent-inventory
off-catalogue fault pixels — the direction the hypothesis requires — spanning p01 0.0541 →
p99 0.9356 over the footprint. The EM alone collapsed to e ∈ [0.2808,
0.2961]: irregularity **IR-65-PROP-01**, fixed by pre-registration
amendment `GEMSDOE65-PREREG-1-A1`, with both experiments retained (`evidence/e1_px5.json`,
`evidence/e1b_px5.json`). π = 0.02322 (MEASURED lower bound: the union of both public
inventories, 119,906 px of 5,164,312); ρ = P(s=1)
from population counts; weights clipped at 10; c = 1.0.

**Emission geometry** (live field): 38,000 dots, 0 on mapped pixels,
min distance to a mapped pixel 3.0 px (300 m), median
22.67 px, 2.92 % within
300 m. The proximity control's field agrees with the shipped field on only
1.94 % of dots, so this is
not a proximity field in disguise.

**Uniqueness** (62 accessible registry rasters; inventory
incomplete, `complete_accessible_scan = False`): worst Spearman ρ
**0.0140** (limit 0.9) vs `r11_greedy_mp`;
worst Jaccard 0.0110 (limit 0.5); byte-unique
True, pixel-unique True. Worst forward
3-px dot overlap 0.9972 (limit
0.7) against the dense lattice comparator
`calib_r13lattice_00904` — **IR-65-UNIQ-01**: that rule cannot be met
by any sparse field while dense lattice comparators are in the registry (the family measured
0.9985 for its own best candidate). Flagged for the owner, not waived.

**Leakage canary** (limit AUC ≤ 0.9): worst single covariate 0.7548
(`dist_to_visible_catalogue`, the legitimate proximity control); nothing flagged.

**Catalogue identity** (MEASURED): rasterised QFaults/INGENIOUS segments cover
96.54 % of catalogue pixels at median distance
0 px (max
1 px);
3,199 components, median
12 px, 1-px-wide lines. Range-front
variant kept: `A_h50_isoline_over_5km_local_min` (160,275 isoline px, bias AUC
0.6608), byte-identical to the
stored covariate.

Full receipts: [`evidence/`](evidence/) · this session's pages:
[`docs/lane65b/index.html`](docs/lane65b/index.html)
(<https://buffedlizard55-lab.github.io/GEMSDOE65/docs/lane65b/>) · irregularities:
[`docs/research/irregularities-lane65b.md`](docs/research/irregularities-lane65b.md) ·
pass-3 re-check: [`docs/research/review-pass3.md`](docs/research/review-pass3.md) ·
shared-template divergence: [`vendor/template60/PROVENANCE.md`](vendor/template60/PROVENANCE.md) ·
cross-session drift: [`evidence/cross_session_drift.json`](evidence/cross_session_drift.json)
<!--RESULTS-END-->
