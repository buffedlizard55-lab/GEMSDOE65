# Lane irregularities — GEMSDOE65 "bandrf" lane (IR-65-025)

This lane is published beside the repository's canonical lane. The canonical lane keeps its own
register (`registry/irregularities.json`, `docs/audit.html`); nothing here replaces it. Every entry
below is a finding of *this* lane, with its evidence on disk.

## IR-65-025a — the protocol's literal duplicate rule is degenerate on this registry

The lane protocol's stop rule is: stop if more than 70 % of the candidate's dots lie within 3 px of
one registry raster's dots. On this registry that rule cannot be satisfied by any dot field:

| measurement | value |
|---|---|
| footprint cells | 5 167 373 |
| cells inside the 3 px neighbourhood of *some* staged prior | 5 167 342 (99.9994 %) |
| a **uniformly random** 22 726-dot field inside that union (5 draws) | 0.99996 – 1.00000 |
| the same random field inside the single densest prior (`r11_greedy_mp.tif`) | 0.736 |
| this candidate, same statistic | 0.9998 |

The candidate is therefore indistinguishable from random noise under the literal rule. It is **not**
a duplicate under the tests that can discriminate: max Spearman ρ = 0.0440, max Jaccard = 0.0046,
byte-identity unique, pixel-identity unique, reverse overlap ≤ 0.026. The run card carries both the
raw flag count (4) and the demonstration (`uniqueness.literal_test_demonstration`).

**Disposition:** the rule is reported as degenerate rather than reinterpreted silently; the download
gate turns on the discriminating tests; both readings stay visible on the card. This is the honest
version of "we did not copy a prior raster": the test that would have said otherwise proves nothing
here, so the verdict rests on the tests that do.

## IR-65-025b — the mandated method was a null; the declared rule was not

Evaluator `gems57-pooled-hide-v2`, four blocked folds, 11 321 withheld positive pixels:

| arm | pooled blocked-hold-out DTI | 95 % CI |
|---|---|---|
| `nnpu` (matched baseline) | 0.00614 | [0.00121, 0.01164] |
| `prop` — SAR propensity-weighted ERM, weights clipped at 10 | 0.00790 | [0.00220, 0.01541] |
| `wire` — declared splay-band × range-front rule | **0.01646** | **[0.01201, 0.02113]** |

Paired `prop − nnpu` = **+0.00176, 95 % CI [−0.00596, +0.01112] → null** (the CI crosses zero).
Paired `wire − nnpu` = +0.01033 [+0.00324, +0.01751]. High-propensity-tercile mean DTI: `wire`
0.0266 vs `nnpu` 0.0034 → the tercile gate does not lose. Per fold the `prop` control wins on SE
(0.0204 vs 0.0147; tercile 0.0302 vs 0.0278) — recorded, not hidden.

**Disposition:** the SAR path is reported as a measured **negative** for the estimator as specified
(five declared covariates give a near-constant propensity, p10–p90 = 0.838–0.849, so re-weighting
has almost nothing to do); the shipped candidate uses the unfitted rule the same hold-out selects.

## IR-65-025c — the shared template was vendored twice, and the stale copy silently won

An earlier revision of this lane carried its own copy of the shared template at `src/gems57/`. That
copy was a *stale* variant: it used the opposite outside-footprint convention (all-finite zeros;
the canonical representation is NaN outside the footprint) and, being under `src/`, it shadowed the
pinned template at `vendor/template58/gems57` for every local import.

**Disposition:** the duplicate copy was deleted. The lane now imports the single pinned template
(`gems65.common` puts `vendor/template58` on `sys.path`; `tests/conftest.py` verifies the pin), and
every measurement was re-run on it: the leakage canary (top single-channel AUC 0.5786, nothing above
0.90), the four blocked folds, and the emission. The re-measured numbers are identical to those
previously reported, and the recommended upload is now the canonical **NaN-outside** encoding
(`…-nan.tif`), with the zeros-outside file kept only as a labelled, validator-failing diagnostic.
This entry exists because a shadowed fork is exactly the failure the standing instruction forbids.

## IR-65-025d — the SAR-EM class prior is not identified by PU data alone

Successive, documented harness revisions on the same fold produced `alpha_plug_in` of 0.877, 0.901
and 0.973 (and 0.247 in another configuration). This is direct evidence for the brief's own warning
that positives-selected-at-random cannot be identified from positives and unlabeled data alone.

**Disposition:** the propensity and prior are reported as a sensitivity analysis only; no result of
this lane depends on their absolute scale, and no projection is written as a score anywhere.
