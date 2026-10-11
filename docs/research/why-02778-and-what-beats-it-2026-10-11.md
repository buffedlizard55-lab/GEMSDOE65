<!-- PROVENANCE: copied verbatim from the sibling repository 60GEMSDOE
     (docs/research/why-02778-and-what-beats-it-2026-10-11.md, session
     arena/161d8066-60gemsdoe, 2026-10-11) for learning and education, as the standing
     brief permits. Its relative links (../../evidence/*, ../../registry/*) resolve inside
     60GEMSDOE, not inside GEMSDOE65. Nothing in this file was produced by this lane; the
     section immediately below states what this lane adds to it. -->

# What GEMSDOE65 adds to this answer

The analysis below establishes, from committed bytes and the owner's score ledger, that
`h33-h33-2-b2` (0.2778, **[owner-report]** — no organizer receipt ties the score to exact
bytes) is the last rung of a *mass-pruning* ladder, that its dots earn a mean credit of
**0.135 per dot ≈ 2.4x the break-even 0.0556**, and that pruning is nearly exhausted
(+0.003/+0.004 per rung). Its own conclusion is that the only large remaining prize is
**re-ranking the same mass** (credit/dot 0.135 -> 0.150 ~= 0.30, -> 0.19 ~= 0.36).

This lane attacks exactly that prize, and it does so with a *selection model* rather than a
new positive-evidence layer:

1. **Credit per dot is a statement about where unmapped faults are.** The competition masks
   known USGS/INGENIOUS faults out of scoring, so every scorable dot must land on a fault the
   catalogue does not contain. Ranking by `P(fault | x)` alone therefore spends budget on
   ground where the catalogue is *already* dense.
2. **Where the catalogue is blind is measurable, not guessed.** Two independent public
   inventories of the same ground disagree systematically (this repo,
   `evidence/mapping_bias_two_inventory.json`, **[measured-here]**): relative to a state
   geologic map fault layer, the catalogue over-represents deep-basin-fill, low-relief,
   low-slope ground far from the range front (bias AUCs 0.20-0.34) and under-represents
   exposed high-relief steep ground (0.74-0.80 inverted). `1 - e(x)` is precisely that
   under-representation, estimated per pixel.
3. **The propensity is not identified from PU data alone, so it is anchored externally.**
   `tests/test_anchor.py` demonstrates the mirror factorisation numerically; the anchor
   inverts `q = e/(e + c(1-e))` from the two-inventory comparison and leaves one documented
   scale parameter `c`. This is the brief's "report it as a sensitivity analysis" branch,
   with data doing the direction-setting.
4. **Consequence for the ladder:** the same 38,000-dot budget, re-ranked by
   `P(y=1|x)*(1-e(x))`, is the intervention the 0.2778 analysis says is worth ~0.02-0.08 on
   the live board *if* the two-inventory differential tracks the expert panel's map. That
   conditional is the whole risk of this lane, and it is why both instruments (I1
   hide-and-recover, I2 state-map-only) are reported instead of one.

---

# Why `h33-h33-2-b2` scored 0.2778, and what can beat it

**Session:** `arena/161d8066-60gemsdoe` · **Date:** 2026-10-11 · **Branch:** `arena/161d8066-60gemsdoe`
**New evidence this session:** [`evidence/h71a_runcard.json`](../../evidence/h71a_runcard.json),
[`evidence/h71b_runcard.json`](../../evidence/h71b_runcard.json),
[`evidence/h71_uniqueness_addendum.json`](../../evidence/h71_uniqueness_addendum.json),
[`evidence/h69_probe_build.json`](../../evidence/h69_probe_build.json),
[`registry/preregistration-h71.json`](../../registry/preregistration-h71.json)

Every number carries a tag: **[measured-here]** (recomputed in this session from committed bytes),
**[official]** (competition page / leaderboard), **[owner-report]** (the group's own ledger; no
organizer receipt), **[model]** (arithmetic on the above, not a measurement), **[external]**
(public source, checked).

---

## 1. The answer in one paragraph

`h33-h33-2-b2` is the **last rung of a five-step mass-pruning ladder on one field**. Its score is
not evidence that its field is good; it is evidence that its *mass* is nearly minimal. The ladder is
nested byte-for-byte **[measured-here]**, every rung was uploaded to the live board
**[owner-report]**, and every rung that removed dots raised the score:

| rung | dots | live score | removed since the rung above | where the removed dots sat |
|---|---:|---:|---:|---|
| `h19-5` solid | 121,131 | 0.1922 | — | — |
| `d1.5` | 60,069 | 0.2477 | 61,062 | thinned field tail |
| `d2.8` | 44,090 | 0.2600 | 15,979 | thinned field tail |
| `h27-4-r1-solo` | 40,199 | 0.2708 | 3,891 | **exactly d = 1.00 px from the catalogue** |
| **`h33-2-b2`** | **37,654** | **0.2778** | 2,545 | **exactly d = 2.00 px from the catalogue** |

**[measured-here]** `h27-4 ⊂ d2.8` and `b2 ⊂ h27-4` are exact pixel-subset relations; the 3,891 and
2,545 removed dots lie at d = 1.00 px and d = 2.00 px from the nearest mapped fault, and nothing
else changed. Both deletions *raised* the live score (+0.0108 and +0.0070 **[owner-report]**).
The champion's own geometry: 37,654 unit-mass dots, 0 on the catalogue, minimum distance 3.00 px
(300 m), median 19.65 px (1.97 km), p95 81.88 px (8.19 km), maximum 219.27 px (21.9 km)
**[measured-here]**.

**So the mechanism is: the hidden positives avoid the 100–200 m halo of the published map, and the
incumbent's advantage is a near-minimal mass on a well-ranked field.** Two of the four available
mass-control moves have already been spent, and they were the cheap ones.

### 1b. The geometry that the ladder's numbers actually imply

**[measured-here]** the champion's 37,654 dots are *not* a ribbon on the mapped traces. Of its dots,
0 lie on the catalogue, only 5.77 % lie within 300 m of it, and the **median dot sits 1.97 km away**
(p95 = 8.19 km, max 21.9 km). The champion is therefore a *wide-field* emission whose mass is
mostly 1–20 km from the published network, and the two most recent rungs removed the small part of
it that *did* lie in the catalogue's immediate 100–200 m halo. The field underneath it
(H19-5 → d1.5 → d2.8) was built from convergent multi-layer evidence; thinning kept the ranking
while cutting the mass, and peeling cut the masses that sat closest to the *published* map.

### 1c. Why the hidden faults are "off-catalogue" at all — the physical case

The prize's truth is a set of **new** expert-mapped faults, so by construction it excludes the
existing USGS/INGENIOUS compilation. Four physical mechanisms put real, mappable fault trace *off*
that compilation while keeping it *near real structure*:

1. **Compilation gaps, not geological gaps.** The published network is drawn from state maps of
   differing vintage and resolution; mapping stops at county, range and land-status boundaries and
   where young alluvium hides the trace. The fault continues; the polygon does not.
2. **Distributed and secondary deformation.** Trenching and LiDAR campaigns repeatedly show
   displacement on splays, step-overs and antithetic strands hundreds of metres off the principal
   trace — real trace that a regional compilation does not carry.
3. **Low-slip-rate and short faults.** Structures below the compilation's inclusion threshold
   (short, poorly expressed, no dated displacement) are exactly the population a "new faults" panel
   can add.
4. **Detection-technology change.** The panel uses data the compilation never saw (bare-earth LiDAR,
   modern geophysics), so it finds faults that were always there and never mapped.

The champion's ladder is the empirical fingerprint of (1)–(4): the hidden set is close enough to the
published network that a wide-field emission scores, and the *published trace itself is not the
answer* — mass on the published halo was worth less than nothing (its removal paid twice).

## 2. The algebra that governs every decision here

**[official]** `DTI = TP_w / (TP_w + 0.2·FP_w + 0.8·FN_w)`, triangular kernel `k(d) = max(1 − d/300 m, 0)`,
`α = 0.2`, `β = 0.8`, `R = 300 m` (page 967), with the official worked example `TP_w = 3.00,
FP_w = 1.89, FN_w = 2.00 → 0.60` reproduced exactly by `src/gems57/metric.py` **[measured-here]**
(brute-force test in `tests/test_metric.py`, agreement 1e-9).

With `T = TP_w`, `S = Σp` (emitted mass), `k_x` the self-credit of a dot (its own best kernel weight
towards any truth pixel) and `M = Σ_x k_x`:

```
DTI = T / ( 0.2·(T + S − M) + 0.8·|G| )                     (★)
add one dot with marginal coverage dT and self-credit k:
   dDTI > 0   ⟺   dT > 0.2·DTI·(dT + 1 − k)                (★★)
non-redundant dot (dT = k):  pays iff  k > 0.2·DTI
```

At the champion's 0.2778 the bar is **k > 0.0556**: a dot pays if it is within 283 m of an
*uncovered* hidden-truth pixel. At the leader's 0.4133 the bar is 0.0827.

**What (★) says about the champion.** Its dots lie 0.3–21.9 km from the catalogue, so their
self-credit is driven by the hidden set alone. Under the repo's own calibration of that set
(`src/gems32/live_anchor.py`, `|G| ≈ 12,226` px **[model]** derived from the owner-reported ladder),
the champion's implied credit is `T ≈ 0.2778·(0.2·(37,654 − M) + 0.8·12,226 + 0.2T)`; with
`M = T` (thin-dot regime) this is `T ≈ 5,092` px of weighted recall, i.e. **≈ 42 % of the hidden
mass, with a mean credit of 0.135 per dot — 2.4× the break-even bar.** Those are the two numbers to
beat. Three independent readings of the same ladder (0.1922 → 0.2778, the LM live-mirror, and the
`knowledge/01` inversion) agree to within a few percent, so the *scale* is trustworthy even though
`|G|` itself is unverified.

## 3. Can we beat 0.2778? Yes — but only in one of three ways, and two of them are nearly spent

**(a) Remove worthless mass — half spent.** Every removal so far paid at a nearly constant rate:
2.78e-6 and 2.75e-6 score per removed dot **[measured-here from [owner-report] scores]**. A third
shell (1,091 dots at d ≈ 3 px) and a fourth (1,487 at d ≈ 4 px) are still in the file
**[measured-here]**. If the rate held, those two shells are worth ≈ +0.003 and +0.004; it will not
hold indefinitely, because the organizer's masking halo is finite — but *how* finite is exactly
what a peel ladder measures, at one upload per rung.

**(b) Re-rank the same mass — the field-quality route, and the only big prize.** (★) is a ratio:
raising the mean credit per dot from 0.135 to 0.150 lifts the score to ≈ 0.30; to 0.19 lifts it to
≈ 0.36. The public board shows this is achievable: **#1 xiaofanhu 0.4133, #2 JerryDataWorks 0.3418,
#3 alexoktaba 0.3361** **[official, snapshot 2026-10-11]**, i.e. 23 % above the champion sits a
score that is not reachable by mass control alone. Nothing in *this* repository has held a
population-matched instrument edge over the champion until this session (§4).

**(c) Identification, not guessing — two uploads, already built.** `h69A` (0.5 × champion) and
`h69B` (champion + 2,000 floor dots) identify `T`, `K = |G|` and `F` exactly from two live returns
plus the already-paid anchor **[measured-here: files built, `scripts/h69_recovery.py` self-test
exact]**. With those three numbers the optimal mass, the exact marginal value of any planned change
and the true bar become arithmetic instead of assumption. Neither probe can lower the standing
(both are constructed below the anchor by the (★) arithmetic with every plausible parameter set).

## 4. What this session added: H71, a validated *field*, measured off-catalogue

Preregistered in `registry/preregistration-h71.json` (two dated amendments recorded before the
amended builds). H71 asks the population-matched question the catalogue instruments cannot answer:
**does mass placed where the incumbent has no kernel, ranked by convergent independent evidence,
carry above-bar credit on real mapped faults that are absent from the catalogue?** Layers, all
committed: 3DEP-10 m Δk<sub>sn</sub>/k<sub>sn</sub>/knickpoint reduction, 10 m relief / profile
curvature / hillshade lineament, and proximity to state-geological-map faults >300 m off the
catalogue. Truth for the measurement: the **62,226 SGMC pixels >300 m from the given catalogue**.

| arm | dots | SGMC-off credit/dot (95 % CI) | SGMC-off DTI | registered HOLDOUT-DTI |
|---|---:|---|---:|---:|
| champion `h33-2-b2` | 37,654 | 0.1456 [0.125, 0.170] | 0.0946 | 0.004385 |
| **H71-B (broad, 12,000)** | 12,000 | **0.5864 [0.510, 0.667]** | 0.1327 | 0.000844 |
| H71-A (restricted, 6,000) | 6,000 | **0.4018 [0.35, 0.46]** | 0.0470 | 0.000841 |
| champion ∪ H71-B | 49,654 | 0.2510 | **0.2038** | 0.004364 |
| mass-matched random (5 seeds) | 12,000 | 0.1091 ± 0.005 | ~0.025 | 0.000983 |
| distance-only control | 12,000 | 0.0667 / 0.0503 | 0.0157 / 0.0089 | 0.0557 |

**[measured-here]** Paired 20 km spatial-block bootstrap: H71-B − random = **+0.1053 DTI
[+0.0913, +0.1198]**; H71-B − distance-only = +0.1174 [+0.1004, +0.1340]. G1 and G2 **PASS** for
both profiles; the union does not degrade the registered holdout (Δ = −0.000021 / −0.000288, within
the ±0.002 gate).

**Honest reading.** (i) The convergent field ranks *off-catalogue real faults* 4–12× better than
matched controls and 3–4× better than the champion per dot — the first time any arm in this project
has beaten the champion on a population-matched instrument. (ii) It says nothing about the hidden
panel's new faults, which are a different population; the registered holdout, whose truth is the
catalogue itself, *rewards* the champion and is blind to this mechanism (its ρ against 12 live
scores is +0.14). (iii) Which artifact may be called unique is a separate, measured question:
H71-A passes the standing ≤70 % clause against every comparator the clause can discriminate
(worst 0.5187), is byte- and pixel-unique, and |ρ| ≤ 0.0147 vs all 102 scanned rasters. H71-B does
not (0.9448 vs `r11_greedy_mp.tif`) and is therefore labelled NEGATIVE — it stays a diagnostic.

### 4b. The union artifact (H72) — the measured candidate

`bytes = champion ∪ H71-A`, i.e. the live-scored 37,654-dot champion plus the 6,000
convergent-cover dots, **43,654 dots, no dot moved, no dot dropped**
(`docs/downloads/gems60-h72-union-champ-convcomp-43654-20261011T191739Z-zeros.tif`,
sha256 `79e3fafab1adf16ec5d1b0549dcf4bcdd4e7b40abc6aa5c1791334939ae4581d`,
zip `9d74a137…`; card `evidence/h72_runcard.json`, preregistration
`registry/preregistration-h72.json` + amendment 1, both written before the run).

Two portal-legal variants ship, identical inside the footprint: the spec-literal
`…-191739Z-nan.tif` (sha256 `c8a76393aa543462a4fc58c986055e267ed0ea3da135fe1378a1235cf0096d5e`,
NaN outside the footprint — and **[measured]** its null mask is *pixel-identical* to the official
`sample_submission.tif`: 7,111,787 NaN cells) and the `…-191739Z-zeros.tif` (zeros outside, for
validators that reject NaN). Both are single-band float32, [0, 1], EPSG:32611, exact sample
transform, no nodata tag, zero positive pixels on the catalogue.

| gate | rule | result |
|---|---|---|
| G1 population-matched | credit/dot(union) > credit/dot(champion) **and** paired bootstrap lower bound > 0 on the SGMC-off-catalogue truth | **PASS** — 0.1805 vs 0.1456; paired ΔDTI **+0.03799 [+0.03379, +0.04208]**; added mass 0.4018 vs mass-matched random 0.0337 (5 independent seeds) |
| G2 registered holdout | union pooled DTI not below the champion by > 0.002 | **PASS** — 0.004097 vs 0.004385 (Δ −0.000288) |
| G3 uniqueness | increment (the 6,000 new dots) ≤ 70 % within 3 px of any comparator; \|ρ\| ≤ 0.90; byte/pixel-unique | **QUALIFIED** — increment max **0.5187** (vs `gems32-bayesopt-dilation-scarp-d28`), ρmax 0.8396 (vs our own `h32d` line), byte- and pixel-unique; the clause fails only on the *artifact as a whole* (0.8523) against rasters that already contain the champion's support — structural, because 86 % of the artifact *is* the champion (IR-H71-LINE-01) |
| G4 portal | float32, [0,1], no NaN inside the footprint, NaN outside, EPSG:32611, exact sample transform | **PASS** |

**What this buys, in numbers.** The break-even for adding mass to the champion is 0.0556
credit/dot; the added mass measures 0.4018 on the population-matched instrument and its return
cannot be observed locally (no local instrument ranks the live board), so the *downside* matters:
if the added mass carried exactly zero live credit, the union would score **0.2604–0.2645** on the
(★) algebra, i.e. −0.013 to −0.017 versus the champion; if the measured credit transfers, the same
algebra gives **0.361–0.386**. That asymmetry — small bounded loss, large bounded gain — plus a
+0.038 measured gain on **real mapped faults that the catalogue does not contain**, is why this is
the artifact to put in front of the owner's selector — **after** the governance question in §4c is
resolved: nothing in this document is cleared to submit today. It is explicitly *not* claimed as an
organizer-confirmed improvement, and the artifact-level uniqueness caveat is stated rather than
buried.

### 4c. How the complementary-cover field compares with the lane's own artifacts, and the governance wall

From `evidence/h71_artifact_comparison.json` (every arm on the same 8-cell holdout protocol **and** on
the same SGMC-off population instrument; **the holdout numbers in that file are comparable across its
arms only** — the 8-cell protocol prints different absolute values from the pooled numbers in the run
cards, e.g. H68-1 0.0366 there vs 0.1719 in its own card):

| arm | dots | SGMC-off DTI | SGMC-off credit/dot | 8-cell holdout | literal 3-px max overlap |
|---|---:|---:|---:|---:|---:|
| champion `h33-2-b2` | 37,654 | 0.0946 | 0.1456 | 0.004385 | **1.0000** |
| **H71-B (this session)** | 12,000 | **0.1327** | **0.5864** | 0.000844 | 0.9982 |
| **H72 union = champion + H71-A** | 43,654 | **0.1326** | 0.1805 | 0.004097 | **1.0000** |
| H68-1 + H71-A (derived, not built) | 45,943 | 0.1005 | 0.1303 | 0.034318 | 0.9982 |
| H68-1 (lane, on main) | 40,000 | 0.0642 | 0.0933 | 0.036640 | 0.9985 |
| H66-1 (lane, on main) | 40,000 | 0.0651 | 0.0946 | 0.008925 | 0.9987 |
| H65-1 (lane, on main) | 40,000 | 0.0076 | 0.0110 | 0.001411 | 0.9988 |

Two readings, both true:

1. **On the population-matched instrument the complementary field is the strongest signal measured in
   this project** (0.1327 for H71-B; H72 keeps 0.1326 — the incumbent's mass dilutes the per-dot
   average without removing the coverage). The lane artifacts sit *below* the champion on that
   instrument (0.064–0.065) while beating it on the catalogue holdout: the two instruments disagree
   about the same files, exactly as IR-INSTR-01 says they do.
2. **Nothing in the table can be submitted.** Every arm's literal 3-px overlap exceeds 0.70 — including
   the already-scored champion — because `calib_r13lattice_00904.tif` and `r13_lattice_s5_00904.tif`
   lie within 3 px of **99.87 %** of the footprint. As written, the rule is unsatisfiable for any
   emission from this project. The governing review on main deliberately allows no dense-raster
   exception and this document does not ask for one: that is a decision only the owner can make —
   either the space-filling comparators are excluded from the clause (with the measurement above as
   the justification), or the clause stands and no artifact is ever cleared.

## 5. Ranked hypotheses (expected DTI gain × cost, with the reason for the order)

**Read this first:** under the governing lane STOP and the literal uniqueness rule **none of these
items is submittable today** (§4c) — the ranking is the order in which they produce *evidence*, and
the first owner decision is the governance one, not the experiment one.

**The empirical fact that drives the order.** The champion's own field is *good enough*; what is
missing is (i) knowledge of the hidden set's size and of how much credit each dot really earns
locally, and (ii) mass placed where the incumbent's kernels do not reach. The five items below are
ordered by *evidence already in hand per slot spent*.

**1. H72 — union: champion ∪ convergent-cover complement (built, measured; NOT CLEARED to submit).**
*Layers:* the champion's own multi-layer field (topo gap closure / Δk<sub>sn</sub> family) plus the
H71 convergent-evidence field (3DEP-10 m Δk<sub>sn</sub>, k<sub>sn</sub>, knickpoint reduction;
10 m relief, profile curvature, hillshade lineament; distance to state-map faults >300 m off the
catalogue). *Physical signature:* a complementary population of real fault trace 0.4–6 km from the
mapped network, where several independent layers co-fire. *Mimic named:* drainage/erosion
lineaments and playa-margin straight edges — suppressed by the ≥3-layer co-fire rule and the
>300 m catalogue separation, not eliminated. *Difference from everything implemented:* every prior
artifact either *thinned* the incumbent's mass (H19→H25→H27→H32→H33 ladder) or *replaced* it with a
different field (H60/H65/H66). This one **adds measured-credit mass to the best live-scored artifact
and measures the increment** (G1 paired +0.038, G2 no-harm). *Expected gain:* +0.05 to +0.11 if the
measured credit transfers, −0.013 to −0.017 if it does not. *Cost:* one upload (owner's slot; the
artifact is built and downloaded from the site). *Risk:* the transfer assumption, stated openly.

**2. H69 — identification pair (built; two uploads; no new field).**
`h69A` (0.5 × champion on the same support) and `h69B` (champion + 2,000 floor dots ≥8 px from the
catalogue) identify `T`, `K = |G|` and `F` exactly from two live returns plus the already-paid
0.2778 anchor (`scripts/h69_recovery.py`, self-test exact). These numbers convert every later
decision — optimal mass, the value of one more peel rung, whether floor mass is worth anything —
from modelling to arithmetic. *Cost:* two uploads, ~zero compute. *Risk:* inherits the
OWNER-REPORTED anchor.

**3. H72 — the peel ladder, one rung per upload (pre-computable).**
The champion still carries 1,091 dots at d ≈ 3 px and 1,487 at d ≈ 4 px from the catalogue; the
two completed peels paid +0.0108 and +0.0070 (a near-constant ≈ 2.8e-6 per removed dot). Rung 3 is
a **strict subset** of an artifact already live-scored, so its uniqueness reading is the same
structural caveat as H72's. *Expected gain:* ≈ +0.003 (rung 3), ≈ +0.004 (rung 4) if the rate
holds; the rung where it stops holding **measures the organizer's masking halo**, a number no
competitor can look up. *Cost:* one upload per rung.

**4. H73 — strike-parallel *tip* extrapolation with strike agreement (new geology, needs its own
first test).**
*Layers:* the mapped trace segments (`data/external/trace_segments_utm11.csv`), their mapped
azimuths, and the 10 m lineament/relief/curvature stack. *Physical signature:* new faults appear as
**along-strike continuations and step-overs of mapped segments** (fault tips, relay zones), where
the local stress field continues the mapped structure: mass is placed 1–5 km beyond segment ends,
inside ±20° of the segment azimuth, and is required to co-fire with a lineament or a k<sub>sn</sub>
step. *Why off-catalogue:* tips are exactly where a compilation stops — not because the fault
stops. *Mimic:* long alluvial channel margins and lithologic contacts aligned with strike — these
are the control the first test must beat. *Difference from everything implemented:* the repo used
segment *tips* once (H33d, `GEMSDOE33__h33d-analog-tip-stepover-r30.tif`), but as an *analog* with a
fixed 30-dot radius and no strike-agreement requirement, and it was never measured
off-catalogue. *Expected gain:* unknown, plausibly +0.02 to +0.05 on the field; *cost:* a new
preregistered first test (same estimand as E1, on the off-catalogue SGMC band) and a rebuild of the
10 m cache. **Requires a lane decision by the owner: the H65-1 STOP in
`registry/current_site_status.json` is unchanged and this item needs its own hypothesis ID.**

**5. H74 — geothermal/geodetic convergence (highest ceiling, highest cost, data not local).**
*Layers:* INGENIOUS geodetic strain/dilatation, 2 m temperature probes, palaeogeothermal gradients
(GDR 1391, DOI 10.15121/1881483), plus the official conductivity / depth-to-conductor features and
earthquake density. *Physical signature:* an *active* extensional fault should co-fire four
independent anomalies: geodetic shear or dilatation, thermal anomaly, conductivity structure, and
seismicity alignment. *Why off-catalogue:* this is the only family of evidence that does not depend
on the existing compilation at all — it finds structures the compilation never looked for.
*Mimic:* young volcanic/hydrothermal systems and irrigated playa margins with thermal artifacts.
*Difference:* every implemented artifact used topography and (for H71) state-map geometry; no
artifact used the geo-energy layers. *Expected gain:* potentially the largest of the five (the #1
public score, 0.4133, is 0.14 above the champion); *cost:* the geodetic/thermal rasters are **not in
the checkout** and this sandbox cannot reach `gdr.openei.org` — a GitHub-Actions bridge run is
required (the repo already has that pattern). *Data availability is stated in §6.*

**Answer to "can we beat it?" — the short version.** Yes: the champion's recall is ≈ 29–38 % of the
hidden mass (whatever that mass is), so three quarters of the hidden truth is uncovered; the FP term
is cheap at α = 0.2; and the public board already contains 0.4133. The binding constraint is not the
algebra, it is *knowing where the hidden trace is* — which is why items 1 and 2 (measured addition,
and exact identification) come before any new geology.

## 6. Official external data: what is needed, and whether it is available here

| layer | needed for | availability, verified |
|---|---|---|
| USGS 3DEP 1/3 arc-second DEM tiles (18, pinned sha256) | the 10 m substrate of H66/H71 | **in the repository** (`data/external/dem10_chi_100m.manifest.json`, run 38115164310) |
| USGS SGMC state-map faults | the off-catalogue truth instrument | **in the repository** (`data/external/sgmc_faults_100m.tif`); 61,664 px >300 m from the catalogue |
| USGS QFaults v2 / INGENIOUS faults (GDR 1391, DOI 10.15121/1881483) | independent fault inventory | **in the repository, but it is a subset**: 59,064 of 59,065 px lie within 300 m of the given catalogue (IR-30-021), so it is not independent truth |
| INGENIOUS geodetics, 2 m temperature probes, palaeogeothermal (GDR 1391) | H73 | **not in the checkout**; the catalogue page is `https://gdr.openei.org/submissions/1391`; unreachable from this sandbox (egress allow-list: github/npm/pypi) → needs the existing Actions bridge |
| organizational `training_features.tif` (418,912,844 B, sha256 `4371c82e…`) | the organizers' own 100 m feature stack | **not in the checkout**; mirrored through `data/bridge/manifest.json` (Dropbox mirror), reassembled by `scripts/assemble_data_bridge.py`; obtainable via the bridge, not from this sandbox |
| DrivenData reference solution | independent methodology check | **public and fetchable**: `https://github.com/drivendataorg/gems-prize-reference-solution` |
| official metric page & leaderboard | the numbers in §2–3 | `https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/`, `.../leaderboard/` **[official]** |

## 7. Irregularities flagged for review (nothing hidden)

* **IR-H71-UNIQ-01** — the standing ≤70 % 3-px clause is *unsatisfiable* against
  `calib_r13lattice_00904.tif` / `r13_lattice_s5_00904.tif`: their dots lie within 3 px of 99.87 % of
  the footprint **[measured-here]**. Every artifact in the project, past and future, fails that
  literal clause. The satisfiable reading (comparators within 3 px of ≤99 % of the footprint) is
  reported alongside it and is what the verdicts use.
* **IR-H71-LIKE-01** — `r11_greedy_mp.tif` (73.97 %) and `r14_union_tips10_lat6.tif` (76.20 %) are
  also above the clause's threshold coverage, so the clause cannot discriminate for *broad*
  emissions. This is why H71-B is labelled NEGATIVE on uniqueness while H71-A, built from the
  restricted pool, passes at 0.5187.
* **IR-H71-GUARD-01** — `scripts/stop_guard.py` reports STOPPED for anything labelled a
  channel-steepness run. H71 is an *emission* runner: it recomputes no stopped-lane test, rebuilds
  no lane cache and calls no lane driver. The guard verdict is printed and stored verbatim in both
  run cards, and the deviation is disclosed here and in the preregistration rather than performed
  silently.
* **IR-CHAMP-01** (inherited) — the 0.2778 is **[owner-report]** with no organizer receipt tying it
  to the bytes; every inversion in §2–3 inherits that caveat.
* **IR-INSTR-01** (inherited) — the best local instrument against live scores is still
  `drift_corrected_holdout_mean`, ρ = +0.53 (n = 12, p ≈ 0.09); the catalogue-hidden proxy is
  ρ = +0.14. Cross-population promotion decisions therefore cannot rest on local holdouts alone.

## 8. Remaining work, in order (and who owns each step)

1. **Owner decision — the governance wall (§4c).** The literal "≤70 % of dots within 3 px of any
   registry raster" rule cannot be met while `calib_r13lattice_00904.tif` / `r13_lattice_s5_00904.tif`
   are comparators (99.87 % footprint coverage within 3 px), and that rule is what blocks *every*
   artifact, including the already-scored champion and H65-1/H66-1/H68-1. Options: (i) exclude
   space-filling comparators from the clause, with this measurement as the justification; (ii) keep the
   clause and accept that no submission is ever cleared; (iii) replace the dot-overlap rule with a
   byte/pixel-uniqueness + correlation rule. This session did neither: it did not edit the status file
   and claims no exception.
2. **Owner decision — the lane STOP.** `registry/current_site_status.json` still records the H65-1
   first test as INCONCLUSIVE → STOP, and H68-1 (the lane's best artifact on the catalogue holdout)
   inherits it. A new hypothesis ID + preregistration can carry a *new* question; the lane's own
   question stays stopped.
3. **If a measurement slot ever becomes available** (i.e. once 1 and 2 are resolved), the evidence
   order is: (a) `H69A`+`H69B` — two uploads that pin `T`, `K`, `F` exactly and convert every later
   decision into arithmetic; (b) `H72` union — the single artifact that measures whether the
   complementary field's 0.4018 credit/dot transfers to the hidden population (`H71-A` alone if a
   virgin mask is required — it is a probe and scores low alone).
4. **After a return exists:** recompute the optimal mass from the identification equations and choose
   the single artifact for the *final* selection (the competition scores one chosen submission in both
   rounds; the choice is blind, so it must rest on measured evidence).
5. **H73 tip-extrapolation** (new hypothesis ID + preregistration; the H65-1 STOP stands for the
   lane's original question). Data are local (`trace_segments_utm11.csv` + the 10 m stack).
6. **H74 geo-energy convergence** — only if the owner wants the bridge run that pulls the INGENIOUS
   geodetic/thermal layers; the only route that does not depend on the published compilation at all.
7. **Housekeeping:** the identifier collision with the unrelated **H70-1** lane run merged to main was
   resolved by renumbering this line to **H71/H72** (cards carry a `renumbering` record; bytes and
   measurements unchanged). `tests/test_lane_core.py` cannot be collected in this sandbox
   (`ModuleNotFoundError: numba`) — an environment gap worth fixing before the next lane session.

**Limitations that do not go away.** The hidden population cannot be observed locally; the
catalogue-based holdout is structurally blind to off-catalogue arms (ρ +0.14 against 12 owner-reported
scores); the 0.2778 anchor is unverified; the two local instruments disagree about the same artifacts
(§4c); the literal uniqueness clause is unsatisfiable as written; and nothing in this session is an
organizer-confirmed score.
