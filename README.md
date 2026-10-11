# GEMSDOE65 — evidence-first GEMS fault-mapping research

> **Every work session starts here.** Re-read this standing brief, `docs/IRREGULARITIES.md`, `docs/HYPOTHESES.md`, `docs/SOURCES.md`, and `evidence/run_card.json` before changing models, data, the website, or any submission artifact.

## Submission status — read before anything else

**There is no submission GeoTIFF in this repository. It is NOT OK to download or submit a file from this project.** The current checkout contains no competition data, no shared evaluator/writer/validator, no local prior-raster registry, and no candidate raster. The site intentionally offers no enabled download link. Do not synthesize a placeholder, copy a sibling project's raster, or report a projected score as an organizer score.

The only current decision is **negative / blocked**: the improvement gate has not been measured, so no weekly submission slot should be used. The exact machine-readable record is [`evidence/run_card.json`](evidence/run_card.json).

## Mission and values

Build an auditable, reproducible way to identify **previously unmapped geological faults** in the DOE GEMS / GeoDAWN region, test whether they indicate geothermal resources, and—only after a successful, documented validation—produce a legal single-band GeoTIFF for the competition. The task predicts faults, not geothermal vents directly. Never promise a leaderboard score or prize.

- **Maximize P(Win):** prioritize work that could improve independently blocked holdout performance; do not spend competition slots on untested ideas or polish an unvalidated model.
- **Own the Outcome:** verify artifacts from bytes on disk, report failures, preserve provenance, and never describe an unrun step as complete.

## Standing task brief and non-negotiable protocol

This section is the durable operational form of the user's project prompt. It keeps the requirements while separating verified facts from inconsistent or unverified score claims.

1. **Research before modeling.** Read the official DrivenData problem, data page, rules, current leaderboard, USGS GeoDAWN materials, primary PU-learning papers, and the organizer reference solution. Keep dated links and the scope of each source in `docs/SOURCES.md`. The leaderboard is a changing public snapshot, not a substitute for local validation or private-round performance.
2. **Stay in this lane.** Test selection-bias-aware positive–unlabeled (PU) learning: treat catalogue faults as positives selected at random given covariates (SAR), not as a uniformly sampled or complete fault set. Estimate `e(x) = P(labeled | fault, x)` with Bekker–Davis SAR-EM and the prescribed small propensity feature set: local relief, slope, a gravity-derived basin-fill proxy, LiDAR coverage, and distance to range front. If a public, defensible index of exhaustively mapped quadrangles exists, use it to anchor propensity scale; otherwise report sensitivity analysis, because PU data alone do not identify a unique propensity scale. Train Bekker–Robberechts–Davis propensity-aware empirical risk with inverse-propensity weights clipped at 10, against an nnPU baseline on identical folds. Do not turn this into an unrelated fault-lineament or dot-placement lane.
3. **Reuse, do not fork.** Use the template's cached feature stack, `evaluate_holdout.py`, and `submission_writer.py`. If a shared tool is wrong, fix it in that shared template and report the fix. This checkout does not contain those components; stop rather than silently rebuilding private copies. `scripts/preflight.py` inventories the blocker without generating predictions.
4. **Holdout is hide-and-recover.** Withhold whole fault segments with a buffer; derive every catalogue-based feature only from visible faults; mask visible faults pixel-exactly; score pooled DTI using alpha 0.2, beta 0.8, and the 300 m triangular kernel. Compare to the current local holdout best. Report withheld-positive count and a 95% CI. A public leaderboard value or model projection is never a holdout score.
5. **Leakage canary.** Evaluate each feature alone on the holdout before trusting it. AUC above 0.90 is leakage until proven otherwise. Do not use a feature that encodes withheld traces or derives from hidden labels.
6. **Predeclared gates.** A candidate must improve overall blocked-holdout DTI and must not lose in the highest-propensity tercile. Before placement and again on final dots, compare to every prior registry raster: stop and record a duplicate if rank correlation exceeds 0.90 or if more than 70% of dots fall within 3 pixels of a registry raster's dots. No registry is present here, so uniqueness cannot be claimed.
7. **One JSON run card per experiment.** Record the hypothesis; mechanism; named non-fault process that could mimic it; HOLDOUT-DTI (evaluator version, withheld-positive count, 95% CI); correlation/overlap versus registry; raster SHA-256; validator output; submission name and a note no longer than 140 characters; and verdict `promote` or `negative`. Use only `HOLDOUT-DTI` or `ORGANIZER-CONFIRMED` copied from an actual submission-page receipt for performance scores. Keep projections, public-board snapshots, owner-reported values, and missing receipts explicitly separate.
8. **Submission output contract.** A final file must be a single-band float32 GeoTIFF on the exact official sample grid (CRS, shape, transform, bounds, resolution), EPSG:32611, 100 m, with predictions in [0, 1] and NaN/null only outside the footprint. Re-read and validate the written bytes. For the historical form error “Predicted values must be in range [0, 1]”, test every in-footprint value, reject infinities and NaNs inside, normalize/clip only valid pixels, then run the official/shared validator. No such validation has run in this checkout.
9. **User-facing site.** The executive summary is linked at the top. The site must say plainly whether a file is safe to submit. A one-click TIF download may appear only after all validation, uniqueness, and holdout gates pass. It must never silently surface a placeholder or a copied prior submission. Current state: **no file; do not submit**.
10. **Budget and process.** Stop at three experiments or two hours. Promotion to a real slot is a separate selector step, subject to the competition's weekly cap. Run three passes: implement and verify; review/fix; re-check against the full request. No slot has been used by this repository review.

## Verified repository state (2026-10-11 UTC)

- The starting Git tree had one tracked file, an 11-byte `README.md`; no prior model, tests, data, cache, raster, registry, website, downloader, evaluator, writer, or validator was present.
- The official competition data URL redirected this unauthenticated session to DrivenData's login page. No credentials were requested or stored, and no competition data were downloaded.
- The official live leaderboard no longer supports the prompt's statement that 0.3195 is the current top: the live page displayed another participant above that value when checked. The value 0.2778 shown in the prompt also appears on the official public board under participant `extradr19`; that page does not identify it with the named GEMSDOE32 TIFF. GEMSDOE32's public artifact manifest lists the TIFF with `receipt: null` and an owner-generated note that calls its value projected/UNSCORED. See `docs/IRREGULARITIES.md` and `docs/SOURCES.md`. These are provenance findings, not model-score validations.
- Giddens & Faulds' 2025 proceedings paper reports that about 91.9% of the study's identified step-overs are associated with range-front faults and explicitly raises topographic visibility bias. The separate “about 25% detailed mapping” claim has not been verified in the official sources checked and is not used as a calibration constant.
- See the [`review site`](index.html), [`executive summary`](executive-summary.html), [`hypothesis ranking`](hypotheses.html), [`research and provenance analysis`](research.html), and [`source register`](sources.html).

## Candidate experiment selected for the next validation opportunity

The top-ranked hypothesis is **terrain/coverage-conditioned SAR propensity**: estimate selection propensity from the specified five covariates, then compare propensity-aware PU risk with nnPU on identical, frozen, buffered segment holdouts. This is a proposed test—not a result. It cannot run here because the data and required shared template tools are absent. See [`docs/HYPOTHESES.md`](docs/HYPOTHESES.md) for all four preregistered candidates, caveats, source availability, cost, and the exact gate.

## Start-of-session checklist

- [ ] Read this README and the linked evidence files above.
- [ ] Run `python scripts/preflight.py`; fail closed if data, tools, or registry are missing.
- [ ] Confirm the dated official sources and score provenance before quoting any result.
- [ ] Run no experiment unless the shared template stack and blocked evaluator are present.
- [ ] Do not publish a TIF or use a submission slot without the predeclared gate and run card.

## Reproduce this review

```bash
python -m unittest discover -s tests -v
python scripts/preflight.py
python -m json.tool evidence/run_card.json >/dev/null
```

`preflight.py` is only a readiness inventory. It does not train, evaluate, validate, create a raster, fetch authenticated competition files, or spend a submission slot.
