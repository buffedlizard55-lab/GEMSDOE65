# GEMSDOE65 — selection-bias-aware PU learning for the GEMS fault map

**Live site:** https://buffedlizard55-lab.github.io/GEMSDOE65/docs/index.html — Executive Summary
first, with the one-click submission download and the exact steps to enter it in the competition.

**Competition:** DrivenData 306, *DOE GEMS* (GeoDAWN geothermal exploration). Closes
2026-12-03; the final round re-scores one chosen file against an expert-expanded label set, so
the thing being rewarded is **new fault discovery**, not redrawing the existing catalogue.

**Current candidate:** `docs/downloads/gems65-sarprop-pu-v1.tif` — sha256
`12240335ff72b4f36714265ccbceec93b114fe06b0ca7abe7e9611cd559618a2`, 74,351 dots, 192 KB,
float32 EPSG:32611, all-finite and inside `[0, 1]`.

---

## Status (read this before anything else)

| Gate | Result | Evidence |
|---|---|---|
| Competition grid verified | **PASS** — 3730×3292, EPSG:32611, transform `(100,0,243350,0,−100,4508550)` | `evidence/grid_verification.json` |
| Holdout instrument reproduced exactly | **PASS** — seed 2026, hide 0.20 → 11,360 withheld positives | `evidence/ingest.json` |
| Leakage canary | **CLEAN** — worst single-feature discriminative AUC 0.5586 (limit 0.90) | `evidence/canary.json` |
| Predeclared gate, SAR-propensity vs nnPU | **PROMOTE** — HOLDOUT-DTI 0.073242 vs 0.067864; top-propensity tercile 0.081533 vs 0.069734 | `evidence/gate.json` |
| Emission rule measured, not assumed | **MEASURED** — monotone to saturation; NMS at the kernel radius; prune ≤2 px | `evidence/budget_curve.json`, `evidence/prune.json` |
| Hypothesis that failed | **NEGATIVE** — forbidding the 3 px halo around known faults lowers holdout DTI at every arm | `evidence/emission_halo.json` |
| On-disk format validator (frozen template) | **PASS** — single band, float32, all-finite, min 0, max 1, 74,351 positives | `docs/downloads/gems65-sarprop-pu-v1.json` |
| Parallel-run duplicate audit vs 655 published rasters | see `docs/verification.html` | `evidence/uniqueness.json` |
| Organizer acceptance / leaderboard score | **NOT KNOWN** — nobody has spent a slot on this file yet | — |

Every number on the site is `HOLDOUT-DTI` (measured here) or `ORGANIZER` (copied from a
competition source). The holdout is a **relative instrument**: it scores withheld catalogue
pixels only, so it ranks arms — it is never comparable with a leaderboard score.

---

## The charter

> **What this section is.** This is the standing request this repository works from, preserved in
> session context and reproduced here so that every session starts by re-reading it. It is
> deliberately labelled as *preserved text, not a certified word-for-word transcript of the
> original message*: quoted historical scores inside it are superseded by the status table above,
> which is measured. The same convention is used by the sibling lane repo (57GEMSDOE,
> `TASK_PROMPT.md`).

### The standing request

> MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION. DO NOT COPY A PREVIOUS SUBMISSION
> UNLESS IT'S FOR LEARNING AND EDUCATION. BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION. IT MUST BE
> OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.
>
> There should be an easy to download submission tif file as described by the prompt. Read the
> entire prompt.
>
> Work line by line, verify from official verified trusted sources, and provide links for manual
> review. No manual input — work autonomously. Flag any irregularities for review. NO
> HALLUCINATIONS — verify line by line. Verify no hallucinations.
>
> Keep Arena's "Core Values" (Maximize P(Win)) and "Own the Outcome" as focal points when
> building/researching/suggesting/implementing.
>
> Put this prompt into the repo README (as the charter) and read it every time we work on the
> project. Create a pull request and merge it onto `main`: make suggestions for what work still
> needs to be done and list limitations in the way of a successful project.
>
> The site must be a clean, organized, easy-to-read UI with official verified source links, an
> Executive Summary subpage at the very beginning explaining exactly how to make a submission into
> the contest, and an obvious one-click TIF download. It should solve having to manually check
> everything, with an up-to-date current feed.
>
> Run the task through multiple passes: Pass 1 implement + verify; Pass 2 review for bugs, missing
> requirements, wrong assumptions and edge cases, and fix; Pass 3 re-check the entire
> implementation against the original request and improve accuracy, reliability, completeness and
> code quality. Do not stop after the first pass.

### This lane's method paragraph (binding)

> Selection-bias-aware PU learning. Treat the catalogue as **SAR**: estimate the propensity
> `e(x) = P(labeled | fault, x)` with the **EM method of Bekker & Davis (PMLR v94, 2018)**.
> Covariates: local relief, slope, gravity-derived basin-fill proxy, lidar coverage, distance to
> range front; anchor the scale with exhaustively-mapped quadrangles if a public index exists,
> otherwise report it as a sensitivity analysis. Train with the propensity-aware risk of
> **Bekker, Robberechts & Davis (arXiv:1809.03207)**, weights clipped at 10, against an **nnPU
> baseline on identical folds**. Gate: higher blocked-holdout DTI overall **and** no loss in the
> highest-propensity tercile. Finish by normalizing to `[0,1]`, writing a float32 EPSG:32611 100 m
> GeoTIFF, passing `validate_submission.py`, running a hash/pixel-agreement check against all prior
> rasters, and offering the download **only if the gate is met** — otherwise log the negative
> result.

### Parallel-run protocol (binding)

1. **Stay in lane.** Stop (log a duplicate) if rank correlation with any registry raster exceeds
   0.90, or if more than 70% of my dots fall within 3 px of one registry raster's dots. Check on
   the surface before placement **and** on the final dots.
2. **Reuse, don't rebuild.** Use the template's cached feature stack, `evaluate_holdout.py` and
   `submission_writer.py`; fix a shared tool once, never keep a private fork.
3. **Label every number** as HOLDOUT-DTI (evaluator version, # withheld positives, 95% CI) or
   ORGANIZER-CONFIRMED. A projection is never written as a score.
4. **Leakage canary.** Any single feature with holdout AUC above 0.90 is leakage until proven
   otherwise.
5. **Run card.** One JSON card: hypothesis; mechanism; the named non-fault process that could mimic
   it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output;
   submission name + note ≤140 characters; verdict promote/negative. **Negative results are
   deliverables.**
6. **Budget.** Stop after 3 experiments or 2 hours. Do not pick submissions: promotion to a real
   slot is a separate selector step within the weekly cap.

### Constraints carried from the user

- The submission must be **unique**, not a copy of any existing submission, and it must be
  **obvious on the site** whether the file is OK to download and submit.
- Artifacts must satisfy the competition's own format rules. A previous file from this family was
  rejected with `"Predicted values must be in range [0, 1]"`; outputs must lie in `[0, 1]`, and the
  export policy here is therefore **all-finite** (zeros outside the footprint) rather than NaN.
- The submission form takes a single-band GeoTIFF (or a ZIP of one), needs a unique name, and
  offers an optional ≤140-character note.
- Flag irregularities; verify line by line; no hallucinations.

---

## How to submit the file

1. Download `docs/downloads/gems65-sarprop-pu-v1.tif` (or the `.zip`, which contains exactly that
   one GeoTIFF).
2. Sign in at https://www.drivendata.org/competitions/306/competition-doe-gems/ and open the
   submit page.
3. Name it `gems65-sarprop-pu-v1` and paste the note
   `Selection-bias-aware SAR propensity PU (Bekker-Davis EM), nnPU-gated.`
   (69 characters, limit 140).
4. Record the returned score and submission id in `evidence/` — that is the only way a number here
   ever becomes ORGANIZER evidence.

Rules in force (verified against the rules PDF, sections 3.1–3.6): up to **three**
automated-scoring submissions per week, one final selection per entity, and a Generative-AI usage
disclosure in the narrative.

---

## Reproduce it from scratch

```bash
python3 scripts/run_lane.py ingest          # verify grid + lidar, reproduce the holdout draw
python3 scripts/run_lane.py gate            # the predeclared arm comparison  -> evidence/gate.json
python3 scripts/canary.py                   # leakage canary                -> evidence/canary.json
python3 scripts/budget_curve.py             # measured budget curve         -> evidence/budget_curve.json
python3 scripts/emission_halo.py            # the rejected halo hypothesis  -> evidence/emission_halo.json
python3 scripts/run_lane.py emit            # live score field + dots       -> evidence/emit.json
python3 scripts/prune_analysis.py           # the 0.2778 reconstruction      -> evidence/prune.json
python3 scripts/run_lane.py prune --radius 2.0
python3 scripts/run_lane.py write           # frozen writer + on-disk gate  -> evidence/submission_receipt.json
python3 scripts/run_lane.py uniqueness      # duplicate audit vs 655 rasters-> evidence/uniqueness.json
python3 scripts/run_lane.py site            # rebuild docs/ from evidence/
```

`src/gems65/template/` is a byte-for-byte copy of the shared `gems57` modules and is **never
edited**; see `evidence/` for the pinned hashes.

---

## What is still outstanding

Full list with reasoning on `docs/limitations.html`. The short version:

1. **Spend a weekly slot on this file and record the receipt.** Nothing else can turn the relative
   holdout number into a real one.
2. **Multi-seed the gate.** The +0.0054 overall delta rests on one draw (seed 2026); it needs an
   interval across seeds before it should be trusted as a general claim.
3. **Add `tests/test_pu.py`** — synthetic SAR recovery (validated interactively at corr(e_hat,
   e_true) = 0.98) and emission invariants (dots >3 px apart, no mass on the catalogue,
   all-finite output).
4. **Push coverage rather than budget.** The ceiling arithmetic on `docs/analysis-02778.html` shows
   a ~0.44 ceiling at this true-positive mass; the binding constraint is distinct structures
   recovered, so the next experiments should add information, not dots.
5. **Owner rulings still open:** IR-58-08 (two uniqueness regimes) and IR-S6-01 (soft priors vs the
   "dot" convention). Neither blocks this file.

---

## Sources

- Competition problem statement and submission format —
  https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
- Competition data page (sample submission, features, labels) —
  https://www.drivendata.org/competitions/306/competition-doe-gems/data/
- Official rules, September 2026 (sections 3.1–3.6) — https://www.nlr.gov/docs/fy26osti/96647.pdf
- Bekker & Davis, *Learning from positive and unlabeled data with a selection bias*, PMLR v94
  (LIDTA 2018) — https://proceedings.mlr.press/v94/bekker18a.html
- Bekker, Robberechts & Davis, *Beyond SCAR: self-propensity weighted learning for learning from
  positive and unlabeled data*, arXiv:1809.03207 — https://arxiv.org/abs/1809.03207
- INGENIOUS Great Basin regional fault compilation (label provenance, rules footnote 4) —
  https://doi.org/10.15121/1881483
- DrivenData reference solution — https://github.com/drivendataorg/gems-prize-reference-solution
- EPSG:32611 — https://epsg.io/32611

## Irregularities flagged for review

- **IR-2** — the 0.2778 score is attributed in prior notes to participant *extradr19*, but no file
  receipt for that attribution exists in any repo inspected. What *is* verified is the raster:
  `GEMSDOE32:docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif`, and its
  exact set identity against the 0.2708 parent (`GEMSDOE28:…-h27-4-r1-solo-d2-8-…-allfinite.tif`).
- **IR-58-08**, **IR-S6-01** — owner rulings outstanding; see §5 above.
- The published leaderboard high recorded in older notes (0.3195, "highest") is **stale**: the saved
  organizer snapshot of 2026-10-11 puts 0.4133 first and 0.3195 at rank 8.
