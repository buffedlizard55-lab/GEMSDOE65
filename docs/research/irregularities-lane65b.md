# Irregularities found in this lane, and what was done about each

Every entry states what was observed, the measurement that established it, whether it was
fixed, and what remains open for the owner. Nothing here is silently waived.

| id | irregularity | status |
|---|---|---|
| IR-65-CAT-01 | The catalogue's weak topographic AUCs looked like a data error | **resolved**: the catalogue *is* the QFaults/INGENIOUS compilation |
| IR-65-FRONT-01 | "Distance to the range front" has no single defensible operationalization | **resolved by proxy**, documented |
| IR-65-IDENT-01 | The propensity is not identified from PU data alone; the EM mirrors | **resolved** by an external two-inventory anchor + proofs in tests |
| IR-65-PROP-01 | The pre-registered EM-selection rule accepted a degenerate near-constant propensity | **fixed** by pre-registration amendment A1; both experiments retained |
| IR-65-NORM-01 | SAR risk normalised by π·E[e] instead of ρ = P(s=1) | **fixed** before any experiment; guarded by a test |
| IR-65-SUBS-01 | Unweighted unlabeled subsampling inflated π from ≈0.02 to 0.867 | **fixed**; guarded by two tests |
| IR-65-FOLD-01 | Per-fold emissions OR-ed together multiplied scored mass by n_folds | **fixed**: out-of-fold score fields, one global emission per arm |
| IR-65-PEEL-01 | Peel used `d > peel_px` where the champion geometry is `d >= 3` px | **fixed** |
| IR-65-I2LEAK-01 | The propensity anchor would have been fitted on the same pixels instrument I2 scores | **fixed**: leave-one-quadrant-out anchor |
| IR-65-UNIQ-01 | The literal uniqueness rule is unmeetable for sparse fields | **flagged for the owner**, not waived |
| IR-65-COV-01 | Covariate receipt reports `mean_on_catalogue` = NaN for two covariates | **open** (cosmetic; the run reads `nanmean` over valid pixels) |
| IR-65-ACCESS-01 | No outbound access to the organizer, USGS, or the data mirrors | **open**; reported as a limitation |
| IR-65B-TEMPLATE-01 | Two divergent pins of the shared `gems57` template now live in this repository | **contained + reported**; owner consolidation needed |
| IR-65B-FORMAT-01 | The two pins contradict each other on the portal format (NaN vs zeros outside the footprint) | **flagged for the owner**; artefact written in zeros mode with the reason recorded |
| IR-65B-PARALLEL-01 | A second session ran the same lane and merged first; both verdicts are negative | **resolved by integration**, not by overwriting |

---

## IR-65-CAT-01 — is the catalogue the known-fault compilation? (resolved)

**Observed.** Every topographic covariate is near-random against the catalogue
(`relief_local` AUC 0.5633, `slope` 0.5577, `grav_basin_fill` 0.4593, `lidar_cover` 0.5205) but
strongly predictive of the state-geologic-map-only fault pixels (`relief_local` 0.7740,
`height_above_base` 0.7687, `slope` 0.7617). For a fault map of an extensional province that is
suspicious: faults are supposed to like relief.

**Measurement.** `scripts/diagnose_irregularities.py` rasterises the mirrored QFaults/INGENIOUS
`trace_segments_utm11.csv` (84,268 of 84,331 segments inside the grid, 1,126 lines) onto the
official grid and compares:

* catalogue pixels covered by rasterised traces: **96.54 %**; catalogue-to-trace distance
  median **0 px**, mean 0.035 px, p90 0 px,
  p99 1 px, **max 1 px** (Mann-Whitney p = 0
  that catalogue pixels are closer to a trace than non-catalogue pixels);
* all **84,331** segment rows of the mirrored file were rasterised
  (`all_touched=True`), giving **82,871** trace pixels inside the
  footprint, of which **71.05 %** are catalogue pixels —
  the catalogue is a *subset* of the trace network, i.e. the compiled traces that were accepted;
* morphology: **3,199** 8-connected components, median
  **12 px**, max **360 px**, and only
  **24 px** of 60,988 survive a 3×3 erosion
  (0.0394 %) — 1-pixel-wide lines, not areas.

**Resolution.** The catalogue is the USGS QFaults / INGENIOUS compilation, so its weak
topographic AUCs are a real property of a geophysics-inferred inventory, not a data error. This
is what makes the two-inventory differential a legitimate selection-bias signal: QFaults carries
many *Inferred* basin-margin faults drawn from geophysics, while state geologic maps are
bedrock-exposure maps. Receipt: `evidence/catalogue_identity.json`.

## IR-65-FRONT-01 — which range front? (resolved by proxy)

Four operationalizations were compared on one criterion: which carries the two-inventory
differential best (AUC of negative distance-to-front separating catalogue pixels from
state-map-only fault pixels).

| variant (1-px boundary isoline of the set) | set px | isoline px | median dist | bias AUC | AUC vs I2 | = stored covariate |
|---|---:|---:|---:|---:|---:|---|
| A_h50_isoline_over_5km_local_min | 3,616,040 | 160,275 | 28.60 | **0.6608** | 0.3561 | yes |
| B_toe_of_front | 260,866 | 78,466 | 31.30 | **0.6144** | 0.4067 | no |
| C_mid_slope_band | 2,572,243 | 221,096 | 10.63 | **0.5543** | 0.5312 | no |
| D_basin_edge | 1,078,921 | 119,209 | 33.62 | **0.6397** | 0.3331 | no |

Variant A is byte-identical to the stored `range_front` covariate the model actually uses, and
was kept; it is labelled a **proxy of limited geomorphic fidelity** everywhere it
appears: its job is to carry the differential, not to be a mapped front. A real front needs raw
3DEP 10 m/1 m tiles, which are unreachable from this sandbox (IR-65-ACCESS-01). Receipt:
`evidence/range_front_variants.json`.

*Superseded numbers.* An earlier ad-hoc diagnostic in this session rasterised merged polylines
rather than per-segment lines and reported 89.25 % coverage and different variant pixel counts.
The committed script is the authority; its values are the ones above, and the difference is
recorded here rather than quietly overwritten.

## IR-65-IDENT-01 — the propensity is not identified from PU data alone (resolved)

The observed-data likelihood of a SAR PU model,
`L = Σ_labeled log(g·e) + Σ_unlabeled log(1 − g·e)`, depends only on the product
`g(x)e(x) = P(s=1|x)`. Any re-factorisation of the same product fits equally well, and the
parametric class does not exclude the mirror (a logistic `e` mirrored about 0.5 is still
logistic).

`tests/test_anchor.py::test_em_direction_is_not_identified` demonstrates this numerically on
synthetic data with a known propensity: the EM returns both a correct-direction branch
(corr > +0.5) and a mirrored branch (corr < −0.5), and their observed-data log-likelihoods differ
by less than 2 %. Two earlier EM initialisations were retired for this reason (a
labelled-vs-unlabelled logistic start gave Spearman −0.899; an 8-iteration constant-`e0`
responsibility warm start gave −0.906).

**Resolution.** A second public inventory anchors the direction: with
`q(x) = P(in catalogue | in catalogue ∪ reference, x)` and reference-inventory completeness `c`,
`q = e/(e + c(1−e))` inverts to `e(x;c) = c·q/(1 − q + c·q)`. The ordering is identified by data;
`c` is one documented scale parameter, swept as the sensitivity analysis the brief asks for.
`tests/test_anchor.py::test_anchor_recovers_true_propensity_direction` shows the anchor recovers
the true ordering (corr > 0.6) for every `c` in the grid on synthetic data where the EM alone
mirrors it.

## IR-65-PROP-01 — the selection rule accepted a degenerate propensity (fixed)

**Observed in `evidence/e1_px5.json`.** Under the original rule ("use the EM when its Spearman
against the anchor is positive"), the EM was selected in all four folds, but its propensity was
near-constant: **e ∈ [0.2808, 0.2961]** across the whole footprint (p01–p99), mean 0.2881 on
catalogue pixels vs 0.2889 off them — i.e. no usable variance and the wrong (weakly) direction.
Consequences visible in the same receipt: `A2_sar_1me` was indistinguishable from `A1_sar`
(paired Δ +0.000120, CI [−0.000464, +0.000825]) and every arm scored AUC ≈ 0.50 against the
state-map-only instrument, where single covariates reach 0.77. A sign test on the ordering cannot
detect a variance collapse.

**Fix.** Pre-registration amendment `GEMSDOE65-PREREG-1-A1` (see
`registry/preregistration.json`): the anchored propensity is primary and the EM becomes a
reported sensitivity arm (`A3_sar_em_1me`). The amendment is arm-neutral — no ranking rule, risk
functional, fold, seed, budget, emission geometry, gate or ship rule changed — and the
pre-amendment experiment is retained and reported next to the post-amendment one. The amendment
cannot make the gate pass; it only stops the mechanism from being switched off by a defect.

## IR-65-NORM-01 / IR-65-SUBS-01 / IR-65-FOLD-01 / IR-65-PEEL-01 (all fixed before the gate)

* **Normaliser.** Scaling the labelled SAR block by `π·E_x[e]` is biased when `g` and `e`
  correlate — and they do here. Correct normaliser is `ρ = P(s=1) = n_L/(n_L+n_U)` on
  **population** counts. Guarded by
  `tests/test_risks.py::test_wrong_normaliser_pi_ebar_is_detected`.
* **Subsample π.** With a 20,000-row unlabeled subsample of a 5,116,066-pixel population the EM
  returned **π = 0.867** against a truth of ≈0.02 because every subsample row was treated as one
  population member. Fixed with `u_weight = n_population/n_subsample`; guarded by both tests in
  `tests/test_propensity_subsample.py`.
* **Per-fold emission.** Emitting inside each fold and OR-ing the results multiplies the scored
  mass by the number of folds. Replaced by out-of-fold score fields plus **one global emission
  per arm per instrument**.
* **Peel.** `d > peel_px` admits dots at exactly 3.00 px only by accident; the champion geometry
  is `d >= 3` px (300 m), which is what `allowed_mask` now enforces. Measured in the E1 receipt:
  `min_dist_to_visible_px = 3.0`.

## IR-65-I2LEAK-01 — the anchor must not see the pixels it is scored on (fixed)

Instrument I2's truth *is* the state-map-only population, and the anchor is fitted on that same
population. Fitting the anchor on all of it would make I2 an in-sample instrument and its AUC
meaningless. Fix: for fold *k* the anchor is fitted on reference pixels **outside** quadrant *k*,
and I2 is scored leave-one-quadrant-out on quadrant *k*. Instrument I1 needs no such treatment —
its truth is withheld catalogue components, which are excluded from the anchor's catalogue sample
by construction and cannot appear in the reference sample (which is >3 px from the whole
catalogue).

## IR-65-UNIQ-01 — the literal uniqueness rule is unmeetable for sparse fields (flagged)

The inherited rule blocks a candidate when more than 70 % of its dots fall within 3 px of *any*
one registry raster's dots. Dense lattice comparators in the family registry
(`calib_r13lattice_00904.tif` and friends) cover nearly the whole footprint, so the sibling
repository measured **0.9985** overlap for its best candidate — a value no sparse field can avoid.
This lane reports both readings side by side (the literal one over all accessible rasters, and a
like-for-like one restricted to dot-field comparators, which is the only comparison in which a
dot-overlap test carries information) and **flags the conflict for the owner instead of waiving
it**. Changing the rule to get a pass would be a waiver, and this session does not make one.

Also note the inventory itself is incomplete: only sibling public-repository rasters are
accessible from this sandbox, so `complete_accessible_scan` is `false` and the shared tool
therefore returns `unique: false` regardless of the measurements.

## IR-65-COV-01 — cosmetic receipt bug (open)

`scripts/build_covariates.py` writes `mean_on_catalogue = NaN` for `slope` and `grav_basin_fill`
because sentinel pixels sit inside the catalogue. The lane reads `nanmean` over valid pixels, so
no result is affected; the receipt should still be fixed upstream.

## IR-65-ACCESS-01 — no outbound access (open, reported)

`drivendata.org`, `docs.nlr.gov` (rules PDF), the five Dropbox data mirrors, `gdr.openei.org`,
`usgs.gov`, `gbcge.org` and `raw.githubusercontent.com` all return HTTP 000 from this sandbox.
Official statements are therefore quoted from the family's line-by-line verification record
(`60GEMSDOE/docs/research/verification-2026-10-04.md`, read 2026-10-04) with links for manual
review, and are labelled as such rather than presented as freshly verified. No organizer receipt
exists anywhere in this repository: **nothing was uploaded and no submission slot was spent.**


---

## IR-65B-TEMPLATE-01 — two divergent pins of the shared template (contained, reported)

**Observed.** Merging `origin/main` into this branch revealed that the canonical lane-65 session
vendors the shared template at `vendor/template58/` (pinned to `buffedlizard55-lab/58GEMSDOE` tree
`3ccda56f…`, per-file hashes in `docs/data/shared_template_pin.json`), while this session had
committed its own copy of the same template under `src/gems57/`. Because `gems57` is a single
module name per Python process, the copy imported first wins for everything imported afterwards:
with `src/` on `sys.path`, this session's copy shadowed the canonical pin and
`tests/test_submission.py::test_writer_actual_tiff_and_single_member_zip_roundtrip` failed (it
asserts NaN outside the footprint; the shadowing writer produced zeros).

**Contained.** `src/gems57/` was moved to `vendor/template60/` with a provenance file
(`vendor/template60/PROVENANCE.md`) that records the measured SHA-256 divergence per module:
`__init__`, `emit`, `evaluate_holdout`, `metric`, `network`, `spatial` are **byte-identical**
between the pins; `gates`, `grid`, `holdout`, `submission_writer`, `uniqueness`, `validate`
differ. `scripts/_bootstrap.py` puts `vendor/template60` first for this lane's scripts only and
then **asserts which copy actually loaded** (`assert_template60`), so a silent version swap cannot
change a published number — the guard caught a real mis-wiring while it was being added. Test
modules reach `gems57` through the canonical pin (`from gems65 import common`), so the shared
pytest process loads exactly one template. Full suite after the change: **113 passed**, and
`scripts/check_repository.py` reports `ok: true` with no problems.

**What this means for the numbers.** Every HOLDOUT-DTI on this lane's pages comes from
`evaluate_holdout.py` and `metric.py`, which are byte-identical to the canonical pin, and the fold
quadrant assignment (`holdout.quadrant_ids`) is byte-identical too — so the DTI arithmetic is
reproducible under the canonical template. The **fold constructor is not**: template58 has no
`buffered_component_draw` (it exposes `build_buffered_holdout_context` / `HoldoutContext` and marks
`build_holdout` legacy). Porting this lane's instruments to that API would change the folds and
therefore every number, so it is left as the owner's consolidation step rather than being done
silently at merge time.

**Not a private fork.** Nothing in `vendor/template60/` was edited; it is a labelled second pin,
reported here, per the standing rule "if a shared tool is wrong, fix it once in the template and
report it; never keep a private fork".

## IR-65B-FORMAT-01 — the two pins contradict each other on the portal format (flagged)

The canonical pin (`vendor/template58/gems57/grid.py`) says `mode="nan"` "is the submission
representation" and that `mode="zeros"` "is not portal-format compliant". This lane's pin
(`vendor/template60/gems57/grid.py`) says the opposite: `mode="zeros"` "is the only
submission-compatible mode" and `mode="nan"` is "for local diagnostics only … a prior portal range
error does not establish NaN as its cause".

This artefact was written in **all-finite `zeros` mode**, because (a) the organizer's own reference
solution (<https://github.com/drivendataorg/gems-prize-reference-solution>) writes an all-finite
raster with **no** `nodata` tag, (b) the official format statement recorded in the family's
verification notes says values must be in [0, 1] with null/NaN outside the bounds — which zeros also
satisfies, since 0 is inside [0, 1] and the scored footprint is what the metric reads, and (c) the
portal rejection this lane was asked to fix (*"Predicted values must be in range [0, 1]"*) arrived
with NaN primaries. The contradiction cannot be settled from this sandbox
(`drivendata.org` is unreachable, IR-65-ACCESS-01), so it is flagged: **if the owner prefers the
canonical NaN representation, `scripts/make_submission.py` should write both variants** — the
sibling session already publishes `-nan.tif` and `-zeros.tif` pairs, which is the safest convention
and is recommended here.

## IR-65B-PARALLEL-01 — two sessions ran the same lane (resolved by integration)

The parallel-run protocol anticipates this. Session `arena/1217c9a0-gemsdoe65` implemented the same
SAR-PU lane first and merged PRs #7 and #9 (canonical site, `RUN_CARD.json`, verdict NEGATIVE,
six published rasters behind a loud not-cleared banner). This session
(`arena/98cb5eb2-gemsdoe65`) implemented it independently: different covariate pipeline
(`covariates_sar2inv.py`), different propensity estimator (a two-inventory anchor with the EM as a
sensitivity arm, versus an EM with a Horvitz-Thompson π), different instruments (leave-one-quadrant-out
I2), different emission geometry (3 px NMS with `d >= 3` peel at a 38,000-dot budget), and a
pre-registered ship rule with an amendment trail.

**Both sessions reached a negative verdict, for different reasons.** That agreement is the useful
result: two independent implementations of the same lane, with different propensity estimators and
different instruments, both fail their own pre-registered gates. Nothing was overwritten in the
merge — the canonical site, run card, guards and tests are untouched, and this session's pages live
under `docs/lane65b/` with its own artefact, run card and evidence files. Drift check between the
two lanes' artefacts is reported below.

**Cross-session drift check** (the protocol's duplicate test, applied to the two lanes' published
rasters rather than to the registry at large; receipt `evidence/cross_session_drift.json`,
script `scripts/cross_session_drift.py`): against all **6** rasters the sibling
session published, worst Spearman ρ = **0.0170** (limit 0.9),
worst forward dot overlap = **0.2873** (limit
0.7), worst Jaccard = **0.0122** (limit
0.5) → `duplicate_by_any_limit = false`.
The informative number is the overlap: **28.7 %** of this lane's
dots land within 300 m of the sibling lane's best-matching field — far above chance for two sparse
38,000-dot fields on 5.17 M pixels, far below the duplicate threshold. Two independent
implementations of the same lane agree on roughly a quarter of placements and disagree on the rest,
which is consistent with both verdicts being negative for *different* reasons.
