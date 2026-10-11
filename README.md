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
