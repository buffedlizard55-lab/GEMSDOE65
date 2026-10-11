# Repository and scientific review — 2026-10-11

## Intake and previous-session next steps

GEMSDOE65 at `90ca1cea667dc1427de27ef997634f3305a7c164` contained only `README.md` with its project title. There was no local cached stack, evaluator, writer, test suite, website, or previous-session log. Consequently the prompt's assertion that data placement was the *single* remaining blocker was not true for this checkout. This session restored owner-mirrored inputs, verified their hashes, and reused an immutable shared-template snapshot. CPU execution was sufficient; no GPU or DrivenData credential was needed for this constrained experiment.

`evidence/repository_inventory.json` inventories the pinned public Git trees of all 62 named repositories. `evidence/site_review.json` records inspection of their index-page source, not successful visits to their live GitHub Pages sites. Neither source inspection nor an owner-supplied score list constitutes an organizer submission receipt. The working registry has 751 distinct prediction-like Git blobs; its broad path filter can include non-submission rasters, and it excludes release-only, historical, unlinked, and private files. It is an inventory for review, not a completeness certificate.

## Why did the cited GEMSDOE32 artifact do well?

### What the bytes and code establish

We downloaded the cited H33-2-B2 and its H27-4 base **only for forensic learning**, never as a feature or candidate initialization. Full-file SHA256 and pixel reads establish:

- Base: 40,199 positive pixels.
- H33-2-B2: 37,654 positive pixels, a strict subset of that base.
- Exactly 2,545 dots removed; their distances to the mapped catalogue span sqrt(2) to 2 pixels.
- Minimum retained distance is sqrt(5) pixels.
- The source generator calls `compute_h33_2_flank_sweep(..., buffers=(2,3))` and describes B2 as deleting dots at catalogue distance <=2 pixels.

These are **RASTER-FORENSICS measurements, not DTI scores**. Receipts and byte pins are in `evidence/h33_forensics.json`.

Code: https://github.com/buffedlizard55-lab/GEMSDOE32/blob/b39e16ee85f83e3291951f56b615d657a071bb2b/scripts/run_h33_validation.py

Artifact manifest: https://github.com/buffedlizard55-lab/GEMSDOE32/blob/b39e16ee85f83e3291951f56b615d657a071bb2b/evidence/h33_submission_bundles.json

### A defensible mechanism, not a causal attribution

In the protocol's DTI, weighted true-positive credit saturates per truth pixel. Dense/redundant emissions can accumulate false-positive mass without providing additional truth coverage. Removing a redundant dot that contributes false-positive mass can therefore improve the ratio. A catalogue-flank exclusion can suppress mapped-fault continuations that receive no new-fault credit. That is a plausible reason the pruning helped; we cannot identify which removed dots were genuine organizer false positives without hidden truth or a receipt-backed controlled ablation.

For binary dots, let T be total truth coverage, M total dot self-credit, n the dot count, and K the truth count. With alpha+beta=1, D = alpha(T+n-M)+beta K. Removing a dot loses truth credit deltaT and removes false-positive mass f.

**Exact removal derivation:** before removal, D=T+alpha*FP+beta*(K-T). After removal, T'=T-deltaT and FP'=FP-f, so `D'=D-(1-beta)*deltaT-alpha*f`. Provided the denominators are positive, the ratio improves exactly when

`alpha*f*DTI > deltaT * (1-(1-beta)*DTI)`.

This keeps loss of coverage separate from removal of FP mass. Keeping a redundant dot with deltaT=0 and f>0 lowers the score whenever T>0; removing it improves the ratio. The expression does not assume T=M or convert a claimed leaderboard number into a prediction.

### What cannot be concluded

The prompt's cited leaderboard result is **user-reported and unverified**, not ORGANIZER-CONFIRMED. The sibling page/manifest also contains older UNSCORED/projection language. The three different current-leaderboard targets in the prompt conflict. None is used as a measured baseline, a claim about the live leaderboard, or a target the new method is said to have beaten.

There is no defensible basis to promise a result above the cited artifact or the current leader. The SAR-PU experiment here failed its local comparison. A weak finite-iteration model is not evidence that selection correction can never help, but it is evidence against spending a slot on *this* implementation.

## Selection bias: the crucial scientific distinction

With PU observations, `P(S=1|x) = e(x) * P(Y=1|x)`. Many pairs `(e,f)` can produce the same observed product. A small propensity feature set is a structural modeling restriction, not an empirical identification certificate. The PMLR paper additionally discusses local certainty; it is not established in these geophysical rasters. We therefore fixed the selection-model intercept at three preregistered reference values and made no claim that they estimate regional mapping coverage.

The user's quoted Great Basin range-front/mapping percentages were not independently recovered from the primary Stanford paper. They motivate a question, not a fitted numerical anchor. A public map index describes map products; it does not automatically certify that all faults in a quadrangle were found. No verified exhaustive-quadrangle anchor exists in this run.

The paper's exact E-step was implemented. Fractional-label outcome and posterior-weighted selection M-steps were used with an explicitly fixed reference propensity. A clipped inverse-propensity risk and genuine nnPU comparator used the same sampling weights, covariates, spatial folds, regularization, and corrected positive mass. Bounded logistic coefficients prevent unbounded signed-risk optimization. Clipping intentionally trades bias for stability. Tests verify analytic gradients, risk identities, nonnegative-risk clamping, and posterior probabilities.

All twelve fold/scenario EM fits reached the fixed iteration cap. Inner optimizers converged, but the EM stopping criterion did not. Results are explicitly **finite-iteration negative results**, not converged propensity estimates. No extra model experiment or tuning was performed after the three-scenario budget. The executed numeric settings and the preregistration-detail gap are recorded in `research/implementation_details.md`.

## Validation discipline and its limits

- Four shared label-blind spatial quadrants; full 8-connected components touching the test quadrant are excluded from training, including their tails.
- An 8 km spatial training buffer; visible catalogue is masked pixel-exactly by the shared evaluator.
- No catalogue-derived predictors. Imputation/scaling fit only on training samples; stratified positive/unlabeled samples carry population-correcting weights.
- All twelve physical features individually tested in each fold before fitting; the canary did not trigger. Pass 2 also checked every standardized/quadratic basis (144 checks) on the same samples without refitting; this was an after-fit diagnostic on an already-negative result. Passing the canary is not proof that all leakage is impossible.
- Pooled distance-weighted terms, not a mean of fold ratios. Paired 20 km spatial-cluster bootstrap and conditional confidence intervals.
- Highest-propensity tercile defined by each training population, never by holdout label optimization. Restricting the spatial evaluation domain to this tercile can truncate a 300 m neighborhood; both arms use the same restriction, and it is a diagnostic rather than a globally additive decomposition.
- The observed catalogue is itself selection biased. Hide-and-recover validates recovery of mapped faults, not transport to the organizer's unmapped-fault population. Withheld catalogue zeros are unlabeled, not verified negatives.
- No portable comparable-incumbent holdout receipt was established. Historical shifted-truth/live-mirror projections cannot stand in for this evidence.

## Uniqueness and range-error findings

The new OOF research surface was serialized with the unmodified shared `submission_writer.py` and re-read by `scripts/validate_submission.py`. It is a float32, single-band, EPSG:32611, 100 m GeoTIFF matching the template's shape/transform. It has no NaN inside the footprint, NaN outside, no infinity, no nodata sentinel in the scored area, and all finite values in [0,1]. This is local format validation, not organizer acceptance.

A common cause of the user's earlier range error is writing a finite negative nodata sentinel, a raw logit/feature value, or an unbounded rescaling into the scored area. We did not receive the exact rejected file, so we **cannot diagnose its specific cause**. The writer rejects bad input; it does not silently clip/fill it. A finite sentinel is never interpreted as a valid prediction.

Pre-placement comparison checked the two requested historical rasters and a dense registry witness. The candidate's bytes and decoded pixels differ from all three. However the 17GEMSDOE continuous witness is positive at every footprint pixel. Its forward three-pixel coverage is complete. Under the inherited literal `finite > 0` support definition, every nonempty candidate is therefore blocked. This is a degenerate rule for mixed dense/point registries, not scientific proof that the new model copied a lane. We did not redefine dots or grant a density exemption.

The duplicate stop is honored: final dot placement and final-dot comparison were **not run**. The remaining registry entries were not cleared. The TIFF stays quarantined outside the public site; no download link, slot selection, or upload is offered.

## Three review passes

1. **Implementation:** data restoration, primary-literature/code inspection, preregistration, three matched sensitivity experiments, quarantine writing, local validation, and pre-placement duplicate stop.
2. **Bug/edge-case review:** added gradient and posterior checks, population-weighted preprocessing checks, whole-component/buffer tests, pooled-bootstrap truth-count tests, NaN/range/grid failure tests, missing-evidence gate tests, and publication checks. Replaced an unsafe default-based validator summary with explicit named checks. No model/parameter selection was performed during code review.
3. **Request reconciliation:** verify report values against JSON evidence, distinguish finite-iteration results and owner mirrors from official confirmation, preserve original request in README, prevent negative TIFF exposure, build site/instructions/source ledger, run full tests and CI, open and merge the requested PR without switching branches.

## Prioritized next session (not executed experiments)

1. Resolve support semantics through the separate selector/owner protocol, preserving the current literal failure until explicitly changed. It is mathematically impossible to pass the current rule against the confirmed dense witness.
2. Obtain independently verifiable submission receipts and a same-evaluator incumbent holdout. Check the weekly cap on the actual submission page; do not infer it.
3. Preregister a larger EM iteration budget and convergence analysis on a fresh locked holdout before any new sensitivity fits. Do not continue optimizing the already-consumed holdout as if it were new evidence.
4. Verify original data provenance and external-data licensing against official downloads. Acquire mapping-completeness evidence, not just publication polygons. The blocked source ledger identifies official starting points.
5. Only after those steps consider DTI-aware emission validated on the same folds. Do not extrapolate the continuous negative result to a dot field without evaluating the actual placement procedure.
6. Treat geothermal relevance separately: fault geometry alone establishes neither heat, fluid supply, permeability at depth, nor a commercially viable resource. Independent field/thermal/hydrochemical evidence would be needed and must not be used to smuggle labels into this lane.
