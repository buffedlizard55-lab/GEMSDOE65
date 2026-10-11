# Session review 2 — 2026-10-11 UTC

**Outcome: negative, no TIF.** The SAR-EM protocol could not be run: the competition raster inputs, grid template, shared holdout evaluator, writer, validator, and prior-raster registry are not in this sandbox, and the official data is login-gated. No holdout DTI, rank correlation, or submission file was produced, so the promotion gate is not met and nothing is offered for download. No weekly submission slot was spent.

Every number below is labelled with one of: **VERIFIED** (fetched or recomputed here, with a link), **USER-REPORTED** (from the request, no receipt), **CLAIM-OTHER-SITE** (another project's own statement, not checked), or **PROJECTION** (never a score).

## 1. What was checked, and how

| Check | Result | Evidence |
|---|---|---|
| Repo state, readiness audit, unit tests | Blocked; 7 tests pass; audit exits 2 (feature stack, labels, template, `evaluate_holdout.py`, `submission_writer.py`, registry all missing) | `python3 scripts/audit_lane_readiness.py`, `python3 -m unittest discover -s tests` |
| DrivenData data tab | **Login page** — no data | fetch of `…/competition-doe-gems/data/` |
| Dropbox-hosted files (example_submission.tif, existing_faults.tif, numeric features) | **Landing page only**, no binary | fetch of the `example_submission.tif` link |
| Outbound network | GitHub, api.github.com, PyPI reachable; DrivenData, Dropbox, OpenEI, and GEMSDOE Pages not reachable by `curl` (fetch-page tool can read some pages) | `curl` probes |
| DrivenData problem page (metric + format) | **VERIFIED** — metric, α=0.2, β=0.8, 300 m triangular kernel, float32 single-layer, EPSG 32611, 100 m, values in [0,1], NaN/null outside bounds | [problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) |
| Metric worked example | **VERIFIED** — 3/(3+0.2·1.89+0.8·2) = 0.6027 (matches the official "0.60") | recomputed in Python |
| Official reference notebook | **VERIFIED** — saved outputs: feature and label rasters 3292 × 3730, EPSG:32611, 100 m; the prediction is written with the labels' transform | [notebook](https://github.com/drivendataorg/gems-prize-reference-solution/blob/main/unet-mc-cv-reference-solution.ipynb), commit `aebe92f` |
| Bekker, Robberechts & Davis citation | **VERIFIED** — authors Bekker, Robberechts, Davis; ECMLPKDD 2019; arXiv 2018. The repo's citation is correct. | [arXiv:1809.03207](https://arxiv.org/abs/1809.03207) |
| Bekker & Davis PMLR 94 (2018) | **VERIFIED** — SAR assumption and EM method | [PMLR v94 bekker18a](https://proceedings.mlr.press/v94/bekker18a.html) |
| Giddens & Faulds (2025), SGP-TR-229 | **VERIFIED** — ~91.9% of step-overs on range-front faults, with a stated detection bias from steep relief; the ~25% detailed-mapping figure is from that study's own area | [PDF](https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Giddens.pdf) |
| GEMSDOE32 site (the user's 0.2778 example) | Fetched. Page says H33-2-B2 is "UNSCORED" and that no organiser score exists for any artifact in that repo. See §2. | [GEMSDOE32 docs](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html) |

## 2. Why did the 0.2778 file score highest? (Answer, with its limits)

**Short answer: we cannot establish this from evidence available here.** The one public page that describes the file says it has no organiser score. The 0.2778 figure is USER-REPORTED with no receipt (IR-65-015). The same request also lists 0.3774 and 0.3195 as higher or top values (IR-65-014), so 0.2778 is not the top of the user's own list.

What the verified metric does tell us, from first principles:

1. **Costs are asymmetric.** In DTI = TPw / (TPw + 0.2·FPw + 0.8·FNw), an uncovered truth pixel costs four times as much as a spurious predicted pixel. A file that spreads moderate probability around the most likely fault corridors pays little for misses that are near the corridor, and collects credit for any hit within 300 m. That is why sparse, dense-core layouts can outscore broad ones.
2. **Credit is spatial, not pixel-exact.** The 300 m triangular kernel rewards predictions within 3 pixels of a truth pixel. Thinning a block of predictions so that each survivor is far from a catalogued fault (the GEMSDOE32 "deletion within 2 px" step) removes mass that was already covered, but this is a *claim* about that file; we did not reproduce it.
3. **The test set is not the catalogue.** The official page says the scored test set is a private set of new faults labelled by experts, and the final round adds verified new faults. A file tuned to the visible catalogue can gain on a catalogue holdout while gaining nothing on new faults (IR-65-016). That is the main reason our holdout DTI cannot predict leaderboard rank.

**Can we beat 0.2778?** Unknown. Nothing in this sandbox can measure it. The route the project has defined (SAR-EM vs nnPU on identical spatial folds, plus a holdout gate) is the right test, but it can only show catalogue recovery, so a pass is a necessary condition, not proof of a higher leaderboard score.

## 3. Parked hypotheses (out of the SAR lane; not run)

The request asked for 3–5 new hypotheses on other layers. The project lane rule forbids substituting another detector, so these are recorded only (IR-65-018). Each uses a layer named on the official problem page. Ranking is by expected gain × cost; **all gains are unmeasured**.

| Rank | Layer(s) (official feature list) | Signature targeted | Why it might catch a fault missing from the catalogue | Named non-fault mimic | Cost |
|---|---|---|---|---|---|
| A | Top-of-crustal magnetic source-depth estimate (magnetics group) | Lateral step in magnetic source depth along a linear trend | Offsets in magnetic basement can show where a fault is buried and absent from surface traces | Intrusive or lithologic contacts and basement highs | Low once the stack is loaded |
| B | Depth to conductive base (surface conductivity group) | Step in basin-bottom depth across a linear zone | Basin-bottom offsets can record faults under cover that were never mapped at the surface | Stratigraphic unconformities and basin-margin geometry | Low–medium |
| C | Geodetic dilatation, shear, and second invariant of strain (geodetic group) | Linear gradient in strain-rate magnitude | Deformation gradients can mark active faults that are missing from the trace catalogue | Groundwater-pumping subsidence and other anthropogenic deformation (needs a literature check before use) | Low (layers already in stack) |
| D | Density of earthquakes (seismic group) | Linear clustering of epicentres | Clusters can trace active structures not yet catalogued | Aftershock sequences and mining or quarry seismicity | Low |

**Top candidate and validation:** A. It cannot be validated on the spatial holdout until the official stack and the shared evaluator are present, so it has not been validated and may not spend a submission slot. Free official source needed: the competition's own feature raster, which the owner must obtain through the DrivenData data tab (login required). No other free source is needed for A, because the layer is in the competition stack.

## 4. Run card

The single canonical card is [`data/run-card.json`](data/run-card.json). It stays **negative**, with `holdout_dti.score = null`, `raster_sha256 = null`, and submission name `null`. Nothing was computed for it, so no value is reported as a score.

## 5. Recommended next steps (in order)

1. **Owner action (blocking):** obtain the official data through the authorized DrivenData account and place the files in `data/`: `training_features.tif` (or `numeric_features.tif`), `labels.tif`, `sample_submission.tif`, and the DEM link list. Record SHA-256 hashes. No credentials should be placed in the repository.
2. Make the shared holdout evaluator, writer, validator, and prior-raster registry available, unchanged, from the template. Do not rebuild them.
3. Run the SAR-EM vs nnPU comparison on identical folds, following the protocol in `HYPOTHESES.md`.
4. Decide the lane question (IR-65-018) before testing any parked candidate.
5. Re-check the GEMSDOE32 "UNSCORED" statement and the leaderboard values only through a permitted route (IR-65-014/015).

## 6. Verification notes

- All links above were fetched or inspected on 2026-10-11 UTC. Links to other sites are for manual review and are not treated as verified scores.
- No file in this repository was copied from another project's submission.
- The shape of 3292 × 3730 comes from the public reference notebook's saved output; it is not from the competition template and was not checked against it.
