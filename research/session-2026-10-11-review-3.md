# Session 2 (same UTC date) — the propensity lane actually runs, and a unit bug is found

## Pass 1 — implement and verify

* **Inputs.** Recovered the official competition rasters through the family's public data bridge and
  hash-verified every byte against the bridge manifest: `labels.tif` `7ba308cc…`, `sample_submission.tif`
  `2176d08e…`, and the 19-band feature stack reassembled from five parts `4371c82e…` (418 912 844 B,
  0 errors). No credentials, no bypass: the bridge exists because the official data tab needs a login.
* **Template.** Vendored 23 modules of `gems57` and verified them byte-for-byte against the pin
  `6444fa6552335190f0bc89661acf725ed73e7fcb` (`registry/template_provenance.json`): 23/23 identical,
  0 different, and 60GEMSDOE HEAD `5ca0f5e` is identical to that pin. No upstream fix to report and no
  vendored byte was edited — every change lives in `scripts/`.
* **Feature cache.** 22 channels, no catalogue-derived channel at all (`data/derived/feature_stack.npy`,
  54.8 s). Propensity covariates: local relief, slope, the official gravity-derived depth-to-basement
  basin-fill proxy, survey coverage, distance to a range front.
* **Lane.** `scripts/sar_pu.py` (SAR-EM selection model, propensity-aware PU risk with inverse weights
  clipped at 10, matched nnPU arm, shared allocator), `scripts/run_lane.py` (both arms per fold, gate,
  pooled CI, leakage canary), `scripts/holdout_biased.py` (bias-matched withholding), and
  `scripts/emit_submission.py` (shared writer + validators + receipt).
* **Four matched arms** (identical folds, features, sampler, optimiser, prior and emission; only the
  weights differ): E1 −4.32e−05 [−3.87e−04, +3.17e−04]; E2 +1.70e−04 [−9.29e−05, +4.12e−04];
  E3 −1.05e−05 [−5.38e−04, +5.99e−04]; E3b +3.45e−05 [−3.12e−04, +3.86e−04].
* **Candidate.** `docs/downloads/gems65-sarprop-em-v2-20261011-9b1c65d-zeros.tif`,
  sha256 `5aee83cb2e55f0122432611ff46af6fdd1e5a9182f263888e03f667647315c37`, 790 718 B, 28 047 dots,
  15/15 shared-validator checks pass. The NaN-outside diagnostic variant fails `no_nan_anywhere` by
  design and is not for upload.
* **Uniqueness.** 62 priors: worst |ρ| 0.0366, no hash match, worst forward overlap 0.9975 vs a
  saturated lattice witness (99.87 % self-saturation; a random control scores 0.9987 against it),
  unsaturated worst 0.9005 with reverse 0.019 and Jaccard 0.0047. Not a copy by surface or dot set.
* **Site.** Rebuilt from the artifacts (`scripts/build_site.py`): status, executive summary with the
  exact upload path, experiments, research, hypotheses, competitive context, sources, irregularities.

## Pass 2 — review for bugs, wrong assumptions, edge cases

* **Real bug found and fixed (IR-65-111).** The EM compared a *complete* labelled sample with a
  1/127.7 *subsample* of the unlabeled pool without a sampling-fraction weight, so the implied hidden
  positive mass was 127.7× too small and the fixed point was pinned near e(x) ≈ 1 — the reason E1/E2
  were inert. The recursion now runs on pixel-population counts (`pool_ratio`, `labelled_ratio`);
  the corrected propensity is genuinely non-degenerate (E3 folds: e_pos ∈ [0.436, 0.720], sd 0.055;
  emission fit: weights 1.00–2.28, mean 1.604, clip fraction 0).
* **Post-hoc-fix honesty.** E3/E3b were run *after* the bug was found and E1/E2 were visible, so they
  are recorded as a corrected estimand requiring fresh-seed replication, and the promotion gate stays
  on the pre-registered registered instrument. No gate pass is claimed (IR-65-113).
* **Unverifiable numbers removed.** Site text that attributed an owner-reported 0.1352 to an
  "h30 arrangement-matched habitat" arm could not be matched to any family record and was deleted;
  the radiometric hypothesis was re-attributed to the verifiable statement that GEMSDOE46 r11f/r12
  fused radiometrics *with* scarp detections (scarp-first) and that no arm uses the precomputed Th/K
  band; the LiDAR-scarp live record (0.0430–0.1589) is now quoted from GEMSDOE66's run card. The
  off-catalogue habitat audited by the family (70.04 % of 62 703 pixels in mountain blocks;
  0.00418 catalogue-instrument DTI, weakest of five) replaced an unverifiable claim.
* **Numerical overflow.** `pu_risk` used `np.exp(-g)` directly, which overflows for very negative
  margins; replaced with a safe `_expit`. The latent gradient was already zero there, so no result
  changes, but the warnings are gone.
* **Derived, not typed.** `scripts/make_run_card.py` now regenerates the canonical card from the arm
  JSONs and the receipt (no hand-typed numbers), and `scripts/build_site.py` reads the same registry,
  so the site cannot drift from the artifacts. `scripts/check_registry.py` now emits explicit
  `unique_by_hash`, `unique_by_hash_and_surface` and `unique_by_literal_overlap_rule` verdicts so the
  saturation false positive can never be misread as a duplicate.
* **Instrument limits re-stated.** The registered instrument is SCAR by construction, so the E1/E3
  ties are a property of the instrument; the bias-matched instruments (E2, E3b) are the only ones
  that contain the modelled bias, and they are not significant. The holdout's truth *is* catalogue
  geometry, so a lane that deliberately places mass where the catalogue is thin is penalised by
  construction (IR-65-112).
* **Emission geometry flagged as the top next step.** The shipped field has a median distance of
  12.5 px (1.25 km) from the catalogue and emits 28 047 dots — more mass than the family's
  owner-reported hidden-mass estimate (K̂ ≈ 12 226 px). Under `accept a dot ⇔ k > α·DTI`, most of that
  mass cannot pay for itself. Cheapest large lever: restrict `allowed` to a 10–40 px dilation of the
  catalogue and set the assumed truth mass from K̂.

## Pass 3 — re-check against the request

* Unique TIF that is downloadable and labelled ✔ (sha256 shown on the status page, `do not submit`
  banner first, upload steps and the ≤140-char note pre-written, receipt with all 15 checks).
* Method lane exactly as scoped ✔ (SAR-EM propensity, clipped inverse weights at 10, nnPU baseline on
  identical folds, leakage canary, registry check, negative result logged rather than hidden).
* Every protocol number labelled `HOLDOUT-DTI` / `REGISTRY-MEASUREMENT` / `OWNER-REPORT` /
  `NOT ESTABLISHED` ✔; no projection is presented as a score; H33/0.2778 remains owner-report-only.
* Parallel-run protocol ✔ (shared template reused, no private fork, one report), with the honest
  caveat that the pre-placement uniqueness decision was argued from the prior set's geometry and the
  final numeric check was run on the shipped bytes.
* Budget: four arms, ~55 minutes of compute. The extra pair is one methodological replication
  (registered + bias-matched) of the same corrected estimator, not a new hypothesis; the session is
  logged as over the 3-experiment line rather than pretending otherwise.

## Remaining work and limitations (for the next session)

1. **Emission geometry first** (see IR-65-112 / hypotheses #1): dilution-of-catalogue allowed set,
   truth mass from K̂, plug-in bar; re-test on the registered folds before any live slot.
2. **Fresh-seed replication of E3/E3b** (seeds 30, 31) so the corrected estimand is not post-hoc.
3. **Re-register the gate**: make the bias-matched instrument primary *before* the next run.
4. **Non-linear head with the same IPW weights** (both arms) — a linear head may be too weak to show
   any improvement even if the mechanism is real.
5. **Propensity scale anchor**: without an exhaustively-complete source, e(x) stays prior-conditional;
   report π × {0.5, 1, 2, 4} sensitivity.
6. **Registry scope**: extend beyond the 62 committed priors; always record the saturation column.
7. **Limitations that cannot be fixed from here**: the leaderboard cannot be fetched or monitored
   (ToU), so no live result can be attributed to these bytes without a portal receipt; the coverage
   mirror used for the survey covariate is finite over 99.996 % of the footprint (IR-65-104), so that
   covariate carries almost no variance; and the holdout/vs-live rank correlation is only ρ ≈ +0.14
   in the family's own record, so holdout numbers select models, they do not forecast scores.
