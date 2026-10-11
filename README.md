# GEMSDOE65 — selection-bias-aware fault discovery

> **Read this file first in every session.** It is the standing brief, the operating contract, and the record of what this checkout can and cannot prove. The single-line submission decision lives in [`docs/data/run-card.json`](docs/data/run-card.json) under `verdict.one_line` and is rendered at the top of the [status page](docs/index.html).

**Lane in one line.** Model catalogue inclusion as *Selected At Random* rather than "unlabeled = negative", estimate the propensity `e(x) = P(labeled | fault, x)` with SAR-EM, train with a propensity-weighted empirical risk (inverse-propensity weights clipped at 10) against a matched nnPU baseline on identical blocked folds, and only offer a downloadable submission when the promotion gate, the on-disk validator and the registry-uniqueness comparison all clear.

---

## 1 · Where the project stands right now (updated at the end of each session)

| Item | State |
|---|---|
| Inputs | **Present and integrity-pinned** (not organizer-authenticated): `evidence/input_pins.json`, six SHA-256 pins, restored by `scripts/restore_inputs.py`. The 419 MB feature stack lives under `data/official/` (git-ignored) and the three derived mirrors under `data/mirrors/`. |
| Shared template | **Present**: `src/gems57/` is the pinned sibling template (grid, hide-and-recover hold-out, metric, dot allocator, fail-closed writer, validator, registry uniqueness) imported rather than forked. |
| Lane code | **Present**: `src/gems65/` adds the propensity covariates, the SAR-EM fit, the matched risk arms, the declared emission rules and the gate arithmetic. |
| Evidence | `evidence/lane_canary.json` (leakage canary), `evidence/lane_holdout.json` (blocked hold-out), `evidence/lane_holdout_folds/*.json` (per-fold cache), `evidence/run_card.json` (the decision). |
| Registry | **62 staged, hash-verified prior rasters** indexed by `scripts/build_registry_index.py` into `data/registry/registry_index.json`. The index is written **fail-closed** (`complete_accessible_scan: false`): the staged set is complete *as staged*, but no scan from this repository can certify that it is the entire public owner-repository inventory. |
| Submission | **See the run card.** The status page states the decision in plain words at the very top; nothing here is a leaderboard forecast. |

Known irregularities are logged in [`docs/IRREGULARITIES.md`](docs/IRREGULARITIES.md) and summarised in [`docs/irregularities.html`](docs/irregularities.html). Read them before trusting any number on this page.

---

## 2 · Standing project brief

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

Only offer a GeoTIFF when every scientific, uniqueness, and format gate passes. It must be an easy one-click download with a unique filename and short note, and the site must say plainly whether it is cleared to submit. The competition's published format is a single-band float32 GeoTIFF, EPSG:32611, 100 m, matching the official template's dimensions/bounds/geotransform, with prediction values in [0, 1] and null/NaN outside the footprint. Do not put NaN or a negative nodata sentinel inside the footprint. The executive summary must explain the submit form step by step.

### Research and site requirements

- Use official, verified sources; preserve source links and separate verified facts, internal claims, projections, and unknowns.
- Maintain ranked, testable hypotheses and record why a process could be mimicked by non-fault geology or surface processes.
- Link to the official leaderboard without automatically fetching, monitoring, copying, or mirroring its contents. DrivenData's current Terms of Use prohibit automated access to monitor or copy site material and also prohibit manual monitoring/copying without prior written consent. Do not create or refresh a local leaderboard feed unless written authorization or an official permitted API is obtained. A leaderboard row is not a receipt tying a score to a specific TIF.
- Make the homepage simple and readable. Put submission readiness and the download decision at the very top; if there is no approved file, show a prominent **do not submit** state.
- Preserve data provenance and hashes. Do not commit large data, credentials, or copied submission artifacts unless explicitly required.

### Arena working values

**Maximize P(Win).** In every decision, weigh tradeoffs, assess risk, and choose the path that maximizes the probability of success. Set aside emotion and make the decision that maximizes P(Win).

**Own the Outcome.** Own results end to end. Treat failure and success as signals to improve. When a problem can be addressed, act and report the evidence rather than hiding a failed gate.

---

## 3 · The original request, quoted

Kept here so the brief cannot drift from what was asked. Quotation marks are verbatim fragments of the project request; anything in brackets is this repository's own annotation.

> “[Produce] a UNIQUE TIF submission — not copied from any GEMSDOE site or prior raster.” … “[Method:] selection-bias-aware PU learning; catalogue = positives selected at random given covariates (SAR), not completely at random; ~92% of step-overs lie on range-front faults (steep relief → easy to see); only ~25% mapped at ≈1:24,000 (Giddens & Faulds 2025, SGP-TR-229). Estimate propensity e(x)=P(labeled|fault,x) with Bekker & Davis EM (PMLR v94, 2018). Small covariate set: local relief, slope, gravity-derived basin-fill proxy, lidar coverage, distance to range front. Anchor scale with exhaustively mapped quadrangles if a public index exists; otherwise report as sensitivity analysis (PU alone non-identifiable). Train with propensity-aware empirical risk of Bekker, Robberechts & Davis (arXiv:1809.03207), weights clipped at 10, vs nnPU baseline on identical folds. Gate: higher blocked-holdout DTI overall AND no loss in highest-propensity tercile. Finish: normalize [0,1]; float32 EPSG:32611 100 m GeoTIFF (NaN only outside footprint); pass validate_submission.py; hash/pixel-agreement check vs all prior rasters; offer download only if gate met, else log negative result.”

> “PARALLEL-RUN PROTOCOL: single lane, no drift; if rank-corr vs any registry raster >0.90 or >70% of dots within 3 px of one registry raster's dots → log duplicate and stop; check on surface before placement AND on final dots. Reuse template's cached feature stack, evaluate_holdout.py, submission_writer.py; if a shared tool is wrong, fix once in the template and report — never keep a private fork.”

> “Holdout = hide-and-recover: withhold whole fault segments with a buffer, derive every catalogue-based feature only from visible faults, mask visible faults pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel).”

> “LEAKAGE CANARY: test each feature alone on holdout before trusting any result; AUC >0.90 = leakage until proven otherwise.”

> “Do not stop after pass 1.” — three passes: implement and verify; review bugs, missing requirements and edge cases and fix them; re-check against the original request and improve accuracy, reliability, completeness and code quality.

> The prompt-literal tokens “validate_[submission.py]”, “evaluate_[holdout.py]” and “submission_[writer.py]” are markdown-link artifacts of the original message; the operative filenames are `validate_submission`/`scripts`-side validators, `evaluate_holdout.py` and `submission_writer.py`, which is what this repository uses. The request also carried entries dated 2026-10-12 against a 2026-10-11 review date; both are logged as irregularity IR-65-013.

---

## 4 · How to run this lane

```bash
# 0 · environment (numpy, scipy, rasterio, scikit-learn)
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

# 1 · inputs: restore and verify the six pinned hashes (idempotent, refuses mismatches)
python3 scripts/restore_inputs.py --check          # verify only
python3 scripts/restore_inputs.py                  # copy from the public mirrors if absent

# 2 · prior-raster registry index (fail-closed inventory certificate)
python3 scripts/build_registry_index.py            # write, or --check to re-fingerprint

# 3 · the three experiments
python3 scripts/run_lane.py canary                 # leakage canary over the blocked folds
python3 scripts/run_lane.py holdout --folds 0      # matched arms + declared rule, resumable
python3 scripts/run_lane.py emit                   # gate-gated emission, validation, uniqueness

# 4 · render the status page and machine-readable feed from the evidence
python3 scripts/build_site.py        # or --check to detect a stale page

# 5 · policy and contract tests
python3 -m unittest discover -s tests -v
python3 scripts/audit_lane_readiness.py
```

Every experiment writes a JSON artifact; the run card is the only place where a verdict is asserted, and it is written by the code, never by hand.

### Evidence classes used in this repository

| Label | Meaning |
|---|---|
| `LEAKAGE-CANARY` | A diagnostic. Carries no score and cannot promote anything. |
| `HOLDOUT-DTI` | A measurement by the shared evaluator on the blocked hide-and-recover folds, always with evaluator version, withheld-positive count and 95 % CI. Not a leaderboard value. |
| `REGISTRY-MEASUREMENT` | The duplicate comparison against the staged rasters (Spearman ρ, 3 px dot overlap, Jaccard). |
| `ORGANIZER-CONFIRMED` | Only ever copied from a submission-page receipt, with its submission id. Nothing in this repository is labelled this way unless a receipt exists. |

---

## 5 · Why the cited 0.2778 is what it is, and whether a higher submission is achievable

The full argument is on [docs/geology.html](docs/geology.html) and [docs/competitive-context.html](docs/competitive-context.html); the short version:

1. **The figure is not receipt-backed.** The sibling lane marks its H33 artifact *UNSCORED*, its manifest carries no receipt, and a leaderboard row does not identify a filename. The file-to-score premise is therefore **unknown**, and the honest answer to “why did that file score 0.2778?” is that it cannot be established from public evidence.
2. **As a number, 0.2778 has a precise meaning.** With α = 0.2 on false positives, β = 0.8 on false negatives and a 300 m triangular kernel taken as a max over the kernel, a dot field scores ≈ 0.28 when roughly a third of the scored truth volume is covered within the kernel while a false-dot mass of the same order as the truth mass is spent. It is a *placement and mass-budget* result, not a formatting one: any dot lattice at ≤ 3 px spacing is self-consistent with the kernel (a 2 px lattice guarantees ≥ 0.53 credit everywhere inside its corridor).
3. **Geology explains the ceiling band.** Basin-and-Range earthquakes produce 0.5–5 m scarplets, which a 100 m grid cannot resolve; one cell of mislocation already costs a third of the kernel credit. The private labels are the step-overs and splays that mapping missed, and this repository *measures* where those sit: a median 9.4 px (940 m) from the nearest visible mapped trace, p10 4.1 px, p90 20 px — a stand-off band, not a halo. Non-fault lineaments (dune crests, pediment edges, cut-banks, shorelines, roads, canals) supply the false-dot mass.
4. **Higher scores are achievable by other teams on the public record** (values above both figures cited in the brief have appeared on the official leaderboard, which this repository links to but never mirrors). For this lane, what is claimed is a *measured* `HOLDOUT-DTI` on a deliberately harder instrument plus a uniqueness certificate — never a projection written as a score.

---

## 6 · Session-start checklist

- [ ] Read this entire README and the current [`run card`](docs/data/run-card.json).
- [ ] Read [`geology.html`](docs/geology.html), [`research.html`](docs/research.html), [`hypotheses.html`](docs/hypotheses.html), [`irregularities.html`](docs/irregularities.html).
- [ ] Run `python3 scripts/restore_inputs.py --check`, `python3 scripts/build_registry_index.py --check`, `python3 -m unittest discover -s tests -v`, `python3 scripts/build_site.py --check`.
- [ ] Confirm the evidence artifacts are the ones generated by the code in this checkout (compare `implementation_sha256` in the pooled summary).
- [ ] Use the [official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) only through an authorized access method; this project does not fetch, monitor, or mirror its rows.
- [ ] Do not offer a GeoTIFF unless `verdict.download_cleared` is `true` and the failing fields are empty.

## Project pages

- [Status, downloads and the decision](docs/index.html) · [status.json](docs/data/status.json)
- [Executive summary — exactly how to submit](docs/executive-summary.html)
- [Why the score is what it is (geological reasoning)](docs/geology.html)
- [Score-provenance audit and achievability](docs/competitive-context.html)
- [Ranked hypotheses](docs/hypotheses.html) · [research](docs/research.html) · [source register](docs/SOURCES.md)
- [Irregularities](docs/irregularities.html) · [IRREGULARITIES.md](docs/IRREGULARITIES.md)
- [Run card (JSON)](docs/data/run-card.json) · [detailed status](docs/STATUS.md)
