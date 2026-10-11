# Session review 2 — 2026-10-11 UTC (integration with main)

**Outcome: negative. No new TIF is offered, no new experiment was run, and no weekly slot was used.** The canonical decision remains [`evidence/run_card.json`](../evidence/run_card.json) (verdict `negative`, `eligible_for_download: false`). This note adds verified checks and corrections; it does not change that decision.

Labels used below: **VERIFIED** (fetched or recomputed in this session, with a link), **MEASURED-MAIN** (recorded in main's evidence files), **USER-REPORTED** (from the request, no receipt), **CLAIM-OTHER-SITE** (another project's own statement, not checked).

## 1. Why no new experiment or TIF in this session

- `AGENTS.md` item 6: the initial three-scenario experiment is consumed, and a new experiment needs a fresh preregistration that does not reuse a tuned holdout. `evidence/run_card.json` records `experiments_completed: 3`.
- The gate is negative on five stated reasons (`evidence/gate.json`: overall improvement not established, highest-propensity tercile not established, registry uniqueness not cleared, comparable incumbent not cleared, optimization not cleared). A new raster cannot pass those by being regenerated.
- A duplicate-stop or lane rule was already triggered on the registry (MEASURED-MAIN, `README.md`). Placement was not attempted.
- The request asks for a TIF "unique and downloadable". A file that fails the gate cannot be offered, and no sibling site's file may be copied (see I01 and I02 in `evidence/irregularities.json`).

## 2. What was verified in this session

| Check | Result | Source |
|---|---|---|
| Full test suite with `requirements.txt` installed (`.venv`, ignored by git) | **78 passed** | `python -m pytest -q` |
| Without the requirements installed | 7 import errors (`numpy`, `pytest` missing). Same on a clean main checkout, so not caused by this branch. | `python -m unittest` |
| Readiness audit | Exit 2 (`gate: negative`). Competition files are not restored in this sandbox. | `scripts/audit_lane_readiness.py` |
| Official metric and format text | **VERIFIED** — distance-weighted Tversky, α=0.2, β=0.8, 300 m triangular kernel; single-layer float32, EPSG 32611, 100 m, values in [0,1], NaN/null outside bounds | [DrivenData problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) |
| Worked example | **VERIFIED** — 3/(3+0.2·1.89+0.8·2) = 0.6027, consistent with the page's "0.60" | recomputed |
| Reference-notebook grid | **VERIFIED** — saved outputs: feature and label rasters 3292 × 3730, EPSG:32611, 100 m | [reference notebook](https://github.com/drivendataorg/gems-prize-reference-solution/blob/main/unet-mc-cv-reference-solution.ipynb) |
| Grid in the quarantined raster | **MEASURED-MAIN** — 3730 × 3292, matching the reference | `evidence/run_card.json` |
| Citation check, Bekker, Robberechts & Davis | **VERIFIED** — authors match the repo's citation; ECMLPKDD 2019 with arXiv 2018 | [arXiv:1809.03207](https://arxiv.org/abs/1809.03207) |
| Data tab | Login page. No credentials were used. | DrivenData data URL |
| Dropbox links | Landing page only, no file | Dropbox `example_submission.tif` link |

## 3. Data provenance — a flag for review

Main's data is **not organizer-authenticated**. `scripts/download_competition_data.sh` restores it from a sibling owner's GitHub repository (`buffedlizard55-lab/GEMSDOE`), and `evidence/data_integrity.json` says so explicitly. The hashes match the owner's pins; they do not prove the bytes are the organizer's files. The competition terms on use and redistribution of the data were not checked in this session. **Before any submission**, the owner should confirm the data source against the official data tab.

## 4. The 0.2778 question

**Short answer: this cannot be established from the evidence here.**

- The GEMSDOE32 page (fetched 2026-10-11) gives the H33-2-B2 note the label "UNSCORED" and says there is no organiser score for any artifact in that repository (**VERIFIED**). Its own projection is 0.2747 and is labelled a model. The 0.2778 figure in the request is therefore **USER-REPORTED** (`I19`).
- The request's own leaderboard figures conflict: 0.3774 as the GEMSDOE top, 0.3195 as "highest right now". The GEMSDOE32 page's own snapshot (dated 2026-10-04) lists #1 0.3262, #2 0.3195 (**CLAIM-OTHER-SITE**). None is confirmed against the official board, and the Terms of Use bar automated access (`I05`).
- Raster-level evidence about the 0.2778 file (its positive pixels are a strict subset of its base, and the removed dots lie within 2 px of the catalogue) is **MEASURED-MAIN** and is analysed in [`review.md`](review.md). It explains what the file *does*, not why it *scored*.
- The metric explains the asymmetry. An uncovered truth pixel costs 0.8 and a spurious prediction costs 0.2, so spreading moderate probability along likely corridors is cheap, while thinning redundant dots can raise credit per emitted pixel. This is mechanism reasoning from the official formula, not a measured attribution.
- **The holdout cannot tell us whether a file beats 0.2778.** Our holdout truth is the catalogue. The official scored set is new expert-labelled faults (`I20`). A catalogue gain can be real and still give no leaderboard gain.

## 5. Parked hypotheses (not run; outside the SAR lane)

The request asks for 3–5 new hypotheses on other official layers. The lane rule forbids testing another detector, so these are recorded only (`I21`). Each names a layer from the official problem page. Ranking is by expected gain × cost; **every gain is unmeasured, and none may use a slot.**

| Rank | Layer(s) (official feature list) | Signature | Why it could catch a missing fault | Named non-fault mimic | Cost |
|---|---|---|---|---|---|
| A | Top-of-crustal magnetic source-depth estimate | Lateral step in source depth along a linear trend | Offsets in magnetic basement can mark buried faults that are absent from surface traces | Intrusive or lithologic contacts; basement highs | Low once the stack is loaded |
| B | Depth to conductive base | Step in basin-bottom depth across a linear zone | Basin-bottom offsets can record faults under cover | Unconformities and basin-margin geometry | Low–medium |
| C | Geodetic dilatation, shear, second invariant | Linear gradient in strain-rate magnitude | Deformation gradients can mark active faults missing from the catalogue | Groundwater-pumping subsidence (needs a literature check before use) | Low |
| D | Density of earthquakes | Linear clustering of epicentres | Clusters can trace active structures not yet catalogued | Aftershock sequences; mining or quarry seismicity | Low |

**Top candidate:** A. It cannot be validated on the spatial holdout until the feature stack is restored and the owner confirms the lane question. The required source is the competition feature raster, from the official data tab, which needs an authorised account.

## 6. Next steps

1. **Owner:** confirm the data source against the official data tab (§3), and decide the lane question for §5.
2. Do not run a new holdout or spend a slot until a fresh preregistration is written (`AGENTS.md` item 6).
3. Re-check any leaderboard value only through an authorised route (`I05`, `I19`).
4. If the lane is extended, test candidate A first, on the same folds as nnPU, with the capped weights and the registry checks in `research/preregistration.md`.

## 7. Notes

- This review changes only `research/` and `evidence/irregularities.json` (three new items, I19–I21). Main's README, run card, gate, and preregistration are unchanged.
- No file was copied from another project's submission. The 3292 × 3730 shape comes from the public reference notebook's saved outputs and is consistent with main's measured raster.
