# GEMSDOE65 · Selection-bias-aware fault discovery

## Submission status — **NEGATIVE. DO NOT SUBMIT THIS RUN.**

A **new model-derived research GeoTIFF was generated**, not copied from a prior submission. It passed local format validation but **failed the scientific and literal uniqueness gates**. It is quarantined under ignored `artifacts/`, never linked from the website. There is **no approved submission download** and **no competition slot was used**.

- **Site:** https://buffedlizard55-lab.github.io/GEMSDOE65/
- **Submission instructions:** https://buffedlizard55-lab.github.io/GEMSDOE65/docs/executive-summary.html
- **Decision:** [`evidence/run_card.json`](evidence/run_card.json)
- **Scientific / code review:** [`research/review.md`](research/review.md)
- **Preregistered hypotheses:** [`research/preregistration.md`](research/preregistration.md)
- **Source audit:** [`evidence/site_review.json`](evidence/site_review.json)

### Measured result, not an organizer score

**HOLDOUT-DTI · evaluator `gems57-pooled-hide-v2` · 60,988 withheld positive pixels · conditional 95% spatial-bootstrap CI:**

| Primary reference propensity assumption | SAR-PU | Matched nnPU | SAR minus nnPU |
|---|---|---|---|
| e(z=0)=0.50, not identified completeness | 0.023650 [0.022121, 0.025162] | 0.027917 [0.025695, 0.030419] | −0.004267 [−0.005371, −0.003370] |

**HOLDOUT-DTI · same evaluator · 34,174 withheld positives in the highest-propensity tercile:** SAR-PU 0.028454 [0.026646, 0.030418]; nnPU 0.036848 [0.034078, 0.040167]. All three scale-sensitivity experiments were negative; EM reached its iteration cap without convergence. These numbers are not comparable to user-reported leaderboard claims.

**REGISTRY-MEASUREMENT:** three rasters compared before the mandatory duplicate stop. A dense prior covers the entire footprint, giving forward overlap 1.0 under the inherited support rule. The remaining registry is not cleared. Byte/pixel difference from those three is not a uniqueness certificate.

**FORMAT-MEASUREMENT:** single-band float32, EPSG:32611, shape 3730×3292, 100 m, exact template transform, finite [0,1] inside, NaN outside. Quarantined raster SHA256:

```text
356b85a8f08e9b37ac990b1eeffaf5b8de92c424d4ed6f18d04f92011290e9a9
```

## Lane 65 result — SAR propensity-aware PU (session 2026-10-11, merged from `arena/1217c9a0-gemsdoe65`)

A second, independent implementation of the same lane, run to completion: propensity EM
(Bekker & Davis 2018 Definition 2 risk, weights clipped at 10) against an nnPU baseline on
**identical folds**, gated on 8 spatially blocked hide-and-recover cells, then built into three
38,000-dot rasters, validated, duplicate-checked against the 15-raster registry corpus and
adjudicated by one shared rule set (`src/gems65/adjudicate.py`, rules R1–R5).

**Its verdict agrees with the canonical one above: NEGATIVE — NOT CLEARED FOR SUBMISSION.**

| arm | HOLDOUT-DTI (8 blocked cells) | verdict | rule |
|---|---|---|---|
| `sar` — the lane's hypothesis | 0.06195 | **NEGATIVE** | R3 — gate not met: nnPU 0.06753, Δ -0.00558, CI95 [-0.01216, -0.00063], wins 2/8; top-propensity tercile Δ -0.01305 |
| `nnpu` — baseline | 0.06753 | **NOT CLEARED** | R4 — below the current holdout best 0.09974 (`g32-h32d-submodular-nan.tif`) |
| `em` — baseline | 0.06555 | **NOT CLEARED** | R4 — same bar |

All six files are format-valid and unique (max registry rank-correlation 0.0187, max 3-px dot
overlap 0.3642, zero mass on masked catalogue pixels, zero NaN inside the 5,167,373-px footprint,
values in [0,1]). The negative result is *clean*: leakage canary max single-feature AUC
0.5738 over 28 features, and the verdict holds across the whole propensity-anchor
sweep ā ∈ {0.15, 0.25, 0.32, 0.50} (the scale is not identified from PU data alone).

### The one finding this session adds to the canonical record

**The blocked-holdout gate is measurably anti-correlated with the live metric**
(`evidence/holdout_calibration.json`, `IR-65-006`): Spearman(holdout-DTI, owner-reported live) =
**-0.436** over 10 registry rasters, and Spearman(dot count, live) = **-0.791**.
The reason is the staff masking ruling: live scoring removes known-fault pixels, while this holdout's
truth *is* catalogue pixels — so the artifacts that score best live (0.2778 → holdout 0.00452) score
worst here, and they avoid the catalogue for exactly the reason this lane does. A second,
oppositely-biased instrument (registry-anchored mirror, Spearman **+0.804** leave-one-out)
also refuses: our best arm scores MIRROR-DTI 0.147, below 10/10 live-scored artifacts.
**Consequence for the next session:** do not use catalogue-hidden holdout DTI as the promotion gate
for an off-catalogue candidate. Either anchor truth in an independent compilation, stratify by
estimated propensity and read the low-e stratum as primary, or spend one receipt.

Two silent shared-tool bugs were found and fixed in the shared modules (never forked):
`IR-65-002` (holdout eligibility dilation never reached the withheld truth → pooled DTI ≈ 0.0008 with
no exception) and `IR-65-003` (duplicate-check Spearman ranked with `argsort(argsort(x))`, breaking
ties by array position → ρ ≈ 0.97 for *independent* sparse rasters, which would have falsely declared
lane drift and stopped the lane). Both have regression tests. `IR-65-004` (EM init) stays **open**: the
EM still does not converge, so no EM-derived number here is presented as a maximum-likelihood estimate.

### Lane 65 pages and artifacts

* `docs/lane65/index.html` — the lane result, the gate, the adjudication rules, instrument quality.
* `docs/lane65/executive-summary.html` — exactly how to make a submission (format contract, the
  `[0,1]` range-error root cause, metric algebra, where to click).
* `docs/lane65/{research,sources,irregularities,limitations,run-card}.html`
* `RUN_CARD.json` — the lane-65 run card (protocol rule 5); `registry/adjudication.json` — the
  rule-by-rule audit trail; `registry/irregularities.json` — IR-65-001 … IR-65-009.
* `docs/research/hypotheses.md` — five ranked candidate hypotheses with falsification tests;
  `docs/research/geothermal-vent-science.md` — reusable knowledge base (every line labelled V/M/I).
* `docs/downloads/*.tif` — the six built rasters. **Publication policy change, flagged as
  `IR-65-009`:** the standing user requirement is a click-to-download TIF with an obvious
  submit/do-not-submit verdict, so these *uncleared evidence artifacts* are published with a loud
  DO-NOT-SUBMIT banner. `scripts/check_repository.py` and `scripts/check_site.py` were amended with a
  narrow allowlist that still fails closed: a raster may be tracked only while **no arm is cleared for
  submission** and its sha256 matches `evidence/submission_build.json`. If any arm is ever cleared,
  publication requires an organizer-confirmed receipt record. Reverse this by deleting the allowlist
  block in those two scripts.
* Reproduce: `python scripts/00_restore_data.py && python scripts/01_prepare_data.py && python
  scripts/02_run_holdout.py --cells 8 --unlabeled 80000 --em-iters 6 --dots 40000 && python
  scripts/03_build_submission.py --dots 38000 --a-bar 0.25 --min-dist 2.8 && python
  scripts/05_holdout_calibration.py && python scripts/07_adjudicate.py && python
  scripts/06_run_card.py && python scripts/build_site_lane65.py`

## Reproduce, audit, and serve

Read this README, the original request below, `research/preregistration.md`, and the current run card **before every session**. Do not rerun a consumed holdout or reset the experiment budget to chase a positive result.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
bash scripts/download_competition_data.sh  # public GitHub bridge; integrity-pinned, not organizer-authenticated
.venv/bin/python scripts/prepare_data.py
.venv/bin/python scripts/restore_audit_priors.py  # audit only; never model inputs
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q
.venv/bin/python scripts/build_site.py
.venv/bin/python -m http.server 8000 --bind 0.0.0.0 --directory docs
```

The CI workflow runs tests and static-site safety checks on each PR/push. The existing `main:/` Pages publisher serves the static site; changing the Pages mode was permission-blocked. A separate workflow refreshes public GitHub commit metadata daily at 07:22 UTC and commits only `docs/data/feed.json` to this session’s `arena/f09c3103-gemsdoe65` branch. The browser reads that small public JSON via the GitHub API, with a dated local fallback; no token reaches the browser. Keep that branch to retain automatic feed updates. The Pages workflow only uses Actions deployment if the repository mode actually permits it. It cannot check organizer scores/caps, train, place candidates, or submit. Browser QA instructions are in `tests/browser/README.md`.

The experiment runner is `scripts/run_experiments.py`. It **refuses to overwrite existing experiment evidence**. This session has already used the three-experiment budget. `scripts/finalize_run.py` reuses recorded predictions; it does not retrain. The CLI `scripts/validate_submission.py` delegates to the pinned shared validators. A static GitHub Pages site cannot train a model in the browser and does not manufacture an arbitrary TIFF when its scientific gate fails.

Large raw inputs, caches, prior rasters, and quarantined outputs stay outside Git. Input and prior rasters are restored by immutable blob/hash pins; the model surface/TIFF is local-only, as explained below. No prior prediction enters `prepare_data.py` or the training runner. `vendor/template58` is an **unmodified, checksummed shared-template snapshot**, not a private metric/writer fork. A fresh checkout can reproduce source restoration and tests; it cannot recover the ignored research TIFF without the recorded model surface or a separately authorized reproducibility run. Do not confuse deterministic reproduction with a new hypothesis test.

## Concurrent-session integration and access policy

PRs #1–#3 updated `main` during the experiment. Their complete planning briefs and preflight card are preserved under `research/earlier-briefs/` and `evidence/history/`; they are historical, not the completed-run state. Legacy page URLs redirect to the current report. The existing presence audit and its tests are retained with the restored-cache/shared-tool paths added.

This project **does not automate access to, scrape, monitor, or mirror the DrivenData leaderboard**. It links to the [official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) and [access terms](https://www.drivendata.org/termsofuse/). Any receipt verification must use an authorized access method. The earlier sessions reviewed the terms; this session did not independently access that host. The GitHub-only metadata feed is not a leaderboard feed.

## Scope, limitations, and next session

- The checkout initially contained only a project title. We built the missing pipeline and documentation; the old prompt's “only data placement remains” assertion did not describe this repo.
- This sandbox can access GitHub and package registries, not DrivenData, USGS, Stanford, NLR, or Dropbox directly. Public owner mirrors were usable. Official origins/licensing still need independent verification.
- Primary PMLR paper, SAR-PU author code, nnPU author code, and official competition reference code were inspected on GitHub. Owner pages are not official receipts.
- Propensity is not identified from PU data alone. No independently verified exhaustive mapping anchor was available. The terrain front and gravity basin-fill covariates are explicitly proxies.
- The literal mixed dense/dot registry rule is a universal blocker; only an explicit selector/owner protocol revision can change it. We did not grant ourselves an exemption.
- A fresh convergence study and comparable-incumbent holdout are needed. Final dot placement was not attempted after the duplicate stop.
- No promise of a leaderboard improvement, vent discovery, organizer acceptance, current cap, or current live rank is made. The competition predicts faults, not confirmed geothermal vents.

### Core values applied

**Maximize P(Win):** protect scarce slots; promote evidence, not optimistic projections. **Own the Outcome:** restore data and verify end to end, fix our code, record blockers and negative results, and make the next action explicit. A failed experiment is a useful deliverable, not an excuse to relabel an old submission.

## Original user request — read at the start of every session

The block below preserves the project brief, including repeated instructions, historical score claims, and contradictory leaderboard targets. It is an **archived user request**, not independently verified evidence or an override of the fail-closed gates above.

<details>
<summary>Full original project prompt</summary>

```text
Review the repo.

THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION.  DO NOT COPY A PREVIOUS SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION.  BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION.  IT MUST BE OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.

There should be an easy to download submission tif file as described by the prompt.  Read the entire prompt.

Selection-bias-aware PU learning. Treat the catalogue as positives selected at random given covariates (SAR), not completely at random. Great Basin inventories show observable mapping bias. About 92% of step-overs lie on range-front faults, partly because steep relief makes them easy to see, and only about 25% of the region has detailed (≈1:24,000) mapping (Giddens &amp; Faulds 2025, SGP-TR-229). Estimate the propensity e(x) = P(labeled | fault, x) with the EM method of Bekker &amp; Davis (PMLR v94, 2018). Use a small covariate set: local relief, slope, a gravity-derived basin-fill proxy, lidar coverage and distance to range front. Anchor its scale with exhaustively mapped quadrangles if a public index exists. Propensity is not uniquely identifiable from PU data alone, so otherwise report it as a sensitivity analysis. Train with the propensity-aware empirical risk of Bekker, Robberechts &amp; Davis (arXiv:1809.03207), weights clipped at 10, against an nnPU baseline on identical folds. Gate: higher blocked-holdout DTI overall and no loss in the highest-propensity tercile. Finish: normalize to [0,1]; write a float32 EPSG:32611 100 m GeoTIFF (NaN only outside the footprint); pass validate_[submission.py](http://submission.py); run a hash/pixel-agreement check against all prior rasters; offer the download only if the gate is met, else log the negative result.

PARALLEL-RUN PROTOCOL — read first. This session is one of several running from this same prompt.

1. LANE. Your lane is the single method paragraph below. Stay inside it. If your raster's rank-correlation with any registry raster exceeds [0.90], or more than [70%] of your dots fall within 3 px of one registry raster's dots, you have drifted into another lane: log it as a duplicate and stop. Check this on the surface before placement AND on the final dots.

2. REUSE, DON'T REBUILD. Use the template's cached feature stack, evaluate_[holdout.py](http://holdout.py) and submission_[writer.py](http://writer.py). Holdout = hide-and-recover: withhold whole fault segments with a buffer, derive every catalogue-based feature only from the visible faults, mask visible faults pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared tool is wrong, fix it once in the template and report it; never keep a private fork.

3. LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator version, number of withheld positives, 95% CI) or ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never written as a score.

4. LEAKAGE CANARY. Test each feature alone on the holdout before trusting any result. AUC above [0.90] means leakage until proven otherwise.

5. RUN CARD. End with one JSON card: hypothesis; mechanism; the named non-fault process that could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output (no NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission name + note of at most 140 characters; verdict promote / negative. Negative results are deliverables.

6. BUDGET. Stop after [3] experiments or [2] hours. Do not pick submissions: promotion to a real slot is a separate selector step, within the weekly cap shown on the submission page.

The following sites should serve as a starting point for understanding how to generate TIF submissions.  These websites are researched, and tested and have generated TIF submissions.  But we need to generate high scoring submissions.

Here are the results from submissions into the competition, separated by ....:

WE NEED TO STUDY, ANALYZE, AND UNDERSTAND THE HIGHEST SCORE FROM THE GEMDOE SITE WHERE THE SUBMISSION TIF IS DOWNLOADED FROM WHICH IS THE FOLLOWING:

[https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html)

h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778

Why and how did this get the highest score and are we able to generate a submission that scores higher than 0.2778?

Answer the question using Phd level experience, knowledge, and judgement. Then use the answer to generate a unique TIF submission into the competition.  Must be unique submission unlike any within the GEMSDOE sites above.  Verify working line by line no hallucinations.

Current competition leaderboard GEMSDOE high score:

0.3774

[https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html)

gems-submission-20260925T001403Z-7f00890a: 0.1563

....

[https://buffedlizard55-lab.github.io/6GEMSDOE/](https://buffedlizard55-lab.github.io/6GEMSDOE/)

gems6_hgb88-topk03_33cec71ff0: 0.0286

....

[https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE3/docs/index.html)

pindrop-v4-nodes-20260925T152420Z-f347b70daa: 0.1193

pindrop-v4-discovery-20260925T152423Z-37f9d5b855: 0.0830

pindrop-v4-ridge-20260925T152422Z-4e03fc9705: 0.1152

....

[https://buffedlizard55-lab.github.io/GEMSDOE2/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE2/docs/index.html)

gemsdoe2-dual-family-union-20260925T160406Z-f68e590f: 0.1560

....

[https://buffedlizard55-lab.github.io/GEMSDOE4/](https://buffedlizard55-lab.github.io/GEMSDOE4/)

gems-submission-20260926T163915Z-237f0063: 0.0343

....

[https://buffedlizard55-lab.github.io/5GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/5GEMSDOE/docs/index.html)

gems-submission-20260926T175114Z-7f00890a: 0.1563

....

[https://buffedlizard55-lab.github.io/7GEMSDOE/](https://buffedlizard55-lab.github.io/7GEMSDOE/)

lidarscarp-ridge-top2pct-36c3a3f341c8: 0.1461

....

[https://buffedlizard55-lab.github.io/8GEMSDOE/](https://buffedlizard55-lab.github.io/8GEMSDOE/)

Hedge-v2_submission: 0.1563

....

[https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html)

2314b599: 0.0107

....

[https://buffedlizard55-lab.github.io/11GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/11GEMSDOE/docs/index.html)

gems-structural-area06-v1: 0.0202

....

[https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/12GEMSDOE/docs/index.html)

r7-nms3-dem10-scarp_0c9199f14e62:0.1294

r7-nms3-dem10-scarp_0c9199f14e62_allfinite:0.1294

....

[https://buffedlizard55-lab.github.io/15GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/15GEMSDOE/docs/index.html)

gems-tso1-20260929T005627Z-conj_alteration_mag: 0.0782

....

[https://buffedlizard55-lab.github.io/14GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/14GEMSDOE/docs/index.html)

GEMS_r5-geom-horse-ensemble_20260929T154852Z_ccbe1de0_site_e96e942f: 0.0020

....

[https://buffedlizard55-lab.github.io/17GEMSDOE/](https://buffedlizard55-lab.github.io/17GEMSDOE/)

17GEMSDOE_F-ensemble-2pct_20260930T050626Z:0.0187

....

[https://buffedlizard55-lab.github.io/18GEMSDOE/](https://buffedlizard55-lab.github.io/18GEMSDOE/)

H19-C_20260930T212401Z_c11e495e: 0.0297

....

[https://buffedlizard55-lab.github.io/19GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/19GEMSDOE/docs/index.html)

h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan: 0.1894

h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan: 0.1922

....

[https://buffedlizard55-lab.github.io/GEMSDOE10/](https://buffedlizard55-lab.github.io/GEMSDOE10/)

h16-continuation-20260927T065521077735Z-3431b83c7c: 0.0461

h20-dem10-scarp-thin-20260927T155223039488Z-ffc91a1686: 0.0921

H25-ctx-ridge-20260927T232947704150Z-6452ae1d00: 0.1280

h28-dotted-ridge-20260928T020256236880Z-6452ae1d00: 0.1839

....

[https://buffedlizard55-lab.github.io/13GEMSDOE/](https://buffedlizard55-lab.github.io/13GEMSDOE/)

20261001_r13-lattice-s5_v2_nan-outside:0.0904

....

[https://buffedlizard55-lab.github.io/16GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/16GEMSDOE/docs/index.html)

h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan: 0.1855

h18-3a-topo-geophys-x-complexity-prior-20260930-c502dfab-nan: 0.0976

h18-4-usgs-geologic-map-faults-gap-20260930-aef8f42c-nan: 0.0360

....

[https://buffedlizard55-lab.github.io/GEMSDOE21/](https://buffedlizard55-lab.github.io/GEMSDOE21/)

h19-4-reference-20260930-691e4dfa: 0.1894

....

[https://buffedlizard55-lab.github.io/20GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/20GEMSDOE/docs/index.html)

h20-1-sarnnpu-powerlaw-pi0363-tilt-wingcrack-20260930-be0e8f6b-nan: 0.1890

h20-5-continuous-pu-proxy-unverified-20260930-824ce73a-nan: 0.1859

....

[https://buffedlizard55-lab.github.io/GEMSDOE22/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE22/docs/index.html)

h23-a-dti-optimal-emission-6pct-20261002-e2ec4b49-nan: 0.1002

h23-b-dti-optimal-emission-10pct-20261002-86176698-nan: 0.0748

....

[https://buffedlizard55-lab.github.io/GEMSDOE23/](https://buffedlizard55-lab.github.io/GEMSDOE23/)

h30-arrangement-matched-habitat-20261002-0d4e02e8-nan: 0.1352

....

[https://buffedlizard55-lab.github.io/GEMSDOE24/](https://buffedlizard55-lab.github.io/GEMSDOE24/)

h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan: 0.2477

....

[https://buffedlizard55-lab.github.io/GEMSDOE25/](https://buffedlizard55-lab.github.io/GEMSDOE25/)

dotted-h19-5-d2-8-20261002-e56ea318af89-nan: 0.2600

....

[https://buffedlizard55-lab.github.io/GEMSDOE26/](https://buffedlizard55-lab.github.io/GEMSDOE26/)

dilcond-oof-v1-20261003-47629f496133-nan: 0.1223

....

[https://buffedlizard55-lab.github.io/GEMSDOE27/](https://buffedlizard55-lab.github.io/GEMSDOE27/)

topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan: 0.2449

....

[https://buffedlizard55-lab.github.io/GEMSDOE30/](https://buffedlizard55-lab.github.io/GEMSDOE30/)

d28-poisson300m-offcat-44090-20261003T233156Z-91eae1ca: 0.2600

....

[https://buffedlizard55-lab.github.io/GEMSDOE31/docs/](https://buffedlizard55-lab.github.io/GEMSDOE31/docs/)

h27-4-solo-d28-20261004-8acb75e1-nan:0.2708

....

[https://buffedlizard55-lab.github.io/GEMSDOE33/](https://buffedlizard55-lab.github.io/GEMSDOE33/)

h33d-analog-tip-stepover-r30-20261004-cb490425926e: 0.2632

....

[https://buffedlizard55-lab.github.io/GEMSDOE34/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE34/docs/index.html)

h34-scatter-q50-arr-matched-20261004T223317Z: 0.0778

....

[https://buffedlizard55-lab.github.io/GEMSDOE35/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE35/docs/index.html)

h35-06-aaa86efb25-20261004T225420098147Z-candidate: 0.0418

....

[https://buffedlizard55-lab.github.io/GEMSDOE36/docs/](https://buffedlizard55-lab.github.io/GEMSDOE36/docs/)

anderson-geothermal-pinn-38854-20261004T230000Z-9b9ea4e6-zeros: 0.2750

....

[https://buffedlizard55-lab.github.io/GEMSDOE37/](https://buffedlizard55-lab.github.io/GEMSDOE37/)

h6-physics-dotted-80k-20261005T055000Z-0bef9211631c: 0.1193

....

[https://buffedlizard55-lab.github.io/GEMSDOE38/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE38/docs/index.html)

D-step-3p0-07pct-tipProt-20261005-ecfbf59e2b48-zero: 0.0763

....

[https://buffedlizard55-lab.github.io/GEMSDOE42/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE42/docs/index.html)

xscale-worm-persistence-20261006T000541Z-nan: 0.0581

....

[https://buffedlizard55-lab.github.io/GEMSDOE43/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE43/docs/index.html)

sup01-hgb21-sep40-n40000-20261006-bc2e4e9a8d6f-nan: 0.0424

....

[https://buffedlizard55-lab.github.io/GEMSDOE45/](https://buffedlizard55-lab.github.io/GEMSDOE45/)

h51-km-faultzone-20261006-zeros: 0.0106

....

[https://buffedlizard55-lab.github.io/GEMSDOE49/](https://buffedlizard55-lab.github.io/GEMSDOE49/)

gate_ortho_w0.25-40k-20261006T213721Z-nan: 0.2376

....

[https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html)

h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778

....

[https://buffedlizard55-lab.github.io/GEMSDOE28/](https://buffedlizard55-lab.github.io/GEMSDOE28/)

h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-nan: 0.2708

h32-1-prethin-tip-euler-d2-8-20261003-31e35eee884e-nan: 0.2649

h36-1-rung30-blind-r1-20261003-b531dae0a36f-nan: 0.2710

h38-1-hf-euler-r30-r1-20261003-56a9f473edc7-nan: 0.2707

....

[https://buffedlizard55-lab.github.io/GEMSDOE29/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE29/docs/index.html)

efd28-repro-20261003-1cc7dc534d51-nan: 0.2600

repo-c0-habitat-emission-20261003-a4d439b07426-nan: 0.0041

sgmc-off-catalogue-44k-20261003-c8dcd780e3fd-nan: 0.0512

wormrank-d28-20261003-59dcaf6dd11d-zeros:0.2560

wormsurv-filter-20261003-921f10960d6e-zeros: 0.0532

xfit-c0-habitat-emission-20261003-ca879db0089a-zeros:0.0439

xfit-h41-union-qfaults-20261003-9edb34b99e3a-zeros:0.0356

....

[https://buffedlizard55-lab.github.io/GEMSDOE46/](https://buffedlizard55-lab.github.io/GEMSDOE46/)

r11f-scarp-radiometric-fusion-00e049b51218-zeros:0.1589

r12-scarp-rad-concordance-23e807e2de9f-zeros: 0.0843

....

[https://buffedlizard55-lab.github.io/GEMSDOE39/](https://buffedlizard55-lab.github.io/GEMSDOE39/)

h40-e-disc-h40e-30k-zeros: 0.0339

....

[https://buffedlizard55-lab.github.io/GEMSDOE40/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE40/docs/index.html)

h8-euler-lineament-depthcluster-20261006-785c4f5d5ce1: 0.0355

h8-euler-lineament-depthcluster-20261006-785c4f5d5ce1-hard: 0.0397

h45-eulerdepthreadcluster-20261006-f28e5cff6826-zeros: 0.0984

....

[https://buffedlizard55-lab.github.io/GEMSDOE41/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE41/docs/index.html)

h42-submission-primary: 0.0245

....

[https://buffedlizard55-lab.github.io/GEMSDOE44/docs/](https://buffedlizard55-lab.github.io/GEMSDOE44/docs/)

h46-twostageAB_20261006T160000Z_b0cfe956-zeros: 0.0715

....

[https://buffedlizard55-lab.github.io/GEMSDOE47/](https://buffedlizard55-lab.github.io/GEMSDOE47/)

h60-lidarscarp-s2p0-20261007-nanoutside: 0.0430

....

[https://buffedlizard55-lab.github.io/GEMSDOE48/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE48/docs/index.html)

h59-cover-ds-belief-b2xh33d-20261008T184547Z-b79c4c61d8d8: 0.2296

....

[https://buffedlizard55-lab.github.io/GEMSDOE50/](https://buffedlizard55-lab.github.io/GEMSDOE50/)

h59-sharpened-scarp-scatter-90k-20261007T171954Z-allfinite: 0.0764

....

[https://buffedlizard55-lab.github.io/GEMSDOE51/](https://buffedlizard55-lab.github.io/GEMSDOE51/)

h53-twostage-20261008T040951Z-9a0b32c871: 0.1047

....

[https://buffedlizard55-lab.github.io/GEMSDOE52/](https://buffedlizard55-lab.github.io/GEMSDOE52/)

h97b-candidate:

....

[https://buffedlizard55-lab.github.io/GEMSDOE53/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE53/docs/index.html)

h8-tiprelay-ridgeconcord-pr2-n80000-20261009-49bec522-zeros: 0.0159

....

[https://buffedlizard55-lab.github.io/GEMSDOE54/docs/](https://buffedlizard55-lab.github.io/GEMSDOE54/docs/)

h54c-manifest-edge-20261009T025732Z-73454bc5:0.0449

....

[https://buffedlizard55-lab.github.io/55GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/55GEMSDOE/docs/index.html)

tensor_full-n16000-sep3-20261009T211747Z-nan: 0.0290

....

[https://buffedlizard55-lab.github.io/56GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/56GEMSDOE/docs/index.html)

h56-final-dotted-ridge-d2p8-20261009T190421Z:0.0658

....

[https://buffedlizard55-lab.github.io/57GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/57GEMSDOE/docs/index.html)

h57r-joint-strata-38000dots-20261010T214547Z-00cf5b2066f1-zeros:

....

[https://buffedlizard55-lab.github.io/58GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/58GEMSDOE/docs/index.html)

ml-binary-ridge-20261012T000000Z:

....

[https://buffedlizard55-lab.github.io/59GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/59GEMSDOE/docs/index.html)

h59j-coherence-consensus-dotted-20261011T043000Z:

....

[https://buffedlizard55-lab.github.io/60GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/60GEMSDOE/docs/index.html)

:

....

[https://buffedlizard55-lab.github.io/61GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/61GEMSDOE/docs/index.html)

h61a-basement-step-20000dots-20261011T012029Z-eb2ae4bb024b-zeros:

h61o-vardepth-none-40000dots-20261011T160711Z-28d4fac611ea-zeros-zeros:

....

62GEMSDOE

:

....

The following is the leaderboard for the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

See below for more links and information related to the competition:

[https://github.com/drivendataorg/gems-prize-reference-solution](https://github.com/drivendataorg/gems-prize-reference-solution)

[https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)

[https://gbcge.org/current-projects/ingenious/](https://gbcge.org/current-projects/ingenious/)

[https://epsg.io/32611](https://epsg.io/32611)

[https://en.wikipedia.org/wiki/Tversky_index](https://en.wikipedia.org/wiki/Tversky_index)

The following is the leaderboard for the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

See below for more links and information related to the competition:

[https://github.com/drivendataorg/gems-prize-reference-solution](https://github.com/drivendataorg/gems-prize-reference-solution)

[https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)

[https://gbcge.org/current-projects/ingenious/](https://gbcge.org/current-projects/ingenious/)

[https://epsg.io/32611](https://epsg.io/32611)

[https://en.wikipedia.org/wiki/Tversky_index](https://en.wikipedia.org/wiki/Tversky_index)

We need to quickly look at the results and results from the GEMSDOE websites above.

Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each naming: the specific layer(s) involved, the physical signature being targeted (e.g., an edge-detection or curvature transform), why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already implemented in this repo. Rank them by expected DTI improvement and implementation cost. Validate the top candidate on our spatially-blocked holdout set before touching a weekly submission slot — do not spend a submission slot on an idea that hasn't beaten the current holdout best. If a candidate can't be validated without new external data, name the specific free, official source needed and check it's obtainable before proposing the idea as viable.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

We have a good understanding of how our hypothesis, methodology, calculations, analysis are done so we should be able to figure out a way to score higher on the leaderboard using previous results and scoring that we have across the sites listed above.  We need to come up with distinct and unique strategies to score higher in this competition leaderboard.  We need to start doing heavy and deep research into the part of the project that matters the most, which is the scientific discovery of geothermal vents.  We should store all of our information and knowledge that we can gather from official verified sources.  This will serve as a starting point for other projects as well.  We need to think outside the box but still be grounded in proper scientific research, we are ultimately aiming for a top prize that many others are competing for.  So it's important to be contrarian but be smart about it.  We need to find sources of data that others are over looking or areas of the project when it comes to geothermal vents.  We need to do deep research and critical thinking and come up with new hypothesis to test.

0.3195 is the highest score right now so we need to design a new strategy, research, testing, analyzing, and generating submission system than the current website.  It should be unique, take unique approaches to generating a submission that can score higher than 0.3195.

Put this prompt into the repo readme and read it everytime we work on the project as a starting point to make sure we are building what we are aiming for and have a strong base to continue building and improving on making something useful for everyday use.  It should solve the problem of having to manually check everything ourselves and having an up to date current feed.

Review the repo.

The following is taken from the Arena AI team and I think it makes a good point on building a successful project, so let's keep the Core Values and Own the Outcome as a focal point when building, developing, researching, suggesting upgrades, and implementing the work.

Our Core Values

Maximize P(Win)

“Maximize the Probability of Winning”: our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). “Maximize P(Win)” frees us from constraints and clarifies that we must put Arena first.

Own the Outcome

We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

We need to focus on being able to generate a submission into the competition.

The site should be able to generate a TIF file that is required for submission.  It should be as easy as download to click a File to submit into the competition.  This needs to be in the executive summary or the very beginning of the site.  it should be obvious when you visit the site.

I tried to submit the document that i downloaded from the site but it returned this error on the submission form:

"Predicted values must be in range [0, 1]"

Also we need to give it a unique name and A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Here is the submission page when i click submit file

New submission

File to submitNo file chosen

You can submit a single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF, with your predictions. It must match the submission format's CRS, shape, and geotransform. You may wish to review the competition rules first.

Note (optional)

A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Create a executive summary subpage that explains exactly how to make a submission into the contest.

Work on the next steps from the previous sessions first.

The goal of this project is to place top of the leaderboard in this competition.  The following is the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)

We need to create a project that can compete and place top of the leaderboard.  We need to understand the problem, collect all the data and organize it into a clean easily auditable table with official verified links for manual verification.

This is the guidelines we need to follow.[https://www.drivendata.org/competitions/306/competition-doe-gems/](https://www.drivendata.org/competitions/306/competition-doe-gems/)

Get familiar with the problem through the overview and problem description,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/). You might also want to reference additional resources available on the about page,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/).

Download the data from the data,[https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/), tab.

Create and train your own model. This reference solution,[https://github.com/drivendataorg/gems-prize-reference-solution](https://github.com/drivendataorg/gems-prize-reference-solution) implements a simple approach.

Use your model to generate predictions that match the submission format.

Tell me what are you limitations and what you need access to during this project.  We will need to find free publicly available sources and data from official and verified sources if we are to use 3rd party or external data.

this pdf outlines how submissions must be entered into the competition.

[https://docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf)

You must be able to do your own research, deep research, scientific literature research and organize the knowledge so that we can critically think through the problem and generate a solution through scientific and free publicly available information.  this must be done autonomously and must be constantly reviewed and improved upon.  Provide suggestions and improvements and implement them.

❌ No DrivenData auth → cannot auto-download training_features.tif, labels.tif, sample_submission.tif, 1m_DEM_links.csv from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (verified redirect to login)

See below for links from the above site.  See attached files for links from the above site.

[https://gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391)

Download competition data from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (requires login) to data/

See links below for competition data:

[https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&amp;st=wz4kofki&amp;dl=0](https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&st=wz4kofki&dl=0)

[https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&amp;st=8junzdyw&amp;dl=0](https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&st=8junzdyw&dl=0)

[https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&amp;st=rnino7ya&amp;dl=0](https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&st=rnino7ya&dl=0)

[https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&amp;st=zj1lag1r&amp;dl=0](https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&st=zj1lag1r&dl=0)

[https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&amp;st=srhhir10&amp;dl=0](https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&st=srhhir10&dl=0)

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Site creation

Create a github page for this repo that has clean ui, user friendly, simple and easy to use.  It should be organized and clean.

It should include all relevant information in an easy to read format with official verified links as sources for review.  Work line by line verify everything no hallucinations.

**The single remaining blocker to training is data placement**: run `bash scripts/download_competition_data.sh` on any unrestricted machine into `data/`, then `python scripts/prepare_data.py` — after that the full train→inference→validate pipeline is ready to run (GPU needed for training; metric/losses/validation all verified working here on CPU).

you need to complete the above task by yourself.  Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Run this task through multiple passes.

Pass 1: Implement the task completely and verify the result.

Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.

Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.

Do not stop after the first pass. Each pass must build on the previous one. Before finishing, verify that the final result fully satisfies the original request.  Work line by line verify everything no hallucinations.

Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project.  It should be worked on in this next session or the next session.  Work line by line verify everything no hallucinations.
```

</details>


## Corrected-scale lane-65 run — second, independent run (session `arena/832a5ec9-gemsdoe65`)

A second lane-65 run was executed independently in parallel with the run recorded above. It is
published as its own sub-site, **[`docs/lane65-corrected-scale/`](docs/lane65-corrected-scale/index.html)**,
and its card is [`registry/run-card.json`](registry/run-card.json) (the repository's canonical card
stays `docs/data/run_card.json` / `RUN_CARD.json`). **Verdict: NEGATIVE — do not submit.**

* It found and fixed a real **unit bug** in the SAR-EM recursion: a complete labelled sample was
  compared with a 1/127.7 subsample of the unlabeled pool without a sampling-fraction weight, so the
  implied hidden-positive mass was 127.7× too small and the EM fixed point was pinned near
  e(x) ≈ 1. The corrected recursion runs on pixel-population counts and yields a non-degenerate
  propensity (e_pos ∈ [0.436, 0.720], inverse weights 1.00–2.28, clip fraction 0).
* Four matched arms on identical blocked folds (only the weights differ):

  | arm | instrument | propensity | Δ (paired 95 % CI) |
  |---|---|---|---|
  | E1 (16 cells) | registered (uniform withholding) | quantile grid | −4.32e−05 [−3.87e−04, +3.17e−04] |
  | E2 (8 cells) | bias-matched, P(select) ∝ (1−ē)² | quantile grid | +1.70e−04 [−9.29e−05, +4.12e−04] |
  | E3 (8 cells) | registered, same folds as E1 | continuous RBF | −1.05e−05 [−5.38e−04, +5.99e−04] |
  | E3b (8 cells) | bias-matched, same design as E2 | continuous RBF | +3.45e−05 [−3.12e−04, +3.86e−04] |

* Artifact: `docs/downloads/gems65-sarprop-em-v2-20261011-9b1c65d-zeros.tif`
  (sha256 `5aee83cb2e55f0122432611ff46af6fdd1e5a9182f263888e03f667647315c37`, 790 718 B, 28 047 dots,
  15/15 shared-validator checks pass; the NaN variant is diagnostics only). Registered in
  `evidence/submission_build.json` under the publisher allowlist with `OK_TO_DOWNLOAD_AND_SUBMIT: false`.
* Uniqueness vs 62 priors: worst |ρ| 0.0366, no hash match, worst forward overlap 0.9975 only against a
  saturated lattice witness (a random control also scores 0.9987 there); unsaturated worst 0.9005 with
  reverse 0.019 and Jaccard 0.0047.
* Highest-value next step from that run: **emission geometry**. The shipped field sits a median of
  12.5 px from the catalogue and emits 28 047 dots — more mass than the family's owner-reported
  hidden-mass estimate (K̂ ≈ 12 226 px) — so most of it cannot pay for itself under the metric's
  `accept a dot ⇔ k > α·DTI` rule. Recipe: restrict the allowed set to a 10–40 px dilation of the
  catalogue, set the assumed truth mass from K̂, and re-test on the registered folds.
* Reproduce: `python3 scripts/build_features.py && python3 scripts/run_lane.py --seeds 20,21 --modes all,detached`
  (plus `--propensity rbf` for E3/E3b), `python3 scripts/emit_submission.py --name <unique> --note "<≤140 chars>"`,
  `python3 scripts/make_run_card.py`, `python3 scripts/build_lane65_corrected_site.py`.

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
