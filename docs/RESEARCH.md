# Scientific assessment and score-provenance audit

## What this competition measures

The competition asks for predictions of **geological faults that are indicative of geothermal resources**, not a direct map of geothermal vents. The official metric is a distance-weighted Tversky index. Because the weight on false negatives exceeds that on false positives and nearby pixels receive triangular distance credit within the official support, a spatially extended prediction can trade precision for recall. That metric property is a reason to test appropriate calibration and support; it is not proof that any specific dense or sparse raster is geological or will score well.

## Why selection bias is a defensible research question

Giddens and Faulds (2025, SGP-TR-229) report that approximately 91.9% of their identified Great Basin step-overs are associated with range-front faults and explicitly note that steep gradients can make range-front step-overs easier to identify. This supports a **detection-bias hypothesis in that step-over inventory**, not a universal estimate for every fault type or map product. The user's “about 25% at 1:24,000” statement is not verified in the official materials checked here; it cannot serve as a numerical propensity anchor.

Under SAR PU learning, let `Y=1` denote a true fault and `S=1` a catalogue label. The observation model is `e(x)=P(S=1 | Y=1, x)`; negatives cannot be labelled positives. The observed label rate obeys `P(S=1 | X=x) = P(Y=1 | X=x) × e(x)`. Without additional restrictions, the two unknown factors are confounded: a low observed-label rate can be explained by few faults, low label propensity, or both. Bekker and Davis formulate learning when the chance of a positive receiving a label depends on a subset of attributes and propose SAR-EM. Bekker, Robberechts and Davis develop empirical risk correction for selection bias. This does **not** make the absolute propensity identifiable from arbitrary PU observations: the propensity-feature subset, any scale anchor, and sensitivity assumptions must be declared. If no independently defensible mapped-quadrangle anchor is available, report scale sensitivity instead of pretending it was identified. Clipping inverse weights at 10, as required for this lane, controls variance at the cost of some residual bias; that trade-off must be reported, not hidden.

The target experiment is therefore a comparison, not an assumed win: same spatially blocked segment folds, same training budget, same base feature stack, SAR-EM propensity-aware risk with weights capped at 10 versus nnPU. Keep the catalogue-derived features visible-only within every fold. Mask the visible catalogue faults pixel-exactly. Evaluate the pooled official-style DTI, its paired block-bootstrap confidence interval, and the highest-propensity tercile separately. Test each feature alone first as the required leakage canary.

## H33-2-B2: what can and cannot be said

The user associates a GEMSDOE32 file named `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` with public value `0.2778`. This association is **not supported as an organizer-confirmed result by the inspected records**:

- The public DrivenData leaderboard snapshot accessed on 2026-10-11 shows the `0.2778` public-board row under `extradr19`. The leaderboard does not link that row to the named TIFF.
- GEMSDOE32's own public `submissions_manifest.json` lists the named file with `receipt: null`; the manifest note describes a projected value and says `UNSCORED`.
- GEMSDOE32 PR #9 describes H33-2-B2 as a pruning/removal arm, with its value a projection rather than a confirmed score. This is useful owner-reported development history; it is not independent evidence that the raster earned a portal score.

Therefore, the reliable answer to “why did it get that score?” is **unknown; the premise is not confirmed**. The evidence supports a likely attribution/provenance mismatch, not a causal geological explanation. The removal experiment may be a useful learning record, but it is outside this repo's SAR propensity lane and must not be copied as a submission. The live leaderboard also now places other entries above the user-reported 0.3195 value; scores move over time. A live board position is neither local holdout evidence nor a submission-page receipt.

## Can this project beat the user-reported anchor?

In principle, yes: the official public leaderboard snapshot retrieved on 2026-10-11 displays `xiaofanhu` at 0.4133 above `DARD` at 0.3195 (**PUBLIC LEADERBOARD DISPLAY — not HOLDOUT-DTI and not a submission-page receipt**). That does **not** show that this method will beat them, and public-board optimization does not establish private test or expert-review success. For this checkout, no honest estimate can be made: there is no local data, incumbent holdout score, evaluator, registry, trained model, or TIFF. The only valid decision today is **do not submit**. A candidate can be promoted only if the preregistered blocked-holdout gate is actually met, then the exact output passes validation and uniqueness checks.

## Confounders to keep explicit

- Lithology and density contrasts can produce gravity edges without faults.
- Basin geometry and unconsolidated fill can hide surface expression, but are not uniquely fault evidence.
- Erosional scarps, drainage channels, roads, and cultural lineaments can mimic fault-like terrain edges.
- Terrain, LiDAR acquisition, access, survey priorities, and mapping campaigns can correlate with one another and with actual geology; a propensity model may therefore absorb geologic prevalence if its interpretation is careless.
- An “exhaustively mapped” quadrangle flag cannot be inferred from a map-sheet grid or the mere presence of a 1:24,000 publication.

## Evidence boundary

No experiment, holdout score, confidence interval, feature-only AUC, propensity estimate, surface correlation, dot overlap, pixel-agreement check, validation result, or organizer receipt exists for this repo. All such fields remain `null`/`NOT_RUN` in [`../evidence/run_card.json`](../evidence/run_card.json). See [`SOURCES.md`](SOURCES.md) for links and source scope.
