# GEMSDOE65 — selection-bias-aware fault discovery

> **Session gate: NEGATIVE. No submission GeoTIFF is available or approved. Do not download a substitute or submit an earlier project's raster.** This checkout has no competition rasters, shared holdout evaluator, submission writer, or prior-raster registry. The negative run card is [`docs/data/run-card.json`](docs/data/run-card.json).

This README is the project's standing brief. **Read it before each project session**, then read the linked research, hypotheses, irregularities, and latest run card before changing code or making score claims. The brief below consolidates the repeated instructions from the project request without discarding their operative requirements.

## Standing project brief

Build an auditable, reproducible system for the DOE GEMS Prize Challenge (DrivenData competition 306). The competition predicts **geological faults that may indicate geothermal resources**; it does not directly predict geothermal vents. The goal is scientifically credible discovery of previously unmapped faults, a useful current information feed, and—only after evidence gates pass—a unique, valid, easy-to-download GeoTIFF. Never copy or relabel a prior submission as a new result.

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

Only offer a TIF when every scientific, uniqueness, and format gate passes. It must be an easy one-click download with a unique filename and short note, and the site must say plainly whether it is cleared to submit. The competition's published format is a single-band float32 GeoTIFF, EPSG:32611, 100 m, matching the official template's dimensions/bounds/geotransform, with prediction values in [0, 1] and null/NaN outside the footprint. Do not put NaN or a negative nodata sentinel inside the footprint. The executive summary must explain the submit form step by step.

### Research and site requirements

- Use official, verified sources; preserve source links and separate verified facts, internal claims, projections, and unknowns.
- Maintain ranked, testable hypotheses and record why a process could be mimicked by non-fault geology or surface processes.
- Keep a current official-leaderboard feed, while clearly distinguishing an official leaderboard row from a receipt tying a score to a specific TIF.
- Make the homepage simple and readable. Put submission readiness and the download decision at the very top; if there is no approved file, show a prominent **do not submit** state.
- Preserve data provenance and hashes. Do not commit large data, credentials, or copied submission artifacts unless explicitly required.

### Arena working values

**Maximize P(Win).** In every decision, weigh tradeoffs, assess risk, and choose the path that maximizes the probability of success. Set aside emotion and make the decision that maximizes P(Win).

**Own the Outcome.** Own results end to end. Treat failure and success as signals to improve. When a problem can be addressed, act and report the evidence rather than hiding a failed gate.

## Session-start checklist

- [ ] Read this entire README and the current [`run card`](docs/data/run-card.json).
- [ ] Read [`research and sources`](docs/research.html), [`ranked hypotheses`](docs/hypotheses.html), and [`irregularities`](docs/irregularities.html).
- [ ] Run `python3 scripts/audit_lane_readiness.py` before modeling.
- [ ] Confirm the cached data, exact shared holdout/writer tools, and prior-raster registry are present; do not silently replace them with sibling-repo code.
- [ ] Refresh or inspect the [official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) and record when it was read.
- [ ] Do not build or offer a TIF if any required evidence gate is absent.

## Current verified checkout state

The checked-out branch started from commit `90ca1cea667dc1427de27ef997634f3305a7c164`; at session start its tracked tree contained only this README. This change adds an evidence site, a leaderboard-feed parser, a presence-only readiness audit, and tests—not a model or submission pipeline. There is still no `data/`, required segment evaluator, shared writer, prior-raster registry, or TIF in this checkout. The upstream public `GEMSDOE` repository has related components, but its names and block/emission evaluation are not the required segment hide-and-recover evaluator; they are not silently substituted here. The official competition data tab requires access, and no authenticated competition files are present locally.

The current negative run, source audit, and historical-score correction are recorded in [`docs/`](docs/). No submission slot was spent. The Pages workflow is present, but the repository's live Pages setting is still legacy publishing from `main:/`; a repository admin must switch **Settings → Pages → Source** to **GitHub Actions** and rerun the workflow before the new site replaces the current README-only page.

## Project pages

- [Status and leaderboard feed](docs/index.html)
- [Executive summary and exact submission steps](docs/executive-summary.html)
- [Ranked within-lane hypotheses](docs/hypotheses.html)
- [Audit of the cited leaderboard score](docs/competitive-context.html)
- [Research and verified sources](docs/research.html)
- [Irregularities and blockers](docs/irregularities.html)
- [Three-pass session review](docs/session-2026-10-11.md)
- [Current run card (JSON)](docs/data/run-card.json)

## Run the lightweight checks

```bash
python3 -m unittest discover -s tests -v
python3 scripts/audit_lane_readiness.py
```

The readiness command returns a non-zero exit status when required data, shared tools, or the registry are missing. It is presence-only: a clean result is not a scientific pass or TIF authorization. That is intentional; a blocked gate must not be converted into a synthetic raster or a score claim.
