# Pass 3 — re-check of the deliverable against the original request

Passes 1 and 2 are logged in the README (implement/verify, then review and fix bugs). This pass
walks the request line by line and states where each requirement landed, or why it did not.
Nothing is marked done unless a committed file shows it.

## The lane's method requirements

| # | requirement | where | status |
|---|---|---|---|
| 1 | Treat the catalogue as positives **selected at random given covariates (SAR)**, not SCAR | `src/gems65/risks.py` (`sar_risk`), `src/gems65/propensity.py` | done — and the SCAR reduction is unit-checked at `e ≡ e0` |
| 2 | Estimate `e(x) = P(labeled \| fault, x)` with the **EM of Bekker & Davis (PMLR v94, 2018)** | `src/gems65/propensity.py::em_propensity`; arm `A3_sar_em_1me` | done, and reported as a **sensitivity arm** because the EM's direction is not identified (IR-65-IDENT-01, proved in `tests/test_anchor.py`) |
| 3 | Covariate set: local relief, slope, gravity-derived basin-fill proxy, LiDAR coverage, distance to range front | `src/gems65/covariates.py`, `lane.PRIMARY_COVARIATES` | done — the five pinned covariates, built from the official 19-band stack, receipt in `.cache/covariates_px5.receipt.json` |
| 4 | **Anchor its scale with exhaustively mapped quadrangles if a public index exists** | `src/gems65/anchor.py` | done in the form the sandbox allows: no quadrangle-level completeness index is reachable (IR-65-ACCESS-01), so the anchor uses a **second public fault inventory** (state geologic map) with completeness `c` as the documented scale parameter, swept over `[0.25, 0.5, 1.0]` |
| 5 | Propensity not identifiable → **report as a sensitivity analysis** | `docs/irregularities.md` IR-65-IDENT-01, `tests/test_anchor.py`, `e_sensitivity` in the experiment receipt | done — formal statement, numerical demonstration, and a `c`-grid |
| 6 | Train with the **propensity-aware empirical risk** of Bekker, Robberechts & Davis (arXiv:1809.03207), **weights clipped at 10** | `src/gems65/risks.py` (`w = min(1/e, 10)`, `v = min((1−e)/e, 10)`), `tests/test_risks.py` | done — unbiasedness by Monte Carlo (\|err\| < 4e-3) and analytic gradients (15 tests) |
| 7 | **nnPU baseline on identical folds** | arm `B_nnpu`, `nnpu_risk` (Kiryo et al. 2017) | done — identical folds, architecture, seed, unlabeled subsample, budget and emission geometry |
| 8 | **Gate**: higher blocked-holdout DTI overall AND no loss in the highest-propensity tercile | `registry/preregistration.json::gate`; `evidence/e1b_px5.json::I1_hide_recover`, `I1_tercile_gate` | evaluated mechanically; the verdict is in `evidence/live_run_card.json` |
| 9 | Normalize to **[0,1]**; float32 EPSG:32611 100 m GeoTIFF | `scripts/make_submission.py`, `gems57.submission_writer`, `gems57.validate` | done — with a **flagged deviation**: all-finite `zeros` mode instead of NaN outside the footprint (see below) |
| 10 | Pass `validate_submission.py` | `gems57.validate.validate` + `assert_submittable`, re-reading the written file | done — the shared family validator is the same check set; the organizer script itself is unreachable |
| 11 | **Hash / pixel-agreement check vs all prior rasters** | `gems57.uniqueness.compare_array_to_registry` over every accessible registry raster, plus `two_phase_summary` | done for what is accessible; the inventory is incomplete and the literal rule is unmeetable for sparse fields (IR-65-UNIQ-01) — flagged, not waived |
| 12 | **Offer download only if the gate is met, else log the negative result** | banner in `docs/index.html` generated from the run card verdict | done — the banner is the first thing on the page and the verdict string is mechanical |

### Flagged deviation on item 9

The brief says NaN outside the footprint. The artefact is written all-finite with zeros outside
the footprint, because (a) the organizer's own reference solution
(<https://github.com/drivendataorg/gems-prize-reference-solution>) writes an all-finite raster
with **no** `nodata` tag, and (b) NaN primaries are what produced the portal rejection
*"Predicted values must be in range [0, 1]"* this lane was asked to fix. `gems57.validate` checks
both readings (`no_nan_anywhere`, `outside_footprint_zero`, `range_0_1_guaranteed`,
`in_footprint_range_0_1`). This is recorded as a deviation rather than a silent choice.

## The user's acceptance criteria

| requirement | where | status |
|---|---|---|
| Obvious whether the generated TIF is OK to download and submit | full-width banner at the top of `docs/index.html` and of the executive-summary subpage, generated from `verdict` | done |
| Easy one-click download | primary button in the banner (`downloads/<artefact>.tif`), plus ZIP, writer receipt and run card | done |
| Executive-summary **subpage** explaining exactly how to submit, at the very beginning of the site | `docs/executive-summary.html`, linked second in the header nav and from the banner; 8 numbered steps including sha256 verification, the portal path, the name/note fields and the receipt-logging step | done |
| Unique submission name + short note ≤ 140 chars | `NAME` / `NOTE` in `scripts/make_submission.py`, lengths asserted by the shared writer (which rejects > 140) | done |
| Fix the range error the user hit | all-finite `zeros` mode + writer that refuses non-finite or out-of-range fields + validator re-read | done |
| Explain at PhD level why `h33-h33-2-b2` scored 0.2778 and how to beat it, then use that answer | `docs/research/why-02778-and-what-beats-it-2026-10-11.md` (copied from the sibling repo with a provenance header) plus a new section stating what this lane adds; site subpage `research/why-02778.html` | done |
| Propose 3–5 **new** geological hypotheses with layers, signature/transform, why it catches catalogue-missing faults, how it differs from the repo; ranked by expected DTI gain vs cost; validate the top candidate on the blocked holdout before spending a slot; name free official sources and confirm obtainability | `docs/research/hypotheses-2026-10-11.md` (five hypotheses, ranked, with obtainability per source); top candidate implemented and gated; **zero slots spent** | done |
| Parallel-run protocol: stay in lane; drift check; label every number; leakage canary; budget | lane paragraph in the README; drift check via `gems57.uniqueness` on surface and dots; evidence-class tags on every number and on the site; `evidence/leakage_canary.json`; budget in `registry/preregistration.json` | done, with the uniqueness caveat flagged (IR-65-UNIQ-01) |
| Put the prompt in the README and re-read it every session | `README.md` — the standing brief is embedded verbatim in a collapsible block, with this repo's lane paragraph stated separately and the substitution flagged | done |
| Work autonomously, verify line by line from official sources with links, flag irregularities, no hallucinations | no human input was requested; `docs/irregularities.md` (12 entries); official links on the site and in the README; every number carries an evidence class and a receipt path | done — with the access limitation stated (IR-65-ACCESS-01): official statements are quoted from the family's verification record, not re-fetched, because those hosts are unreachable here |
| Report limitations and what access is needed | `docs/index.html` §9 and the README's limitations section | done |
| Three passes, then a PR merged to main, plus suggestions for remaining work | this file; PR from `arena/98cb5eb2-gemsdoe65`; suggestions in the README | done |
| Never keep a private fork of a shared tool | `src/gems57/` is copied verbatim; no shared tool was modified. The propensity/normaliser fixes are in **this lane's** modules (`gems65`), and `PROVENANCE.md` records the copy | done |

## Things this pass found and corrected

1. The README's reproduction list omitted `scripts/diagnose_irregularities.py`, so two evidence
   files quoted by the site (`catalogue_identity.json`, `range_front_variants.json`) would not
   have been regenerable. Added.
2. `scripts/make_submission.py` printed a validator key that does not exist (`n_positive`); the
   real key is `emitted_positive_pixels`. Fixed — a wrong key here would have made the artefact
   step fail after the file was already written.
3. `range_front_variants` initially rebuilt variant A as `(h − min_filter(h)) ≥ 50` when the
   cached `height_above_base` **already is** height above a 5 km local minimum; that would have
   double-detrended the front and changed the kept variant. Fixed to `h ≥ 50`.
4. `tests/test_risks.py::test_em_recovers_known_propensity` asserted a positive correlation with
   the true propensity — an assertion the estimator cannot guarantee (IR-65-IDENT-01). Rewritten
   to assert what is identifiable (magnitude of the ordering, and sign/size of the product `g·e`)
   with the direction pinned separately in `tests/test_anchor.py`.
5. `propensity.sigmoid` was used by tests but only defined in `risks`; re-exported from
   `propensity` so callers do not need both modules.

## What would change the verdict

The verdict is mechanical, so this is a statement about measurements, not judgement:

* the primary gate needs `A1_sar − B_nnpu` on I1 with a paired 95 % CI excluding 0. In
  `e1_px5` the point estimate was +0.000905 with CI [−0.004230, +0.006227] — the effect is an
  order of magnitude smaller than the noise, so **no amount of re-running under the same design
  will pass it**; the design would have to change (a stronger ranker, or an instrument that
  represents the live target better).
* the tercile condition needs `A1_sar ≥ B_nnpu` restricted to the highest-propensity tercile.
* the ship rule then chooses between `A1_sar` and `A2_sar_1me` using the I2 comparison.

If the gate does not pass, the honest deliverable is the negative result plus the artefact marked
`DO-NOT-SUBMIT`, which is what the brief asks for ("else log the negative result").
