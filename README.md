# GEMSDOE65 — Selection-bias-aware PU learning for unmapped-fault discovery (DOE GEMS Prize Challenge)

**Read this file first, every session.** It contains the standing brief (verbatim, §1), the lane
this repository is allowed to work in (§2), the current state (§3), and the rules that keep every
number honest (§4).

---

## 0. Where the submittable file is — and this session's verdict

**`docs/downloads/`** — every GeoTIFF there has a row in [`docs/index.html`](docs/index.html) that
says, in one line, whether it is **OK TO DOWNLOAD AND SUBMIT** or **DO NOT SUBMIT**, plus the rule
that decided it. The site is generated from `evidence/*.json` by `scripts/build_site.py` and never
hand-edited.

> ### ⛔ THIS SESSION (2026-10-11): **no file is cleared for submission.**
>
> | arm | HOLDOUT-DTI (8 blocked cells) | verdict | rule that decided it |
> |---|---|---|---|
> | `sar` — the lane's hypothesis | 0.06195 | **NEGATIVE** | R3: gate not met (nnPU 0.06753, Δ -0.00558, CI95 [-0.01216, -0.00063], wins 2/8; top-propensity tercile Δ -0.01305) |
> | `nnpu` — baseline | 0.06753 | **NOT CLEARED** | R4: below the current holdout best 0.09974 (`g32-h32d-submodular-nan.tif`) |
> | `em` — baseline | 0.06555 | **NOT CLEARED** | R4: same bar |
>
> All six written files are **format-valid and unique**: the 14-point validator passes on every one,
> max rank-correlation against the 15-raster registry corpus is 0.0187 and max 3-px dot overlap
> 0.3642 — both far inside the 0.90 / 0.70 lane-drift thresholds — and all three arms place
> **zero mass on masked catalogue pixels**. They are published as evidence artifacts.
> **Do not spend a weekly slot on any of them.**
>
> The negative result is the deliverable, and it is a *clean* one: the leakage canary found no
> suspect feature (max single-feature AUC 0.5738 over 28 features), and the verdict does not
> change anywhere in the propensity-anchor sweep ā ∈ {0.15, 0.25, 0.32, 0.50}.
>
> **And the gate instrument itself is suspect** — see §3.1. Spearman(blocked-holdout DTI,
> owner-reported live score) = **-0.436** over 10 registry rasters, while the
> registry-anchored mirror instrument reaches **+0.804**. On the mirror our best arm scores
> 0.147, below 10/10 live-scored artifacts. Two differently-biased instruments agree: refuse.

```
open docs/index.html          # or visit the GitHub Pages URL for this repo
```

---

## 1. Standing brief (verbatim — do not paraphrase, do not drop requirements)

> THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!
>
> MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION. DO NOT COPY A PREVIOUS SUBMISSION
> UNLESS IT'S FOR LEARNING AND EDUCATION. BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION. IT MUST BE
> OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.
>
> There should be an easy to download submission tif file as described by the prompt. Read the
> entire prompt.
>
> Selection-bias-aware PU learning. Treat the catalogue as positives selected at random given
> covariates (SAR), not completely at random. Great Basin inventories show observable mapping bias.
> About 92% of step-overs lie on range-front faults, partly because steep relief makes them easy to
> see, and only about 25% of the region has detailed (≈1:24,000) mapping (Giddens & Faulds 2025,
> SGP-TR-229). Estimate the propensity e(x) = P(labeled | fault, x) with the EM method of Bekker &
> Davis (PMLR v94, 2018). Use a small covariate set: local relief, slope, a gravity-derived
> basin-fill proxy, lidar coverage and distance to range front. Anchor its scale with exhaustively
> mapped quadrangles if a public index exists. Propensity is not uniquely identifiable from PU data
> alone, so otherwise report it as a sensitivity analysis. Train with the propensity-aware empirical
> risk of Bekker, Robberechts & Davis (arXiv:1809.03207), weights clipped at 10, against an nnPU
> baseline on identical folds. Gate: higher blocked-holdout DTI overall and no loss in the
> highest-propensity tercile. Finish: normalize to [0,1]; write a float32 EPSG:32611 100 m GeoTIFF
> (NaN only outside the footprint); pass validate_submission.py; run a hash/pixel-agreement check
> against all prior rasters; offer the download only if the gate is met, else log the negative result.
>
> PARALLEL-RUN PROTOCOL — read first. This session is one of several running from this same prompt.
>
> 1. LANE. Your lane is the single method paragraph below. Stay inside it. If your raster's
>    rank-correlation with any registry raster exceeds [0.90], or more than [70%] of your dots fall
>    within 3 px of one registry raster's dots, you have drifted into another lane: log it as a
>    duplicate and stop. Check this on the surface before placement AND on the final dots.
> 2. REUSE, DON'T REBUILD. Use the template's cached feature stack, evaluate_holdout.py and
>    submission_writer.py. Holdout = hide-and-recover: withhold whole fault segments with a buffer,
>    derive every catalogue-based feature only from the visible faults, mask visible faults
>    pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared tool
>    is wrong, fix it once in the template and report it; never keep a private fork.
> 3. LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator version, number of withheld positives, 95% CI) or
>    ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never written as a
>    score.
> 4. LEAKAGE CANARY. Test each feature alone on the holdout before trusting any result. AUC above
>    [0.90] means leakage until proven otherwise.
> 5. RUN CARD. End with one JSON card: hypothesis; mechanism; the named non-fault process that could
>    mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output (no
>    NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission name + note of
>    at most 140 characters; verdict promote / negative. Negative results are deliverables.
> 6. BUDGET. Stop after [3] experiments or [2] hours. Do not pick submissions: promotion to a real
>    slot is a separate selector step, within the weekly cap shown on the submission page.

Additional standing requirements from the owner (also verbatim in intent):

* Work line by line verifying from official, verified, trusted sources; provide links for manual
  review. No manual input. Flag any irregularities for review. **No hallucinations.**
* Create a GitHub Pages site with a clean, user-friendly UI, and an **executive summary subpage that
  explains exactly how to make a submission into the contest**. The download must be obvious the
  moment the site is visited.
* The submission needs **a unique name** and **a short note (≤140 characters)** to tell submissions
  apart later.
* The portal error **"Predicted values must be in range [0, 1]"** must be engineered out permanently.
* Before implementing, generate **3–5 candidate geological hypotheses we haven't tried yet**, each
  naming the layer(s), the physical signature targeted, why it should catch a fault *missing* from
  the USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything
  already implemented. Rank by expected DTI improvement and implementation cost. Validate the top
  candidate on the spatially-blocked holdout before touching a weekly submission slot.
* Core values: **Maximize P(Win)** and **Own the Outcome**.

---

## 2. Lane and its scientific claim

| item | content |
|---|---|
| Lane | Selection-bias-aware (SAR) PU learning for the hidden-fault field |
| Hypothesis | The INGENIOUS/USGS catalogue is a *propensity-biased* sample of the region's Quaternary faults: `P(labelled \| fault, x)` rises with local relief, slope and detailed-map coverage. A detector trained under SCAR inherits that bias and ranks its best pixels in already well-mapped, steep, range-front terrain — which is exactly where the catalogue is densest and where scored pixels are masked out. Reweighting by the propensity should move expected credit into under-mapped, low-relief basin terrain where unmapped faults remain. |
| Mechanism | `e(x) = P(s=1\|y=1,x)` estimated by EM; classifier retrained by minimising the propensity-weighted risk (Definition 2) with `c = min(1/e, 10)`; belief = the EM posterior `f(1-e)/(1-fe)`. |
| Named non-fault process that could mimic it | **Alluvial-fan apex / drainage-front linearity.** In low-relief, low-propensity basin terrain the same covariate combination that makes a buried fault hard to map also produces straight geomorphic edges (fan apexes, channel banks, lithologic contacts, playa margins) that a linear-in-RFF model can read as a scarp. This is the process that would make the SAR arm's *added* mass wrong rather than merely uncertain. |
| Pre-registered gate | higher blocked-holdout pooled DTI overall **AND** no loss in the highest-propensity tercile, with no single-feature holdout AUC above 0.90 |

---

## 3. Current state (updated every session; numbers are generated, never typed)

The machine-readable state lives in `evidence/` and `registry/`; `docs/index.html` renders it.

* `evidence/covariates.json` — data hash verification, grid geometry, covariate provenance and statistics.
* `evidence/holdout_pu.json` — **HOLDOUT-DTI** for all arms, the `a_bar` sensitivity, the leakage canary, the gate verdict.
* `evidence/submission_build.json` — the written rasters, their validator output, the duplicate / lane-drift check against all 15 registry rasters, and the per-arm verdict.
* `evidence/holdout_calibration.json` — does the blocked holdout actually predict the live score?
* `evidence/live_mirror.json` — the registry-anchored relative instrument and its own quality.
* `registry/adjudication.json` — the rule-by-rule audit trail behind every verdict (R1–R5).
* `registry/irregularities.json` — 8 irregularities (IR-65-001 … IR-65-008) with evidence and disposition.
* `RUN_CARD.json` — the single JSON card required by protocol rule 5.

### 3.1 The most important measured fact in this repo

**The blocked-holdout gate cannot see this lane's mechanism, and it is measurably anti-correlated
with the live metric.** Known USGS/INGENIOUS fault pixels are *masked out* of live scoring (DrivenData
staff, forum thread 11516), while this holdout's "truth" *is* catalogue pixels. Measured on the
registry corpus (`evidence/holdout_calibration.json`):

| registry artifact | dots | HOLDOUT-DTI | OWNER-REPORT live |
|---|---|---|---|
| `g32-h33-2-b2` (best live) | 37,654 | 0.00452 | 0.2778 |
| `g36-anderson-pinn` | 38,854 | 0.00458 | 0.2750 |
| `g49-gate-ortho-w025` (worst live) | 40,000 | 0.00000 | 0.2376 |
| `g32-dotted-h19-5-d2-8` | 44,090 | 0.09674 | 0.2600 |
| `g32-h32d-submodular` | 46,090 | **0.09974** ← current holdout best | *no receipt* |

Spearman(holdout, live) = **−0.436** (n = 10); Spearman(dot count, live) = **−0.791**. The artifacts
that score best live score *worst* on this holdout, because they avoid the catalogue — which is
exactly what this lane does too. So the gate result is a negative result **about the proxy**
(`IR-65-006`), and rule R4 refuses the baseline arms on the honest reading of "has not beaten the
current holdout best".

The second instrument, `scripts/04_live_mirror.py`, takes the best-scoring registry artifact as
pseudo-truth and reaches Spearman **+0.804** (leave-one-out, n = 10) against live scores. It is the
better proxy and it is biased in the *opposite* direction (it rewards resemblance to a known-good
submission), and it also refuses: our best arm scores MIRROR-DTI 0.147, below every live-scored
artifact. **Never write either number as a score**; both are instruments.

---

## 4. Rules that keep the numbers honest

1. **Evidence classes.** Every number carries one of:
   `[OFFICIAL]` (read from a DrivenData / USGS / DOE / peer-reviewed page, link given),
   `[MEASURED]` (computed in this checkout from hash-pinned bytes, command given),
   `[OWNER-REPORT]` (a sibling repository's own claim; no organizer receipt),
   `[MODEL]` (an estimate conditioned on an unverified anchor — never a result).
   **No ORGANIZER-CONFIRMED number exists in this repository**: `drivendata.org` is outside this
   sandbox's network allowlist, so no submission receipt could be read. Every live score quoted here
   is `[OWNER-REPORT]` and is labelled as such.
2. **Hash-pinned inputs.** Nothing is trained on data whose sha256 has not been checked
   (`scripts/01_prepare_data.py` aborts on mismatch; see `registry/data_manifest.json`).
3. **No hand-copied numbers on the site.** `scripts/build_site.py` reads `evidence/*.json`.
4. **A projection is never written as a score.**
5. **Negative results are deliverables** and are shipped with the same rigour as positive ones.

---

## 5. Reproducing everything

```bash
# 0. restore the hash-pinned competition data from the owner mirror (no DrivenData login needed)
python scripts/00_restore_data.py

# 1. verify hashes, build covariates + the 5,167,373 x 23 feature matrix   (~2 min)
python scripts/01_prepare_data.py

# 2. fetch the 15 prior submission rasters used for the duplicate check    (~20 s)
python scripts/00_fetch_registry.py

# 3. the gate: propensity-aware ERM vs nnPU on 8 blocked hide-and-recover cells  (~8 min)
python scripts/02_run_holdout.py --cells 8 --unlabeled 80000 --em-iters 6 --dots 40000

# 4. build + validate + duplicate-check the rasters for all three arms     (~3.5 min)
python scripts/03_build_submission.py --dots 38000 --a-bar 0.25 --min-dist 2.8

# 5. calibrate the instrument against nine owner-reported live scores      (~3 min)
python scripts/05_holdout_calibration.py

# 6. the registry-anchored relative instrument                             (~4 min)
python scripts/04_live_mirror.py docs/downloads/<candidate>-nan.tif

# 6b. re-take every verdict with all the evidence present (no retraining)
python scripts/07_adjudicate.py
python scripts/04_live_mirror.py docs/downloads/<candidate>-nan.tif

# 7. validate any file independently, then rebuild the site
python scripts/validate_submission.py --all
python scripts/build_site.py

# tests (metric vs brute force, Definition-2 unbiasedness, EM recovery, validator, dupcheck)
python tests/test_all.py
```

Environment: Python 3.11, `numpy scipy scikit-learn pandas rasterio` (see `requirements.txt`),
2 CPU / 3 GB RAM is sufficient — the whole pipeline above runs in under 25 minutes on that.

---

## 6. Verified sources (all read 2026-10-11; links for manual review)

| # | Source | What it establishes | Link |
|---|---|---|---|
| 1 | Competition problem description, "Performance metric" + "Submission format" | DTI (α=0.2, β=0.8, R=300 m), float32 EPSG:32611 100 m, values in [0,1], null/nan outside bounds | <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/> |
| 2 | DrivenData staff (`chrisk-dd`), forum thread 11516, 16 Sep 2026 | known USGS/INGENIOUS fault pixels are **masked/excluded** from evaluation, in round 1 and in the re-evaluation | <https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516> |
| 3 | Official reference solution (J. Lipor, PSU) | U-Net + MC-CV + Tversky loss baseline; band metadata access pattern | <https://github.com/drivendataorg/gems-prize-reference-solution> |
| 4 | Bekker & Davis 2018, PMLR 94:8–22 | the SAR assumption and the EM method for propensity estimation | <https://proceedings.mlr.press/v94/bekker18a.html> |
| 5 | Bekker, Robberechts & Davis, arXiv:1809.03207 (ECML-PKDD 2019) | Definition 1 (`e(x)=Pr(s=1\|y=1,x)`), Definition 2 (propensity-weighted risk, proved unbiased), Prop. 3–5, EM in §5.2 | <https://arxiv.org/abs/1809.03207> · PDF: <https://jessa.github.io/assets/pdf/bekker2019ecml.pdf> |
| 6 | Kiryo et al. 2017, arXiv:1603.07419 | the nnPU baseline (non-negative PU risk) | <https://arxiv.org/abs/1603.07419> |
| 7 | Giddens & Faulds 2025, SGP-TR-229, 50th Stanford Workshop | **91.9%** of step-overs on range-front faults; bias acknowledged ("more easily identified due to steep topographic gradients"); **~25%** of the study area mapped at 1:24,000 | <https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Giddens.pdf> |
| 8 | Faulds et al. 2026, 51st Stanford Workshop | "Publicly available high-resolution Lidar now covers much of the GBR, but detailed geological maps include **less than 25%** of the region" — confirms lidar coverage is *not* a proxy for detailed-map coverage | <https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2026/Faulds.pdf> |
| 9 | USGS GeoDAWN data release, DOI 10.5066/P93LGLVQ | the airborne magnetic/radiometric survey the feature bands derive from | <https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and> |
| 10 | INGENIOUS / GDR (labels' origin, DOI 10.15121/1881483) | the Great Basin Regional Dataset Compilation the catalogue comes from | <https://gbcge.org/current-projects/ingenious/> · <https://gdr.openei.org/submissions/1391> |
| 11 | EPSG:32611 | WGS 84 / UTM zone 11N | <https://epsg.io/32611> |
| 12 | Tversky index | the metric family DTI generalises | <https://en.wikipedia.org/wiki/Tversky_index> |
| 13 | USGS 3DEP 1 m DEM tile index used for the lidar-coverage covariate | 716 tiles, `prd-tnm` S3 URLs, mirrored at `external/dem_links.json` | <https://www.usgs.gov/3d-elevation-program> |

---

## 7. Limitations (see `LIMITATIONS.md` for the full list)

* **No DrivenData access.** `drivendata.org` is outside this sandbox's allowlist, so no submission can
  be uploaded, no receipt can be read, and no live score in this repo is organizer-confirmed.
* **The holdout's truth is the catalogue.** A proxy whose truth *is* the given catalogue cannot
  reward a genuinely new fault by construction, and §3 of `evidence/holdout_calibration.json`
  measures how weakly it tracks the live board.
* **Propensity is not identified** from PU data alone; the scale is a pre-registered sensitivity
  (`a_bar`), not a measurement. No public index of exhaustively mapped 1:24,000 quadrangles was
  reachable from this sandbox to anchor it.
* **Compute.** 2 CPU / 3 GB RAM: the classifier is a logistic model on 48 random-Fourier features,
  not a U-Net. Ranking quality is therefore below what a GPU-trained convolutional detector reaches.
