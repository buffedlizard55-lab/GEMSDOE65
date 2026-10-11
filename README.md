# GEMSDOE65 — selection-bias-aware PU learning (SAR propensity lane)

> **Read this file before every session.** It is the standing brief: the goal, the lane, the
> gates, what is verified, what is assumed, and exactly what must happen next. Then read
> [`registry/run-card.json`](registry/run-card.json) (the canonical machine-readable card) and the
> project site in [`docs/`](docs/index.html).
>
> **Submission decision in one line:** a unique, fully validated candidate GeoTIFF
> **`gems65-sarprop-em-v2-20261011-9b1c65d-zeros.tif`** is downloadable at
> [`docs/downloads/`](docs/downloads/) — and it is **NOT cleared for a weekly slot**. The
> pre-registered promotion gate returned a statistical tie on both instruments, so the honest state
> is *research artifact, do not submit*. See [why](#why-the-gate-says-no) below.

## 1. The goal

Place at the top of the [DOE GEMS Prize Challenge](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)
(DrivenData competition 306) by producing a scientifically defensible prediction raster of
**geological faults that may indicate geothermal resources** across the Great Basin study area —
including faults that the published USGS/INGENIOUS compilations missed — and by only ever
uploading a raster whose evidence gates have passed.

The public leaderboard is participant-level and does not name files; the project therefore never
presents a leaderboard number as if it were a receipt for one of our rasters, and it never
scrapes or mirrors the board ([Terms of Use](https://www.drivendata.org/termsofuse/) prohibit
automated monitoring/copying and manual monitoring/copying without prior written consent).

## 2. This lane (do not drift)

Model catalogue inclusion as **Selected At Random given covariates** (SAR), not completely at
random. Estimate the propensity `e(x) = P(labelled | fault, x)` with the EM method of
Bekker & Davis ([PMLR v94, 2018](https://proceedings.mlr.press/v94/bekker18a.html)) on a small
covariate set — local relief, slope, a gravity-derived basin-fill proxy, survey coverage, and
distance to a range front — and train with the propensity-aware empirical risk of Bekker,
Robberechts & Davis ([arXiv:1809.03207](https://arxiv.org/abs/1809.03207)) with inverse weights
**clipped at 10**, against an nnPU baseline on identical folds. Because PU data alone do not
identify the scale of `e(x)`, the prior is an explicit sensitivity parameter and the propensity is
reported as a sensitivity analysis, never as a calibrated probability.

Everything else in the pipeline is **reused, not rebuilt**: the feature stack cache, the
hide-and-recover evaluator (`vendor/gems57/holdout.py`, `evaluate_holdout.py`), the metric
(`metric.py`), the writer (`submission_writer.py`) and the validators are vendored byte-for-byte
from the family template repo `buffedlizard55-lab/60GEMSDOE` at commit
`6444fa6552335190f0bc89661acf725ed73e7fcb`; the sha256 of every vendored file is checked in
[`registry/template_provenance.json`](registry/template_provenance.json).

## 3. Gates (all must pass before a raster is called submittable)

1. **Promotion gate.** Pooled blocked-holdout DTI (α = 0.2, β = 0.8, 300 m triangular kernel)
   higher than the matched nnPU baseline *and* no loss in the highest-propensity tercile.
2. **Leakage canary.** Any single feature with holdout AUC above 0.90 is leakage until explained.
3. **Uniqueness.** Rank correlation ≤ 0.90 and ≤ 70 % of dots within 3 px of any one prior
   raster — evaluated with a **saturation column**, because a witness whose own dots cover the
   whole footprint within 3 px trips the rule for *any* candidate (measured: 61/61 priors).
4. **Format.** Single-band float32 GeoTIFF, EPSG:32611, 100 m, 3730 × 3292, transform
   `(100, 0, 243350, 0, -100, 4508550)`, all-finite with values in [0, 1], zeros outside the
   footprint, no NaN inside, no positive mass on the mapped catalogue.
5. **Budget.** Three experiments or two hours per session; negative results are deliverables.

## 4. What happened in the current session (2026-10-11 UTC)

* Recovered the **official competition data** through the family's public data bridge and verified
  every sha256 against the bridge manifest: `labels.tif`/`existing_faults.tif`
  (`7ba308cc…`), `sample_submission.tif` (`2176d08e…`), and the 19-band feature stack
  reassembled from five parts (`4371c82e…`, 418 912 844 bytes). Nothing was invented and no
  access control was bypassed — the bridge exists because the data tab requires a login.
* Vendored and hash-verified the shared template (23 files) and the official reference-solution
  commit provenance from the family's audit receipts.
* Built a cached 22-channel feature stack (`data/derived/feature_stack.npy`) from the official
  bands plus three derived covariates, with **no catalogue-derived channel at all**.
* Ran **E1** on the registered shared instrument and **E2** on a pre-registered bias-matched
  instrument, and emitted the candidate raster through the shared writer/validators.
* Ran four matched arms on identical folds (both arms share features, sampler, optimiser, prior
  and emission; they differ only in the weights):
  | arm | instrument | propensity | Δ (paired 95 % CI) | reading |
  |---|---|---|---|---|
  | E1 (16 cells) | registered (uniform withholding) | quantile grid | −4.32e−05 [−3.87e−04, +3.17e−04] | tie |
  | E2 (8 cells) | bias-matched, P(select) ∝ (1−ē)² | quantile grid | +1.70e−04 [−9.29e−05, +4.12e−04] | +0.8 %, n.s. |
  | E3 (8 cells) | registered (same folds as E1) | continuous RBF | −1.05e−05 [−5.38e−04, +5.99e−04] | tie |
  | E3b (8 cells) | bias-matched, same design as E2 | continuous RBF | +3.45e−05 [−3.12e−04, +3.86e−04] | +0.14 %, n.s. |
* **Found and fixed a real unit bug** in the EM (the reason E1/E2 were inert): the labelled set is
  the *complete* catalogue while the unlabeled set is a 1/127.7 subsample of the pool, and the
  recursion compared them without a sampling-fraction weight, so the implied hidden-positive mass
  was 127.7× too small and the EM fixed point was pinned near e(x) ≈ 1 whatever the covariates
  said. With the pixel-population correction the propensity is genuinely non-degenerate
  (e_pos ∈ [0.44, 0.71], sd 0.05, inverse weights 1.00–2.28, clip fraction 0). E3/E3b are that
  corrected lane.
* Verdict: **negative**. With an active correction on the only instrument that contains bias, the
  gain is +0.14 % of the DTI with a CI straddling zero (four cells win, four lose). The lane does
  not clear the gate, so no weekly slot is spent.

## 5. Why the gate says no

* The registered instrument withholds segments **uniformly at random**. That is SCAR by
  construction, so it contains no covariate-dependent bias for the SAR arm to remove; the E1 and E3
  ties are a property of the instrument, not evidence about the real task.
* On the bias-matched instrument, where the mechanism should show up, the corrected lane moves in
  the predicted direction but by +0.14 % with a CI straddling zero — indistinguishable from noise
  at this sample size. The mechanism is not demonstrated.
* A **second, independent** reason the absolute numbers are low (and the highest-value next step):
  the emitted dot field sits a median of **12.5 px (1.25 km)** from the published catalogue, and
  22.5 % of dots are beyond 30 px. Under the organizer's 300 m kernel that placement earns little
  credit from catalogue faults, and the 28 047 emitted dots exceed the family's owner-reported
  estimate of the hidden truth mass (K̂ ≈ 12 226 px). Sparse, catalogue-anchored fields in the
  family score 0.26–0.2778 live; this lane's geometry is different by design (it is looking where
  the catalogue is thin) and is penalised by a holdout whose truth *is* the catalogue.
* The uniqueness rule is tripped only by two saturated lattice witnesses (99.9 % self-saturation)
  that also trip for a random 28 218-dot control; the surface correlation (max |ρ| = 0.0366), the
  reverse overlap (≤ 0.0193) and the dot-set Jaccard (≤ 0.019) say the candidate is **not** a copy
  of any prior. See IR-65-107.

## 6. Next steps (in priority order)

1. **Fix the emission geometry before anything else — highest expected value.** The allocator
   currently spends a fixed budget of `π·n_active` dots over the whole domain, which produces
   ~28 000 dots with a median distance of 12.5 px from the catalogue. The family's live anchors say
   a sparse field (≈ 44 000 px) hugging the catalogue scores 0.26, while the metric's own algebra
   (`accept a dot ⇔ k > α·DTI`) says a dot only pays for itself inside ≈ 283 m of a true fault at
   DTI ≈ 0.28. Concrete recipe: restrict `allowed` to a dilation of the visible catalogue
   (10–40 px), lower the assumed truth mass `k_truth` to the owner-reported K̂ ≈ 12 226 px, and
   accept only dots whose kernel credit exceeds the plug-in bar. Test it on the registered folds
   *before* touching the live slot.
2. **Re-register the gate instrument before the next run.** The bias-matched instrument is the only
   one that contains the mechanism; make it the *primary* gate for the next session (it was
   pre-registered as a diagnostic this session) and re-run both arms.
3. **Replace the linear head with a non-linear head under the same IPW weights** (a gradient-boosted
   or small MLP head with `clip(1/e,1,10)` sample weights). The matched pair is what the gate
   measures, so the head swap must be applied to *both* arms.
4. **Anchor or bound the propensity scale.** PU data alone cannot identify the absolute scale of
   `e(x)`. Either find an official source that can be proven exhaustive over part of the footprint,
   or report `e(x)` only as a prior-conditional sensitivity band (π × {0.5, 1, 2, 4}).
5. **Extend the uniqueness check to every fetchable prior raster**, always recording the
   saturation column so the rule is never misread (IR-65-107).
6. Only then: a weekly slot. Until then, the download page stays labelled **do not submit**.

## 7. Repository layout

```
data/raw/            official feature stack + labels (git-ignored, hashes in registry/inputs.json)
data/bridge/         pinned label/sample rasters used by the shared template
data/derived/        cached 22-channel feature stack (git-ignored, reproducible)
vendor/gems57/       byte-identical shared template (metric, holdout, writer, gates, validate…)
scripts/             build_features, fetch_data, sar_pu, holdout_biased, run_lane,
                     emit_submission, check_registry, make_run_card, build_site,
                     audit_lane_readiness
registry/            run cards, holdout arm results, registry check, template provenance
docs/                the public site + downloadable artifacts (+ docs/data/*.json)
tests/               unit + site + run-card consistency tests
```

## 8. Running it

```bash
pip install --break-system-packages numpy scipy rasterio scikit-learn   # or a venv
bash scripts/fetch_data.sh          # documents/verifies where the inputs come from
python3 scripts/build_features.py   # ~55 s, writes data/derived/feature_stack.npy
python3 scripts/run_lane.py --seeds 20,21 --modes all,detached          # E1 (~13 min here)
python3 scripts/run_lane.py --instrument biased --seeds 20,21 --modes all \
        --out registry/holdout_arms_biased.json --cache registry/holdout_terms_biased.npz  # E2
python3 scripts/run_lane.py --propensity rbf --seeds 20,21 --modes all \
        --out registry/holdout_arms_e3.json --cache registry/holdout_terms_e3.npz           # E3
python3 scripts/run_lane.py --propensity rbf --instrument biased --seeds 20,21 --modes all \
        --out registry/holdout_arms_biased_e3.json                                          # E3b
python3 scripts/make_run_card.py    # regenerate the canonical card from the artifacts
python3 scripts/emit_submission.py --name <unique-name> --note "<≤140 chars>"
python3 scripts/check_registry.py --candidate docs/downloads/<file> --priors <prior tifs>
python3 scripts/build_site.py && python3 -m unittest discover -s tests
```

## 9. Working values

**Maximize P(Win).** Weigh trade-offs, assess risk, and choose the path that most raises the
probability of winning — including refusing to spend a weekly slot on an unvalidated idea.

**Own the Outcome.** Own the result end to end: publish the negative result with its numbers,
flag what is unverified, and fix the pipeline rather than papering over a failed gate.
