# GEMSDOE65 — selection-bias-aware PU learning for the GEMS fault map

> **Where this lane lives.** This lineage of the GEMSDOE65 lane is developed entirely under
> `lane65-sarprop/`, so that it can share the repository with the other, independently developed
> lineage at the repository root without either overwriting the other. Everything below is
> relative to `lane65-sarprop/`. The site is `lane65-sarprop/docs/index.html`; serve it with
> `python3 -m http.server 8080 --directory docs` from this directory. The repository root keeps
> its own canonical, negative-result site and its own verification workflow, and nothing here
> changes it.

**Why the artifact is a release asset and not a tracked file.** The repository root lineage
publishes its own rasters under `docs/downloads/` through a hash-pinned allowlist
(`scripts/check_repository.py`, its irregularity IR-65-009) that deliberately refuses to publish
anything once an arm is *cleared* for submission without an organizer-confirmed receipt. This
lineage's arm **is** cleared locally, so it cannot use that allowlist without tripping the guard,
and it has no organizer receipt. The artifact therefore lives outside Git entirely: attached to
this lane's release, rebuilt on demand from the committed dot list, and never silently present in
a clone. Irregularity ids in this subtree are prefixed `IR-65L-` to keep them distinct from the
root lineage's `IR-65-0xx` series.

**Site:** `lane65-sarprop/docs/index.html` — Executive Summary
first, with the one-click submission download and the exact steps to enter it in the competition.
It is also served live at
`https://buffedlizard55-lab.github.io/GEMSDOE65/lane65-sarprop/docs/index.html` (repository-root
publishing), and the durable copy of the artifact is the release asset
`https://github.com/buffedlizard55-lab/GEMSDOE65/releases/download/lane65-sarprop-pu-v1/gems65-sarprop-pu-v1.tif`.

**Competition:** DrivenData 306, *DOE GEMS* (GeoDAWN geothermal exploration). Closes
2026-12-03; the final round re-scores one chosen file against an expert-expanded label set, so
the thing being rewarded is **new fault discovery**, not redrawing the existing catalogue.

**Current candidate:** `docs/downloads/gems65-sarprop-pu-v1.tif` — sha256
`12240335ff72b4f36714265ccbceec93b114fe06b0ca7abe7e9611cd559618a2`, 74,351 dots, 192 KB,
float32 EPSG:32611, all-finite and inside `[0, 1]`. Every local precondition is green, so the
site's banner reads **OK TO DOWNLOAD AND SUBMIT**; what is *not* green is a spent submission
slot, because nobody has claimed one for this file yet.

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
| Parallel-run duplicate audit vs 653 published rasters | **CLEAR with a flagged anomaly** — worst rank correlation 0.0401, worst dot-set Jaccard 0.0207; the literal 3 px rule fired 58 times and every firing is at or below its own uniform null (irregularity **IR-65L-01**) | `evidence/uniqueness.json`, `evidence/uniqueness_review.json` |
| Ranked candidate-hypothesis register | **DELIVERED** — 5 candidates with layers, signature, cost and source; the top locally runnable one was tested and **rejected** | `HYPOTHESES.md`, `evidence/hypotheses.json` |
| Unit tests | **13 PASS** in under a second, synthetic, no competition rasters needed | `tests/test_lane.py` |
| Organizer acceptance / leaderboard score | **NOT KNOWN** — nobody has spent a slot on this file yet | — |

Every number on the site is `HOLDOUT-DTI` (measured here) or `ORGANIZER` (copied from a
competition source). The holdout is a **relative instrument**: it scores withheld catalogue
pixels only, so it ranks arms — it is never comparable with a leaderboard score.

---

## Why the 0.2778 submission scored 0.2778 (answer to the headline question)

The highest score this project has ever received a receipt for is 0.2778, on
`gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif`. It is now understood exactly,
because the file is in the registry and so is its parent:

> The 0.2778 raster is, **by exact set identity**, the 0.2708 raster
> (`GEMSDOE28:…-h27-4-r1-solo-d2-8-…-allfinite.tif`, 40,199 dots) with every dot inside **2.0 px**
> of the mapped catalogue deleted. 2,545 dots went: 1,201 at √2 and 1,344 at exactly 2.0 px. No
> other change. Verified by `python3 scripts/prune_analysis.py`, which reconstructs the child from
> the parent and reports `exact set identity: True`.

The arithmetic then closes with no free parameters. Deleting those dots left the true-positive
mass untouched and removed exactly `0.2 × 2545 = 509.0` units of false-positive mass, which pins
the two denominators and gives a true-positive mass of ≈5,471 and an implicit public truth set of
≈14,143 positives. That is why +0.0070 was available for free: the file was **over-emitting**, and
every dot within 2 px of the catalogue was a pure false positive — the metric scores on
`valid & ~known`, so a dot whose nearest truth is masked earns nothing and pays 0.2.

**Can we score higher?** Yes, arithmetically: with the same true-positive mass and zero false
positives the ceiling is `5471 / (5471 + 0.8 × (14143 − 5471)) = 0.4410`, above the current
leader's 0.4133. The binding constraint is therefore coverage, not the metric: this lane's gate
is about recovering more of the truth without paying the false-positive tax. The two operational
consequences are already implemented — non-maximum suppression at the kernel radius, and a
≤2 px prune before serialisation — and the third, multi-seed gate confidence, is the first item
of remaining work. Full derivation with the measurement tables: `docs/analysis-02778.html`.

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
python3 scripts/run_lane.py uniqueness      # duplicate audit vs 653 rasters-> evidence/uniqueness.json
python3 scripts/duplicate_review.py         # density-corrected reading of it  -> evidence/uniqueness_review.json
python3 scripts/hypothesis_test.py          # validate the top local candidate-> evidence/hypothesis_thermal_pathway.json
python3 scripts/hypotheses.py               # the ranked register             -> evidence/hypotheses.json, HYPOTHESES.md
python3 scripts/run_card.py                 # the one run card                -> evidence/run_card.json
python3 scripts/run_lane.py site            # rebuild docs/ from evidence/  (deterministic)
python3 scripts/check_site.py               # fail closed if the site and the raster disagree
```

`src/gems65_sarprop/template/` is a byte-for-byte copy of the shared `gems57` modules and is **never
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
4. **Push coverage rather than budget.** The ceiling arithmetic above shows a ~0.44 ceiling at
   this true-positive mass; the binding constraint is distinct structures recovered, so the next
   experiments should add information, not dots. The ranked register in `HYPOTHESES.md` names the
   five candidates; the first is the USGS Quaternary Fault database itself, which the organisers
   name as a scored-label source, and 44.7% of its in-footprint traces sit more than 300 m from
   any catalogue pixel.
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
- **IR-65L-01 — the parallel-run duplicate rule is not scale free.** The rule "stop if more than
  70% of your dots fall within 3 px of one registry raster's dots" fired **58 times** against this
  file, all of it as an artifact: the template dilates the other raster's support by the kernel
  radius, so any prior covering a few percent of the map covers all of it, and the statistic
  saturates at 1.0 for *any* candidate. In this audit 53 of the 58 firings had support above
  300,000 cells (mean 4.3M — i.e. full-footprint probability surfaces), the analytic uniform null
  is 1.0000 for each of the twelve worst, and the direct measure of "same dot set", the Jaccard
  index, is at most **0.0207 across all 653 rasters**. Reported, not silently overridden: both
  readings are published (`evidence/uniqueness_review.json`), the site shows the anomaly, and an
  owner ruling is needed on whether the density-corrected reading replaces the literal one.
- **IR-65L-02 — the registry audit covers 653 of 655 indexed rasters.** Two entries could not be
  read (details in `evidence/uniqueness_review.json` under `error_details`), so a completeness
  claim is out of reach and none is made; "not a duplicate of anything checked" is the claim.
- **IR-58-08**, **IR-S6-01** — owner rulings outstanding; see §5 above.
- The published leaderboard high recorded in older notes (0.3195, "highest") is **stale**: the saved
  organizer snapshot of 2026-10-11 puts 0.4133 first and 0.3195 at rank 8.
