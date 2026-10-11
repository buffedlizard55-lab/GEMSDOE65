# GEMSDOE65 — selection-bias-aware PU learning (SAR) for the DOE GEMS Prize

**Competition:** DrivenData 306, DOE GEMS Prize —
<https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>
**Lane:** the catalogue as *positives selected at random given covariates*, propensity-aware
risk, dots placed where the catalogue is blind.
**Site (GitHub Pages):** <https://buffedlizard55-lab.github.io/GEMSDOE65/> —
the front page opens with a verdict banner and a one-click download;
[executive summary / how to submit](docs/executive-summary.html).

## Is the artefact OK to download and submit?

See the banner on the site front page. It is generated mechanically from
[`registry/preregistration.json`](registry/preregistration.json) applied to
[`evidence/e1_px5.json`](evidence/e1_px5.json) by
[`scripts/make_submission.py`](scripts/make_submission.py); the verdict string
(`SHIPPABLE` / `DO-NOT-SUBMIT`) is written into
[`evidence/live_run_card.json`](evidence/live_run_card.json) and rendered verbatim. No human
judgement enters the verdict, and this session spends **zero** submission slots — promotion to
a real weekly slot is a separate selector step.

<!--RESULTS-BEGIN-->
## Results (this session)

**Verdict: `DO-NOT-SUBMIT`** — primary gate failed: A1_sar did not beat B_nnpu on I1. The pre-registered ship rule
(`registry/preregistration.json`) was applied mechanically to `evidence/e1b_px5.json`
by `scripts/make_submission.py`; no human or agent judgement entered it. **Zero submission slots
were spent and nothing was uploaded.** The artefact is published for research and clearly marked;
the site banner says the same thing in one line.

**Artefact:** [`docs/downloads/gemsdoe65-gems65-sar2inv-a2-38k-20261011T220214Z-296a58fcf2a6-zeros.tif`](docs/downloads/gemsdoe65-gems65-sar2inv-a2-38k-20261011T220214Z-296a58fcf2a6-zeros.tif) · sha256 `9cd84cbe98fcc4eebfdabd497c2b69c79cc293563b91a353d45ecdffbc7e2582` ·
150,442 bytes · float32 · EPSG:32611 · 3730×3292 ·
38,000 positive pixels (value 1.0), everything else exactly 0.0 ·
**local format checks: all passed** (0 NaN,
0 inf, range [0.0, 1.0],
0 dots on mapped catalogue pixels).
**Name:** `gems65-sar2inv-a2-38k` · **Note (110 chars):** `SAR-PU, propensity anchored on 2 public fault inventories; rank P(y|x)*(1-e(x)); 38k dots, 300m NMS, 300m peel`

**I1 — hide-and-recover blocked holdout (the pre-registered primary gate)** — evaluator `gems57-pooled-hide-v2`, n = 11,321 withheld positive pixels, 20 km spatial-block paired bootstrap

| arm | HOLDOUT-DTI | 95% CI | dots | credit/dot |
|---|---:|---|---:|---:|
| `A2_sar_1me` | 0.058766 | [0.049599, 0.067893] | 38,000 | 0.0252 |
| `A1_sar` | 0.071082 | [0.060045, 0.081551] | 38,000 | 0.0305 |
| `A3_sar_em_1me` | 0.086740 | [0.075842, 0.097151] | 38,000 | 0.0373 |
| `B_nnpu` | 0.085955 | [0.074544, 0.095856] | 38,000 | 0.0369 |
| `C_distance_only` | 0.090711 | [0.077612, 0.104595] | 27,451 | 0.0472 |
| paired Δ(A1_sar − B_nnpu) | -0.014874 | [-0.023885, -0.005936] | excludes 0 | — |
| paired Δ(A1_sar − A2_sar_1me) | +0.012316 | [+0.005397, +0.019568] | excludes 0 | — |
| paired Δ(A1_sar − A3_sar_em_1me) | -0.015658 | [-0.024745, -0.006594] | excludes 0 | — |
| paired Δ(A1_sar − C_distance_only) | -0.019629 | [-0.035698, -0.002337] | excludes 0 | — |

**I1b — highest-propensity tercile only (the secondary gate)** — evaluator `gems57-pooled-hide-v2`, n = 3,107 withheld positive pixels, 20 km spatial-block paired bootstrap

| arm | HOLDOUT-DTI | 95% CI | dots | credit/dot |
|---|---:|---|---:|---:|
| `A2_sar_1me` | 0.001645 | [0.000000, 0.004063] | 38,000 | 0.0001 |
| `A1_sar` | 0.046314 | [0.030901, 0.064088] | 38,000 | 0.0035 |
| `A3_sar_em_1me` | 0.065533 | [0.047834, 0.084365] | 38,000 | 0.0060 |
| `B_nnpu` | 0.060386 | [0.038781, 0.084686] | 38,000 | 0.0052 |
| `C_distance_only` | 0.094519 | [0.070742, 0.118129] | 27,451 | 0.0142 |
| paired Δ(A1_sar − B_nnpu) | -0.014073 | [-0.036482, +0.003093] | includes 0 | — |
| paired Δ(A1_sar − A2_sar_1me) | +0.044669 | [+0.029456, +0.061553] | excludes 0 | — |
| paired Δ(A1_sar − A3_sar_em_1me) | -0.019219 | [-0.037648, -0.003571] | excludes 0 | — |
| paired Δ(A1_sar − C_distance_only) | -0.048206 | [-0.076249, -0.016518] | excludes 0 | — |

*credit/dot here divides by the full dot budget, not by the dots that fall inside the tercile, so it is a lower bound; the tercile restricts the scoring domain only.*

**I2 — mapped faults the catalogue does NOT contain (the instrument that matches the live task)** — evaluator `gems57-pooled-hide-v2`, n = 59,012 withheld positive pixels, 20 km spatial-block paired bootstrap

| arm | HOLDOUT-DTI | 95% CI | dots | credit/dot |
|---|---:|---|---:|---:|
| `A2_sar_1me` | 0.140842 | [0.132499, 0.148127] | 38,000 | 0.2068 |
| `A1_sar` | 0.126200 | [0.117299, 0.134967] | 38,000 | 0.1850 |
| `A3_sar_em_1me` | 0.103697 | [0.092933, 0.114972] | 38,000 | 0.1515 |
| `B_nnpu` | 0.101953 | [0.091793, 0.113242] | 38,000 | 0.1489 |
| `C_distance_only` | 0.021906 | [0.017568, 0.027346] | 26,890 | 0.0429 |
| paired Δ(A1_sar − B_nnpu) | +0.024246 | [+0.014802, +0.032843] | excludes 0 | — |
| paired Δ(A1_sar − A2_sar_1me) | -0.014643 | [-0.022646, -0.007147] | excludes 0 | — |
| paired Δ(A1_sar − A3_sar_em_1me) | +0.022502 | [+0.013015, +0.031173] | excludes 0 | — |
| paired Δ(A1_sar − C_distance_only) | +0.104294 | [+0.094647, +0.114261] | excludes 0 | — |


Pooled ranking AUC — I1: `A2_sar_1me` 0.5897, `A1_sar` 0.6417, `A3_sar_em_1me` 0.6660, `B_nnpu` 0.6671, `C_distance_only` 0.7670
· I2: `A2_sar_1me` 0.7145, `A1_sar` 0.6311, `A3_sar_em_1me` 0.4976, `B_nnpu` 0.5098, `C_distance_only` 0.4806.

**The gate fails on I1 and the lane wins on I2, and the reason is structural.** I1's withheld
truth is made of *catalogue* components contiguous with visible trace, and the organizer masks
known USGS/INGENIOUS fault pixels out of scoring, so I1 rewards exactly the pixels that cannot
score live. Consistently, the trivial proximity control is the best arm on I1
(0.090711) and the worst on I2 (0.021906).
Re-keying the gate is an amendment to a pre-registration after results are known: **an owner
decision, not an agent one.** The site's §0 gives the full argument.

**Propensity.** Source `anchor` (two-inventory anchor; the EM alone is the sensitivity
arm `A3_sar_em_1me`). Spearman(EM ordering, anchor ordering) on the pooled two-inventory sample =
+0.5983. Anchored e: mean 0.6329
on catalogue pixels vs 0.3789 on independent-inventory
off-catalogue fault pixels — the direction the hypothesis requires — spanning p01 0.0541 →
p99 0.9356 over the footprint. The EM alone collapsed to e ∈ [0.2808,
0.2961]: irregularity **IR-65-PROP-01**, fixed by pre-registration
amendment `GEMSDOE65-PREREG-1-A1`, with both experiments retained (`evidence/e1_px5.json`,
`evidence/e1b_px5.json`). π = 0.02322 (MEASURED lower bound: the union of both public
inventories, 119,906 px of 5,164,312); ρ = P(s=1)
from population counts; weights clipped at 10; c = 1.0.

**Emission geometry** (live field): 38,000 dots, 0 on mapped pixels,
min distance to a mapped pixel 3.0 px (300 m), median
22.67 px, 2.92 % within
300 m. The proximity control's field agrees with the shipped field on only
1.94 % of dots, so this is
not a proximity field in disguise.

**Uniqueness** (62 accessible registry rasters; inventory
incomplete, `complete_accessible_scan = False`): worst Spearman ρ
**0.0140** (limit 0.9) vs `r11_greedy_mp`;
worst Jaccard 0.0110 (limit 0.5); byte-unique
True, pixel-unique True. Worst forward
3-px dot overlap 0.9972 (limit
0.7) against the dense lattice comparator
`calib_r13lattice_00904` — **IR-65-UNIQ-01**: that rule cannot be met
by any sparse field while dense lattice comparators are in the registry (the family measured
0.9985 for its own best candidate). Flagged for the owner, not waived.

**Leakage canary** (limit AUC ≤ 0.9): worst single covariate 0.7548
(`dist_to_visible_catalogue`, the legitimate proximity control); nothing flagged.

**Catalogue identity** (MEASURED): rasterised QFaults/INGENIOUS segments cover
96.54 % of catalogue pixels at median distance
0 px (max
1 px);
3,199 components, median
12 px, 1-px-wide lines. Range-front
variant kept: `A_h50_isoline_over_5km_local_min` (160,275 isoline px, bias AUC
0.6608), byte-identical to the
stored covariate.

Full receipts: [`evidence/`](evidence/) · site:
<https://buffedlizard55-lab.github.io/GEMSDOE65/> · irregularities:
[`docs/irregularities.md`](docs/irregularities.md) · pass-3 re-check:
[`docs/research/review-pass3.md`](docs/research/review-pass3.md)
<!--RESULTS-END-->

## Read this every session

The standing brief is retained verbatim below, as instructed ("Put this prompt into the repo
readme and read it everytime we work on the project as a starting point"). It is inherited
across the GEMSDOE family of repositories; the *lane paragraph* inside it belongs to the
sibling repo `60GEMSDOE` (channel steepness / knickpoints) and is **not** this repo's lane.
This repo's lane is stated separately, immediately after.

<details open><summary><b>The standing brief, verbatim (inherited; 60GEMSDOE lane paragraph
included for provenance)</b></summary>

```text
Review the repo.

THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION.  DO NOT COPY A PREVIOUS SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION.  BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION.  IT MUST BE OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.

There should be an easy to download submission tif file as described by the prompt.  Read the entire prompt.

Tectonic-geomorphology lane: channel steepness and knickpoints, not scarp shape. Kirby and Whipple (2012) review how bedrock-channel steepness and knickpoints record spatial gradients in rock uplift, including across active normal faults. Perron and Royden's χ transform (ESPL, 2013) puts different channels on a comparable footing, and Gailleton et al. (Earth Surface Dynamics) give a reproducible knickpoint-segmentation method. Scarps degrade and bury, but channel profiles keep recording base-level steps, so this can see faults the curvature features no longer show. Extract drainage from the free 3DEP 10 m DEM (or 1 m tiles), compute χ and normalized steepness, and keep only knickpoints and steepness steps that align across several independent drainages along a common strike. First test: do channels crossing withheld segments show larger steepness steps than random lines of the same orientation? If not, stop. Map and mask the usual confounds: lithology, climate gradients, ephemeral channels and playa base levels. Output the standard validated GeoTIFF, uniqueness-checked against every earlier raster.

PARALLEL-RUN PROTOCOL — read first. This session is one of several running from this same prompt.

1. LANE. Your lane is the single method paragraph below. Stay inside it. If your raster's rank-correlation with any registry raster exceeds [0.90], or more than [70%] of your dots fall within 3 px of one registry raster's dots, you have drifted into another lane: log it as a duplicate and stop. Check this on the surface before placement AND on the final dots.

2. REUSE, DON'T REBUILD. Use the template's cached feature stack, evaluate_holdout.py and submission_writer.py. Holdout = hide-and-recover: withhold whole fault segments with a buffer, derive every catalogue-based feature only from the visible faults, mask visible faults pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared tool is wrong, fix it once in the template and report it; never keep a private fork.

3. LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator version, number of withheld positives, 95% CI) or ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never written as a score.

4. LEAKAGE CANARY. Test each feature alone on the holdout before trusting any result. AUC above [0.90] means leakage until proven otherwise.

5. RUN CARD. End with one JSON card: hypothesis; mechanism; the named non-fault process that could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output (no NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission name + note of at most 140 characters; verdict promote / negative. Negative results are deliverables.

6. BUDGET. Stop after [3] experiments or [2] hours. Do not pick submissions: promotion to a real slot is a separate selector step, within the weekly cap shown on the submission page.

The following sites should serve as a starting point for understanding how to generate TIF submissions.  These websites are researched, and tested and have generated TIF submissions.  But we need to generate high scoring submissions.

Here are the results from submissions into the competition, separated by ....:

WE NEED TO STUDY, ANALYZE, AND UNDERSTAND THE HIGHEST SCORE FROM THE GEMDOE SITE WHERE THE SUBMISSION TIF IS DOWNLOADED FROM WHICH IS THE FOLLOWING:

[https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html)

h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778

Why and how did this get the highest score and are we able to generate a submission that scores higher than 0.2778?

Answer the question using Phd level experience, knowledge, and judgement. Then use the answer to generate a unique TIF submission into the competition.  Must be unique submission unlike any within the GEMSDOE sites above.  Verify working line by line no hallucinations.

Historical repository-page leaderboard figure (not current official board):

0.3774	[https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html](https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html)

**Dated erratum (2026-10-11):** this 0.3774 value is a historical repository-page figure, not the current official public leaderboard. The manual official-page read is #1 xiaofanhu 0.4133; DARD 0.3195 is rank 9 (corrected in Round H73). See [`registry/leaderboard_snapshot_2026-10-11.json`](registry/leaderboard_snapshot_2026-10-11.json).

[The full per-repository score ledger (GEMSDOE … 62GEMSDOE), dated public-board rows, and provenance distinctions are maintained in `docs/score-ledger.csv`; the official leaderboard link https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/, and the resource links: https://github.com/drivendataorg/gems-prize-reference-solution ; https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and ; https://gbcge.org/current-projects/ingenious/ ; https://epsg.io/32611 ; https://en.wikipedia.org/wiki/Tversky_index ]

We need to quickly look at the results and results from the GEMSDOE websites above.

Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each naming: the specific layer(s) involved, the physical signature being targeted (e.g., an edge-detection or curvature transform), why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already implemented in this repo. Rank them by expected DTI improvement and implementation cost. Validate the top candidate on our spatially-blocked holdout set before touching a weekly submission slot — do not spend a submission slot on an idea that hasn't beaten the current holdout best. If a candidate can't be validated without new external data, name the specific free, official source needed and check it's obtainable before proposing the idea as viable.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

We have a good understanding of how our hypothesis, methodology, calculations, analysis are done so we should be able to figure out a way to score higher on the leaderboard using previous results and scoring that we have across the sites listed above.  We need to come up with distinct and unique strategies to score higher in this competition leaderboard.  We need to start doing heavy and deep research into the part of the project that matters the most, which is the scientific discovery of geothermal vents.  We should store all of our information and knowledge that we can gather from official verified sources.  This will serve as a starting point for other projects as well.  We need to think outside the box but still be grounded in proper scientific research, we are ultimately aiming for a top prize that many others are competing for.  So it's important to be contrarian but be smart about it.  We need to find sources of data that others are over looking or areas of the project when it comes to geothermal vents.  We need to do deep research and critical thinking and come up with new hypothesis to test.

0.3195	is the highest score right now so we need to design a new strategy, research, testing, analyzing, and generating submission system than the current website.  It should be unique, take unique approaches to generating a submission that can score higher than 0.3195.

**Dated erratum (2026-10-11):** the preceding 0.3195 statement is historical. The current manually read public leader is 0.4133 (xiaofanhu); 0.3195 (DARD) is rank 9 on the live board (re-read 2026-10-11, see Round H73). Public rows are not project scores or file attribution.

Put this prompt into the repo readme and read it everytime we work on the project as a starting point to make sure we are building what we are aiming for and have a strong base to continue building and improving on making something useful for everyday use.  It should solve the problem of having to manually check everything ourselves and having an up to date current feed.

Review the repo.

The following is taken from the Arena AI team and I think it makes a good point on building a successful project, so let's keep the Core Values and Own the Outcome as a focal point when building, developing, researching, suggesting upgrades, and implementing the work.

Our Core Values

Maximize P(Win)

“Maximize the Probability of Winning”: our decision making framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that Arena succeeds. We set aside our emotions and make tough decisions in order to maximize P(Win). “Maximize P(Win)” frees us from constraints and clarifies that we must put Arena first.

Own the Outcome

We own results end to end — not just our individual slice of the work. When problems arise and we have the means to act, we do so without waiting for permission or assignment. We treat failure and success as signals and use them to improve. At Arena, we stay accountable to the final outcome.

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.

The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

We need to focus on being able to generate a submission into the competition.

The site should be able to generate a TIF file that is required for submission.  It should be as easy as download to click a File to submit into the competition.  This needs to be in the executive summary or the very beginning of the site.  it should be obvious when you visit the site.

I tried to submit the document that i downloaded from the site but it returned this error on the submission form:

"Predicted values must be in range [0, 1]"

Also we need to give it a unique name and A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Here is the submission page when i click submit file

New submission

File to submit / No file chosen

You can submit a single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF, with your predictions. It must match the submission format's CRS, shape, and geotransform. You may wish to review the competition rules first.

Note (optional)

A short comment to help you or your team tell submissions apart later e.g. clustering with k=25

Create a executive summary subpage that explains exactly how to make a submission into the contest.

Work on the next steps from the previous sessions first.

The goal of this project is to place top of the leaderboard in this competition.  The following is the competition:

[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)

We need to create a project that can compete and place top of the leaderboard.  We need to understand the problem, collect all the data and organize it into a clean easily auditable table with official verified links for manual verification.

This is the guidelines we need to follow.[https://www.drivendata.org/competitions/306/competition-doe-gems/](https://www.drivendata.org/competitions/306/competition-doe-gems/)

Get familiar with the problem through the overview and problem description,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/). You might also want to reference additional resources available on the about page,[https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/).

Download the data from the data,[https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/), tab.

Create and train your own model. This reference solution,[https://github.com/drivendataorg/gems-prize-reference-solution](https://github.com/drivendataorg/gems-prize-reference-solution) implements a simple approach.

Use your model to generate predictions that match the submission format.

Tell me what are you limitations and what you need access to during this project.  We will need to find free publicly available sources and data from official and verified sources if we are to use 3rd party or external data.

this pdf outlines how submissions must be entered into the competition.

[https://docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf)

You must be able to do your own research, deep research, scientific literature research and organize the knowledge so that we can critically think through the problem and generate a solution through scientific and free publicly available information.  this must be done autonomously and must be constantly reviewed and improved upon.  Provide suggestions and improvements and implement them.

❌ No DrivenData auth → cannot auto-download training_features.tif, labels.tif, sample_submission.tif, 1m_DEM_links.csv from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (verified redirect to login)

See below for links from the above site.  See attached files for links from the above site.

[https://gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391)

Download competition data from [https://www.drivendata.org/competitions/306/competition-doe-gems/data/](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (requires login) to data/

See links below for competition data:

[the owner's mirrored Dropbox links: GEMS_96647.pdf; example_submission.tif; existing_faults.tif; gems-geodawn-numerical-features.tif; Digital-elevation-model-links-JSON.pdf]

Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.  The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Site creation: Create a github page for this repo that has clean ui, user friendly, simple and easy to use.  It should be organized and clean.  It should include all relevant information in an easy to read format with official verified links as sources for review.  Work line by line verify everything no hallucinations.

The single remaining blocker to training is data placement: run `bash scripts/download_competition_data.sh` on any unrestricted machine into `data/`, then `python scripts/prepare_data.py` — after that the full train→inference→validate pipeline is ready to run (GPU needed for training; metric/losses/validation all verified working here on CPU).

you need to complete the above task by yourself.  Work line by line verifying from official verified trusted sources, provide links for manual review.  There should be no manual input, work on your own to complete tasks.  Flag any irregularities for review.  No hallucinations.

Verify no hallucinations.  The goal of this project is to get a full list that follow our requirements.  No hallucinations.  Verify line by line.

Run this task through multiple passes.

Pass 1: Implement the task completely and verify the result.

Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge cases. Fix everything you find.

Pass 3: Re-check the entire implementation against the original request. Improve accuracy, reliability, completeness, and code quality. Fix any remaining issues.

Do not stop after the first pass. Each pass must build on the previous one. Before finishing, verify that the final result fully satisfies the original request.  Work line by line verify everything no hallucinations.

Go ahead and create a pull request and then merge the pull request onto the main. Make suggestions for what work still needs to be done and any limitations that is in the way of a successful project.  It should be worked on in this next session or the next session.  Work line by line verify everything no hallucinations.
```

</details>

<details open><summary><b>This repository's lane (GEMSDOE65)</b></summary>

Selection-bias-aware PU-learning lane (this repository, GEMSDOE65), as recorded in this
session's working notes. The verbatim user message was condensed by the session-memory system,
so this is a faithful transcription of the lane's requirements rather than a byte copy; every
requirement below is implemented and cited in the code and receipts.

> Treat the catalogue as positives **selected at random given covariates (SAR)**, not SCAR.
> Estimate the propensity e(x) = P(labeled | fault, x) with the EM method of Bekker & Davis
> (PMLR v94, 2018). Covariate set: local relief, slope, gravity-derived basin-fill proxy,
> LiDAR coverage, distance to the range front. Anchor its scale with exhaustively mapped
> quadrangles if a public index exists. The propensity is not uniquely identifiable from PU
> data alone, so otherwise report it as a sensitivity analysis. Train with the
> propensity-aware empirical risk of Bekker, Robberechts & Davis (arXiv:1809.03207), weights
> clipped at 10, against an nnPU baseline on identical folds. Gate: higher blocked-holdout DTI
> overall AND no loss in the highest-propensity tercile. Finish: normalize to [0,1]; float32
> EPSG:32611 100 m GeoTIFF (NaN only outside the footprint); pass validate_submission.py;
> hash/pixel-agreement check against all prior rasters; offer the download only if the gate is
> met, else log the negative result.

Deviation recorded (flagged, not silent): the artefact is written in **all-finite `zeros`
mode** — zero outside the footprint instead of NaN — because (a) the organizer's own reference
solution writes an all-finite raster with no `nodata` tag, and (b) NaN primaries are what
produced the portal rejection *"Predicted values must be in range [0, 1]"* that this lane was
asked to fix. `gems57.validate` asserts both readings.


</details>

## What is here

| path | contents |
|---|---|
| [`src/gems65/`](src/gems65/) | this lane: `covariates`, `propensity` (Bekker & Davis SAR EM), `anchor` (two-inventory propensity), `risks` (propensity-aware ERM + nnPU), `lane` (folds, arms, emission) |
| [`src/gems57/`](src/gems57/) | the shared family tools, copied **verbatim** and hash-pinned: `emit`, `evaluate_holdout`, `holdout`, `metric`, `network`, `spatial`, `submission_writer`, `uniqueness`, `validate`. Never forked; fixes go upstream and are reported |
| [`tests/`](tests/) | 21 unit tests: risk unbiasedness + analytic gradients, the retired normaliser, the retired EM initialisations, the subsample-π bug, and the formal non-identifiability / anchor-direction proofs |
| [`registry/preregistration.json`](registry/preregistration.json) | instruments, arms, gate, ship rule, budget — written **before** any holdout number existed |
| [`evidence/`](evidence/) | every measurement, each with an evidence class: `mapping_bias_two_inventory`, `catalogue_identity`, `range_front_variants`, `leakage_canary`, `fold_receipt`, `sgmc_instrument_receipt`, `e1_px5`, `live_run_card` |
| [`docs/research/hypotheses-2026-10-11.md`](docs/research/hypotheses-2026-10-11.md) | the five ranked geological hypotheses required before implementation |
| [`docs/research/why-02778-and-what-beats-it-2026-10-11.md`](docs/research/why-02778-and-what-beats-it-2026-10-11.md) | why `h33-h33-2-b2` scored 0.2778 and what beats it (copied from `60GEMSDOE` with a provenance header, plus this lane's addition) |
| [`scripts/`](scripts/) | `build_covariates`, `run_lane` (`bias`/`canary`/`e1`/`e2`), `diagnose_irregularities`, `make_submission`, `build_site` |

## Reproduce

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_covariates.py        # covariate cache (~3 min)
.venv/bin/python -m pytest tests -q                 # 21 passed
.venv/bin/python scripts/run_lane.py bias           # two-inventory mapping bias
.venv/bin/python scripts/run_lane.py canary         # leakage canary (limit AUC 0.90)
.venv/bin/python scripts/run_lane.py e1             # the gated experiment (5 covariates)
.venv/bin/python scripts/diagnose_irregularities.py # catalogue identity + range-front variants
.venv/bin/python scripts/make_submission.py         # live fit, emit, write, validate, certify
.venv/bin/python scripts/build_site.py              # regenerate the GitHub Pages site
```

Heavy inputs (the 418 MB official feature stack, the covariate cache, registry rasters) live in
`.cache/` and `data/bridge/` and are git-ignored: the patchset budget is ~128 MB / 10,000 files.
`scripts/_bootstrap.py` reassembles and sha-verifies the bridge if it is missing.

## Evidence classes used on every number

| tag | meaning |
|---|---|
| `HOLDOUT-DTI` | local spatially blocked holdout, shared evaluator version, n withheld positives, 95% CI from a 20 km block paired bootstrap. **Never a leaderboard score** |
| `ORGANIZER-CONFIRMED` | copied from a submission-page receipt. **This repo has none** |
| `MEASURED` | deterministic measurement of local hash-pinned data (counts, distances, AUCs) |
| `MODEL` | arithmetic on the above; not a measurement |
| `OWNER-REPORT` | a score reported by the repository owner without an organizer receipt (e.g. 0.2778) |

## Limitations and the access that would remove them

* **No outbound access to the organizer or to USGS.** From this sandbox `drivendata.org`,
  `docs.nlr.gov` (rules PDF), the five Dropbox data mirrors, `gdr.openei.org`, `usgs.gov`,
  `gbcge.org` and `raw.githubusercontent.com` all return HTTP 000. Official statements are
  quoted from the family's line-by-line verification record
  (`60GEMSDOE/docs/research/verification-2026-10-04.md`) with links for manual review.
  Needed: a host with outbound HTTPS to those domains, or a mirrored rules PDF.
* **The holdout may not represent the live target.** I1 rewards proximity to visible traces
  (withheld truth is contiguous with visible trace); the live board does not — the family
  measured that deleting dots 1–2 px from the catalogue *raised* the live score twice
  (+0.0108, +0.0070, owner-report). Both instruments are reported; neither is a projection.
* **The propensity anchor assumes the reference inventory is unbiased in x.** State geologic
  maps are bedrock-exposure maps; if they under-sample buried basin faults, the anchor
  over-corrects toward exposed ground. This is the named mimicking process (inventory vintage
  and compiler-rule confounding), and it is the largest single risk in the lane.
* **The range front is a proxy** (50 m isoline of height above a 5 km local minimum), not a
  mapped front. A real front needs raw 3DEP 10 m/1 m tiles — unreachable here.
* **LiDAR layer provenance:** quantised scarp descriptors derived in a sibling repo from public
  3DEP tiles — 10 failed tiles of 716, a 1–2 m datum offset, and they are terrain descriptors,
  not fault detections. Tagged `PUBLIC-REPOSITORY-DERIVATIVE`, not organizer-provided.
* **Uniqueness inventory is incomplete.** Only sibling public-repository rasters are
  accessible, and the literal rule (≤70 % of dots within 3 px of *any* registry raster) is
  unmeetable for sparse fields because dense lattice comparators cover nearly the whole
  footprint (the family measured 0.9985). Both the literal and the like-for-like readings are
  reported; the rule is flagged for the owner, never silently waived.

## Three-pass review

1. **Implement/verify** — covariate build, risk functionals with Monte-Carlo and analytic
   gradient checks, EM, anchor, folds, emission, artefact writer, site.
2. **Review/fix** — four real bugs found and fixed in this lane's own code and one in the
   inherited usage pattern: (i) the SAR normaliser must use ρ = P(s=1) on *population* counts,
   not π·E[e] (biased when g and e correlate — guarded by
   `test_wrong_normaliser_pi_ebar_is_detected`); (ii) an unweighted unlabeled subsample
   inflated π to 0.867 against a truth of ≈0.03 (guarded by `tests/test_propensity_subsample.py`);
   (iii) two EM initialisations converge to the *mirrored* factorisation — both retired and
   replaced by the SCAR-identity start plus the external anchor; (iv) per-fold emissions OR-ed
   across folds multiplied scored mass by n_folds — replaced by out-of-fold score fields and one
   global emission per arm; (v) the peel used `d > peel_px` where the champion geometry is
   `d >= 3` px — corrected.
3. **Re-check against the request** — see [`docs/research/review-pass3.md`](docs/research/review-pass3.md).

## Core values applied

**Maximize P(Win):** the scarce resource is a weekly submission slot, so nothing is promoted
without a pre-registered gate, a control arm, and a leakage canary; the lane deliberately
spends zero slots and reports a verdict instead of a hope.
**Own the Outcome:** negative results, non-identifiability proofs, retired initialisations and
an unmeetable uniqueness rule are all published as deliverables rather than hidden.

## Suggestions for the next session (ranked by expected value per hour)

1. **Fix the instrument before fixing the model.** I1 (hide-and-recover) rewards dots that hug
   visible traces, because withheld truth is contiguous with visible trace; the live board does
   the opposite (the family measured that deleting dots 1–2 px from the catalogue *raised* the
   live score twice, +0.0108 and +0.0070, owner-report). Build an **I3**: hold out whole
   *state-map* segments with the catalogue fully masked, so the truth population is
   "mapped faults the catalogue does not contain" everywhere, not just beyond 300 m. Until the
   instrument agrees in sign with the live target, no gate result can be trusted in either
   direction.
2. **A stronger ranker.** The five pinned covariates give pooled AUC 0.667 on I1 and ≈0.50 on
   I2; the official 19-band stack is right there and unused by this lane. Gradient boosting over
   all 19 bands (with the propensity still anchored on two inventories) is the cheapest large
   gain available, and it is inside the lane: the lane constrains the *risk functional and the
   selection model*, not the feature set.
3. **H65-4 en-echelon stepover / relay-ramp gaps** (`docs/research/hypotheses-2026-10-11.md`):
   the catalogue is 3,199 fragmented 1-px traces with median 12 px, so unmapped linkage geometry
   between segment tips is abundant and no sibling lane has scored it. Narrow (a few thousand
   candidate pixels) but it can be *combined* with the propensity ranking instead of replacing it.
4. **H65-2 LiDAR-conditional emission.** LiDAR covers 75.37 % of the footprint; the final-round
   truth is an expert panel's map. Spend budget preferentially where the panel will have 1 m
   LiDAR, and require two independent lines of evidence where it does not.
5. **Get one organizer receipt.** Everything in this repo is HOLDOUT-DTI or MEASURED. One
   cleared submission, with its score, timestamp, file sha256 and remaining slot count copied
   into `evidence/`, converts the family's ladder arithmetic (credit/dot 0.135 → 0.150 ≈ 0.30)
   from owner-report into evidence. That is the selector step, not this lane.
6. **Full re-train sensitivity over π and c.** This lane swept the reference-inventory
   completeness `c` at the ranking level and measured π from the two-inventory union
   (0.02322, a lower bound); re-training per (π, c) pair is 8 more fits and would show whether
   the SAR risk or only the ranking carries the effect.
7. **Resolve IR-65-UNIQ-01 with the owner.** The literal 70 %-within-3-px rule cannot be met by
   any sparse field while dense lattice comparators are in the registry (the family measured
   0.9985). That needs a written amendment to the protocol, not a per-session waiver.
8. **Fix IR-65-COV-01 upstream** (`mean_on_catalogue` = NaN for two covariates in the build
   receipt) and push the `gems65` normaliser/subsample fixes into the shared template if any
   sibling lane adopts SAR — the standing instruction is to fix shared tools once, in the
   template, and report it.
9. **Port the anchor.** The two-inventory propensity anchor is not specific to faults: any PU
   competition with two overlapping public inventories of the same objects can identify the
   selection direction this way. It is worth extracting into the shared template with its tests.

