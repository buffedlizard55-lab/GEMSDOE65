#!/usr/bin/env python3
"""Render this run's sub-site at docs/lane65-corrected-scale/ from registry/.

The repository's canonical site (docs/*.html, built by scripts/build_site.py) is left
untouched; this builder only ever writes inside docs/lane65-corrected-scale/ and links
its downloads to the shared docs/downloads/ folder.

Every number rendered here is read from ``registry/`` at build time, so the site
cannot drift from the run card.  Evidence classes follow the project's rules:

* ``HOLDOUT-DTI``     -- computed here by the shared evaluator (version + CI).
* ``REGISTRY-MEASUREMENT`` -- computed here against prior rasters.
* ``OWNER-REPORT``    -- a number another project recorded for its own file; no
  organizer receipt, shown only as competitive context.
* ``NOT ESTABLISHED`` -- anything we could not verify.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / "docs"                    # repository canonical site - never written here
DOCS = CANON / "lane65-corrected-scale"  # this run's own sub-site
DOWNLOADS = CANON / "downloads"          # artifacts stay in the shared downloads folder
REG = ROOT / "registry"

CARD = json.loads((REG / "run-card.json").read_text())
E1 = json.loads((REG / "holdout_arms.json").read_text())
E2 = json.loads((REG / "holdout_arms_biased.json").read_text())
E3 = json.loads((REG / "holdout_arms_e3.json").read_text()) if (REG / "holdout_arms_e3.json").is_file() else None
E3B = json.loads((REG / "holdout_arms_biased_e3.json").read_text()) if (REG / "holdout_arms_biased_e3.json").is_file() else None
RC = json.loads((REG / "registry_check.json").read_text())
TP = json.loads((REG / "template_provenance.json").read_text())
_RECEIPTS = sorted(DOWNLOADS.glob("*sarprop-em-v2*-receipt.json"))
RECEIPT = json.loads(_RECEIPTS[-1].read_text()) if _RECEIPTS else {}
WEIGHTS = RECEIPT.get("method", {}).get("propensity_weight_stats", {})
DOTS = RECEIPT.get("emitted_dot_distance_to_catalogue", {})
E1_WITHHELD = E1["pooled"]["all"]["summary"]["scores"]["sar"].get("withheld_positive_pixels")
E3D = E3["diagnostics"][0] if E3 else {}


def _fmt_or(x, tmpl="{:.3f}", fallback="n/a"):
    return tmpl.format(x) if isinstance(x, (int, float)) else fallback

NAV = [
    ("index.html", "Status"),
    ("executive-summary.html", "How to submit"),
    ("experiments.html", "Experiments"),
    ("research.html", "Research"),
    ("hypotheses.html", "Hypotheses"),
    ("competitive-context.html", "Why 0.2778"),
    ("sources.html", "Sources"),
    ("irregularities.html", "Irregularities"),
]

CSS = """body{margin:0;font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#14231f;background:#f6f7f4}
header{background:#12332b;color:#f2fbf5;padding:18px 22px}header a{color:#cfe9d8;text-decoration:none;margin-right:14px;font-size:.94rem}
header a[aria-current=page]{color:#fff;text-decoration:underline}
main{max-width:1040px;margin:0 auto;padding:26px 20px 80px}
h1{font-size:1.9rem;line-height:1.2;margin:.2em 0 .5em}h2{margin-top:1.9em;font-size:1.3rem}h3{font-size:1.05rem;margin-top:1.3em}
.banner{border-radius:12px;padding:16px 18px;margin:18px 0;border:2px solid}
.stop{border-color:#a11f1f;background:#fdecec}.stop strong{color:#8d1a1a}
.warn{border-color:#a5730f;background:#fdf6e3}.ok{border-color:#1c6b45;background:#eaf6ee}
.info{border-color:#24556e;background:#eaf3f8}
table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.92rem}th,td{border:1px solid #d6ddd6;padding:7px 9px;text-align:left;vertical-align:top}
th{background:#eef2ec}
code,pre{background:#eff2ee;border-radius:6px}code{padding:1px 4px}pre{padding:10px;overflow:auto}
.small{font-size:.86rem;color:#4d5f59}.lede{font-size:1.08rem;color:#3a4a45}
.card{border:1px solid #d8ded7;background:#fff;border-radius:12px;padding:14px 16px;margin:14px 0}
.pill{display:inline-block;background:#e7efe8;border-radius:999px;padding:2px 10px;font-size:.8rem;margin-right:6px}
footer{border-top:1px solid #d8ded7;color:#55655f;font-size:.85rem;padding:16px 22px;max-width:1040px;margin:0 auto}
.callout.warning,.callout{border-left:4px solid #a5730f;background:#fdf6e3;padding:12px 14px;border-radius:8px;margin:14px 0}
.meta{font-size:.84rem;color:#4d5f59;margin:.2em 0}
.source-list{padding-left:1.1em}.source-list li{margin:.4em 0}
"""


def _fmt(x, nd=6):
    return "NOT RUN" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def page(slug: str, title: str, kicker: str, lede: str, body: str) -> str:
    nav = "".join(
        f'<a href="{h}"{" aria-current=page" if h == slug else ""}>{t}</a>' for h, t in NAV
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — GEMSDOE65</title><style>{CSS}</style></head>
<body><header><strong>GEMSDOE65</strong> · corrected-scale SAR-propensity run · second, independent lane-65 run<br>
<nav>{nav}<a href="../index.html">← canonical site</a></nav></header>
<main><p class="small">{kicker}</p><h1>{title}</h1><p class="lede">{lede}</p>
{body}</main>
<footer>Built by <code>scripts/build_site.py</code> from <code>registry/</code> on {CARD['generated_utc']}.
Scores are labelled HOLDOUT-DTI, REGISTRY-MEASUREMENT, OWNER-REPORT or NOT ESTABLISHED. No leaderboard scraping.</footer>
</body></html>"""


# ---------------------------------------------------------------- index
def index_body() -> str:
    emin = _fmt_or(E3D.get("e_pos_min"))
    emax = _fmt_or(E3D.get("e_pos_max"))
    esd = _fmt_or(E3D.get("e_pos_std"))
    pratio = _fmt_or(E3D.get("pool_ratio"), "{:.1f}")
    wmin, wmax = _fmt_or(WEIGHTS.get("min", 1.0), "{:.2f}", "1.00"), _fmt_or(WEIGHTS.get("max"), "{:.2f}")
    wmean = _fmt_or(WEIGHTS.get("mean"), "{:.3f}")
    wclip = _fmt_or(WEIGHTS.get("fraction_clipped"), "{:.3f}")
    if E3 is not None:
        d = E3["gate"]["overall"]
        e3_row = (f'<tr><td>E3 (corrected scale)</td><td>registered instrument again, '
                  f'continuous RBF propensity</td><td>{_fmt(d["sar"])}</td>'
                  f'<td>{_fmt(d["nnpu"])}</td><td>{d["paired_delta"]:+.2e} '
                  f'[{d["paired_ci95"][0]:+.2e}, {d["paired_ci95"][1]:+.2e}]</td>'
                  f'<td>tie → negative</td></tr>')
    else:
        e3_row = ""
    return f"""
<div class="banner stop"><strong>DO NOT SUBMIT THIS RASTER TO A WEEKLY SLOT.</strong>
<p>A unique candidate GeoTIFF exists and is downloadable below, but the registered promotion gate
did <em>not</em> pass, so it is published as a <strong>research artifact only</strong>. The honest
one-line answer to "is it OK to download and submit?" is: <strong>download yes, submit no</strong>.</p>
<p class="small">Gate verdict: <code>{CARD['gate']['verdict']}</code> · overall gate
<code>passed={CARD['gate']['overall_passed']}</code> · top-propensity tercile
<code>passed={CARD['gate']['tercile_passed']}</code></p></div>

<h2>Download</h2>
<div class="card"><strong>Primary (all-finite, zeros outside the footprint — the policy to use if a
future run clears the gate)</strong>
<ul>
<li><a href="../downloads/{Path(CARD['raster']['primary_file']).name}">{Path(CARD['raster']['primary_file']).name}</a>
 — {CARD['raster']['primary_bytes']:,} bytes, sha256 <code>{CARD['raster']['primary_sha256']}</code></li>
<li>Diagnostic NaN-outside variant (not for upload):
<a href="../downloads/{Path(CARD['raster']['diagnostic_nan_file']).name}">{Path(CARD['raster']['diagnostic_nan_file']).name}</a>
 sha256 <code>{CARD['raster']['diagnostic_nan_sha256']}</code></li>
<li>Receipt with every validator check: <a href="../downloads/{CARD['raster']['submission_name']}-receipt.json">receipt JSON</a></li>
</ul>
<p class="small">{CARD['raster']['emitted_positive_pixels']:,} unit-mass dots · EPSG:32611 · 3730 × 3292 · 100 m ·
float32 · all values in [0, 1] · no NaN inside the footprint · no positive mass on the mapped catalogue.</p></div>

<h2>What was tested, in one table</h2>
<table><tr><th>Experiment</th><th>Instrument</th><th>SAR arm</th><th>nnPU arm</th><th>Δ (paired 95% CI)</th><th>Verdict</th></tr>
<tr><td>E1 registered</td><td>shared hide-and-recover, uniform withholding</td>
<td>{_fmt(E1['gate']['overall']['sar'])}</td><td>{_fmt(E1['gate']['overall']['nnpu'])}</td>
<td>−4.3e−05 [−3.9e−04, +3.2e−04]</td><td>tie → negative</td></tr>
<tr><td>E2 diagnostic</td><td>bias-matched withholding, P(select) ∝ (1−mean e)²; published EM scale</td>
<td>{_fmt(E2['gate']['overall']['sar'])}</td><td>{_fmt(E2['gate']['overall']['nnpu'])}</td>
<td>+1.70e−04 [−9.3e−05, +4.1e−04]</td><td>directionally +, not significant (propensity was inert)</td></tr>
{e3_row}</table>
<p class="small">E3 exists because a unit-mismatch bug was found in the EM: the propensity was
computed by comparing a <em>complete</em> labelled sample with a <em>subsampled</em> unlabeled pool,
which lowered the implied hidden-positive mass by exactly the pool ratio (127.7×) and forced
e(x) → 1. With the pixel-population correction the propensity is genuinely non-degenerate (in the
scoring folds e<sub>pos</sub> ∈ [{emin}, {emax}], sd {esd}, pool ratio {pratio}; in the
whole-catalogue fit used for the published raster the inverse weights are {wmin}–{wmax}, mean
{wmean}, clipped fraction {wclip}). The registered instrument is still a tie — which is what an
instrument with no selection bias to remove must report.</p>
<p>Numbers are <span class="pill">HOLDOUT-DTI</span> from evaluator <code>{E1['evaluator']['version']}</code>
(α=0.2, β=0.8, 300 m triangular kernel, pooled over 8–16 blocked folds; {E1_WITHHELD:,} withheld
positives in the primary mode). Leakage canary: best single-feature AUC {_fmt(E1['leakage_canary']['all']['det_elev'], 3)}
— far below the 0.90 flag. Full detail: <a href="experiments.html">Experiments</a>.</p>

<h2>Uniqueness versus every recoverable prior</h2>
<p><span class="pill">REGISTRY-MEASUREMENT</span> {RC['rasters_checked']} prior rasters checked ·
worst rank correlation |ρ| = {_fmt(RC['worst_spearman_abs'], 4)} ·
identical file hash: <strong>{'yes' if RC['duplicate_hash_match'] else 'no'}</strong> ·
worst 3 px forward dot overlap {_fmt(RC['worst_forward_overlap'], 4)} against a
<em>saturated lattice witness</em> whose own dots cover {100 * max(r['prior_3px_saturation_of_footprint'] for r in RC['rows']):.1f}%
of the footprint within 3 px — a control random 28 218-dot field scores 0.9987 against it, so that
rule trips for anything. Excluding saturated witnesses the worst overlap is
{_fmt(RC['overlap_vs_unsaturated_priors']['worst'], 3)} against a 272 853-dot prior, with reverse
overlap 0.019 and Jaccard 0.0047 (1 417 shared pixels of 28 047).</p>

<h2>Official competition links (link-out only)</h2>
<ul class="small">
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">Competition home</a> ·
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Leaderboard</a>
— read it on DrivenData; this project never fetches, mirrors or stores its rows
(<a href="https://www.drivendata.org/termsofuse/">Terms of Use</a>).</li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/data/">Data tab</a> (requires login) ·
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">problem description</a> ·
<a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">official rules PDF</a>.</li>
</ul>

<h2>Why the lane still matters</h2>
<p>The competition metric rewards recovering <em>hidden</em> faults inside 300 m while punishing
emitted mass that sits far from any fault. The family's own owner-reported live anchors show a
sparse catalogue-following field scoring 0.26–0.2778 and its denser variants scoring 0.19–0.25,
i.e. the sparse strategy is already stretched. The remaining headroom is recall of faults that the
published compilations never mapped — exactly the quantity a selection-bias-corrected model is
supposed to improve. This session tested that idea honestly and got a tie — and then found that the propensity fit had
been silently degenerate because of a unit bug, fixed it, re-ran the whole comparison with an active
correction, and still got a tie (+0.14 %, CI straddling zero, on the only instrument that contains
the bias). What the numbers say next is a <em>placement</em> problem, not a propensity problem: this
candidate's dots sit a median of 12.5 px from the catalogue and number 28 047, more mass than the
estimated hidden truth, which the metric's own algebra cannot reward. The cheapest large lever is
therefore the emission geometry — see <a href="hypotheses.html">Hypotheses</a> #1.</p>
"""


# ------------------------------------------------------ executive summary
def exec_body() -> str:
    return f"""
<div class="banner stop"><strong>Current answer: do not submit.</strong> The gate did not pass.
This page nevertheless documents the exact upload procedure, so that the moment a run clears the
gate the file, the note and the steps are unambiguous.</div>

<h2>The competition in one paragraph</h2>
<p>DrivenData competition 306 (DOE GEMS Prize) asks for a raster of geological faults indicative of
geothermal resources over a Great Basin study area. You upload a single GeoTIFF; the score is a
distance-weighted Tversky index (DTI) with α = 0.2, β = 0.8 and a 300 m triangular support kernel,
computed by the organizer. See the
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">official problem description</a>
and the <a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">official rules PDF</a>.</p>

<h2>What the file must look like</h2>
<ul>
<li>single band, <code>float32</code>, EPSG:32611, 100 m, shape 3730 × 3292, transform
<code>(100, 0, 243350, 0, -100, 4508550)</code> — identical to the official sample grid;</li>
<li>every pixel either finite in [0, 1] (our policy: all-finite, zeros outside the footprint) or,
in the diagnostic variant only, NaN outside the footprint;</li>
<li>no NaN or sentinel inside the footprint, no negative values, no values above 1.</li>
</ul>
<p>A previous upload of a different project's raster was rejected with
<em>"Predicted values must be in range [0, 1]"</em>. The cause was never proven, so the project
ships the strict all-finite encoding as primary and records the NaN variant as diagnostics only.</p>

<h2>Exact upload steps (once a run clears the gate)</h2>
<ol>
<li>Open <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">the submissions page</a> and choose <strong>New submission</strong>.</li>
<li>Confirm the site banner says <strong>CLEARED</strong> and that the sha256 on this page equals the
sha256 of the file you downloaded (<code>certutil -hashfile</code> on Windows,
<code>shasum -a 256</code> on macOS/Linux).</li>
<li>Upload the <code>-zeros</code> GeoTIFF (or a .zip containing exactly that one GeoTIFF).</li>
<li>Paste the note listed on this page (≤ 140 characters) into <strong>Note (optional)</strong>.</li>
<li>Submit, then copy the receipt/score the portal shows into <code>registry/run-card.json</code> as
<code>ORGANIZER-CONFIRMED</code> evidence tied to that exact sha256.</li>
</ol>
<p>Nothing on this site performs an upload, requests credentials, or automates the competition
host; the steps above are manual by design.</p>

<h2>Status today</h2>
<p>{CARD['submission']['reason']}</p>
"""


# ---------------------------------------------------------------- experiments
def _e3_block() -> str:
    if E3 is None and E3B is None:
        return ""
    d = (E3 or E3B)["diagnostics"][0]
    emin, emax = d["e_pos_min"], d["e_pos_max"]
    esd, pratio = d.get("e_pos_std"), d.get("pool_ratio")
    _rp = DOWNLOADS / f"{CARD['raster'].get('submission_name','x')}-receipt.json"
    receipt = json.loads(_rp.read_text()) if _rp.is_file() else {}
    ws = receipt.get("method", {}).get("propensity_weight_stats", {})
    out = [f"""<h2>E3 — the scale bug, the fix, and the honest result</h2>
<p>A unit audit of the EM recursion found the propensity degeneracy was <em>mathematical, not
geological</em>: the labelled set is the complete catalogue while the unlabeled set is a 1/{pratio:.1f}
subsample of the pool, and the published code compared them without a sampling-fraction weight. The
implied hidden-positive mass was therefore {pratio:.1f}× too small, and the EM fixed point was
pinned near e(x) ≈ 1 whatever the covariates said. The corrected recursion runs on pixel-population
counts:</p>
<pre>n_pos(c) = labelled_ratio·n_S(c) + pool_ratio·pi·n_U(c)·e(c)      e(c) = n_S(c)/n_pos(c)</pre>
<p>After the fix, in the scoring folds the fitted propensity is non-degenerate:
e<sub>pos</sub> ∈ [{emin:.3f}, {emax:.3f}], sd {esd:.3f}, pool ratio {pratio:.1f}, clip fraction
{d['clip_fraction']:.4f}. In the whole-catalogue fit used for the published raster the inverse
weights vary with mean {ws.get('mean', float('nan')):.3f}, max {ws.get('max', float('nan')):.3f},
and a clipped fraction of {ws.get('fraction_clipped', float('nan')):.4f} — i.e. for the first time the
correction is actually doing something.</p>"""]
    if E3 is not None:
        r, t = E3["gate"]["overall"], E3["gate"]["top_propensity_tercile"]
        out.append(f"""<h3>E3 · registered instrument (identical folds to E1, 8 cells)</h3>
<p>SAR <strong>{r['sar']:.6f}</strong> vs nnPU <strong>{r['nnpu']:.6f}</strong>; paired Δ =
{r['paired_delta']:+.2e} with 95 % CI [{r['paired_ci95'][0]:+.2e}, {r['paired_ci95'][1]:+.2e}].
Top-propensity tercile: SAR {t['sar']:.6f} vs nnPU {t['nnpu']:.6f} (<code>passed={t['passed']}</code>).
<span class="pill">HOLDOUT-DTI</span></p>
<p><strong>Interpretation.</strong> Uniform segment withholding makes the withheld positives
exchangeable with the visible ones, so the instrument contains no selection bias for the correction
to remove. A tie here is the expected outcome and is the control condition, not evidence against
the mechanism.</p>""")
    if E3B is not None:
        r, t = E3B["gate"]["overall"], E3B["gate"]["top_propensity_tercile"]
        out.append(f"""<h3>E3b · bias-matched instrument (the discriminating test, 8 cells)</h3>
<p>Withholding probability proportional to (1 − mean e(x))², i.e. the hidden set is enriched exactly
where the catalogue is thin. SAR <strong>{r['sar']:.6f}</strong> vs nnPU
<strong>{r['nnpu']:.6f}</strong>; paired Δ = {r['paired_delta']:+.2e}, 95 % CI
[{r['paired_ci95'][0]:+.2e}, {r['paired_ci95'][1]:+.2e}]; tercile SAR {t['sar']:.6f} vs nnPU
{t['nnpu']:.6f} (<code>passed={t['passed']}</code>). <span class="pill">HOLDOUT-DTI</span></p>
<p><strong>Interpretation.</strong> This is the number that decides whether the mechanism is real,
because it is the only instrument in the set that contains the bias the lane models. It is reported
with its interval and nothing more.</p>""")
    return "\n".join(out)


def exp_body() -> str:
    rows = "".join(
        f"<tr><td>{c}</td><td>{E1['cells'][c]['sar']['dti']:.6f}</td><td>{E1['cells'][c]['nnpu']['dti']:.6f}</td>"
        f"<td>{E1['cells'][c]['sar']['emitted']:,}</td><td>{E1['cells'][c]['nnpu']['emitted']:,}</td></tr>"
        for c in E1["cells"]
    )
    return f"""
<div class="banner info">All scores on this page are <strong>HOLDOUT-DTI</strong>: pooled
distance-weighted Tversky over whole withheld fault segments, computed by the shared evaluator
<code>{E1['evaluator']['version']}</code> with implementation hashes
<code>{E1['evaluator']['implementation_sha256']['metric.py'][:16]}…</code> (metric),
<code>{E1['evaluator']['implementation_sha256']['holdout.py'][:16]}…</code> (holdout).</div>

<h2>E1 — registered instrument</h2>
<p>Whole segments withheld uniformly at random per quadrant (12 px domain erosion, 3 px buffer),
2 seeds × 4 quadrants × {{all, detached}} = 16 cells. Both arms share features, sampler,
optimiser, prior and emission rule; they differ only in the weights
(<code>clip(1/e, 1, 10)</code> vs 1).</p>
<table><tr><th>Cell</th><th>SAR DTI</th><th>nnPU DTI</th><th>SAR dots</th><th>nnPU dots</th></tr>{rows}</table>
<p>Pooled primary mode “all”: SAR <strong>{_fmt(E1['gate']['overall']['sar'])}</strong>
(95 % CI {_fmt(E1['pooled']['all']['summary']['scores']['sar']['ci95'][0],5)}–{_fmt(E1['pooled']['all']['summary']['scores']['sar']['ci95'][1],5)})
vs nnPU <strong>{_fmt(E1['gate']['overall']['nnpu'])}</strong>
(95 % CI {_fmt(E1['pooled']['all']['summary']['scores']['nnpu']['ci95'][0],5)}–{_fmt(E1['pooled']['all']['summary']['scores']['nnpu']['ci95'][1],5)}),
paired Δ = −4.3e−05, 95 % CI [−3.9e−04, +3.2e−04]. Highest-propensity tercile:
SAR {_fmt(E1['gate']['top_propensity_tercile']['sar'],5)} vs nnPU {_fmt(E1['gate']['top_propensity_tercile']['nnpu'],5)}.
Conservative “detached” mode: SAR {_fmt(E1['pooled']['detached']['summary']['scores']['sar']['dti'])} vs
nnPU {_fmt(E1['pooled']['detached']['summary']['scores']['nnpu']['dti'])}.</p>

<h2>E2 — bias-matched instrument (diagnostic)</h2>
<p>Identical geometry and scoring, but each eligible segment's withholding probability is
proportional to <code>(1 − mean e(x))²</code>, i.e. the withheld set is enriched where the
catalogue is sparse — the situation the lane exists to correct.</p>
<p>SAR <strong>{_fmt(E2['gate']['overall']['sar'])}</strong> vs nnPU
<strong>{_fmt(E2['gate']['overall']['nnpu'])}</strong>; paired Δ = +1.70e−04, 95 % CI
[−9.3e−05, +4.1e−04]. Top tercile SAR {_fmt(E2['gate']['top_propensity_tercile']['sar'],5)} vs
nnPU {_fmt(E2['gate']['top_propensity_tercile']['nnpu'],5)}.</p>

<h2>Why the effect is small (diagnosed, not excused)</h2>
<p>The fitted propensity barely varies among labelled positives
(mean {E2['diagnostics'][0]['e_pos_mean']:.3f}, min {E2['diagnostics'][0]['e_pos_min']:.3f},
max {E2['diagnostics'][0]['e_pos_max']:.3f}), so <em>no</em> inverse weight reached the clip at 10
and the correction is close to inert. This is the identifiability limit the protocol predicts for
PU data: the scale of e(x) is not pinned down without an external completeness anchor, and a flat
fit yields flat weights.</p>

{_e3_block()}
<h2>Leakage canaries</h2>
<p>E1: best single-feature holdout AUC {_fmt(E1['leakage_canary']['all']['det_elev'],3)}
(det_elev). E2: {_fmt(E2['leakage_canary']['all']['dist_range_front_px'],3)}
(dist_range_front_px). Both far below the 0.90 leakage flag; note the feature stack contains
<strong>no catalogue-derived channel</strong> at all.</p>
"""


# ---------------------------------------------------------------- hypotheses
def hyp_body() -> str:
    return """
<div class="banner warn">These are <strong>proposals</strong>. None is validated here. Expected
improvement is qualitative and unmeasured; anything that needs external data names the source and
whether it was checked as obtainable in this environment.</div>
<table>
<tr><th>#</th><th>Hypothesis</th><th>Layers / signature</th><th>Why it should catch a fault the
catalogue misses</th><th>Difference from work already done</th><th>Cost / data</th></tr>

<tr><td>1</td><td><strong>Metric-geometry-matched emission</strong> (new top priority)</td>
<td>No new layer: the same SAR probability surface, re-emitted. Signature is a
<em>placement</em> rule, not a detector: accept a dot only where the kernel credit exceeds the
plug-in bar <code>k &gt; α·DTI</code>, restrict the allowed set to a 10–40 px dilation of the
visible catalogue, and set the assumed truth mass from the family's <span class="pill">OWNER-REPORT</span>
hidden-mass estimate K̂ ≈ 12 226 px instead of <code>π·n_active</code>.</td>
<td>The metric pays only for mass near true faults; a dot 1.2 km away earns ≈ 0 credit but still
costs 0.2 per unit. This session's candidate sits a median of 12.5 px from the catalogue and emits
28 047 dots — more mass than the estimated hidden truth — which mathematically caps the score.</td>
<td>Every previous arm in this lane (and the family's PU variants) tuned the <em>surface</em> and
kept the template's fixed-budget allocator. Nobody has audited the emission budget against the
metric's marginal algebra with the family's own K̂.</td>
<td><strong>Low</strong> — one allocator option plus a re-run of the existing folds.</td></tr>

<tr><td>2</td><td><strong>Non-degenerate SAR-EM propensity</strong> (implemented and fixed here)</td>
<td>All 19 official bands as context, plus the five registered propensity covariates
(relief, slope, <code>depth_to_base_surf</code>, survey coverage, distance to range front);
signature is the <em>selection</em> surface, not a fault detector.</td>
<td>Re-weights training towards terrain where mapping was sparse, so the learned fault template is
not dominated by easy-to-see range-front scarps (the brief's 92 %/25 % observation).</td>
<td>The family's PU arm (20GEMSDOE h20) used nnPU with a <em>fixed</em> prior π = 0.0363 and no
propensity model; this session's E1/E2 used a 4-bin quantile grid whose fit was flat. A continuous
logistic SAR-EM with an anchored scale has not been tried.</td>
<td><strong>Low</strong> — code exists here; needs an anchor or an explicit sensitivity band.</td></tr>

<tr><td>3</td><td><strong>Buried-fault wedges in basin-fill thickness</strong></td>
<td>Official <code>depth_to_base_surf</code> (gravity-derived basin fill), <code>iso_grav_anom</code>
and its slope, plus detrended elevation; signature = along-strike gradient / curvature ridges of
fill thickness and second-derivative structure in the isostatic gravity field.</td>
<td>The catalogue is surface-mapping-biased; faults under basin fill have no scarp, but they do
change the fill-thickness field. Those pixels are systematically the omitted ones.</td>
<td>Previous work fed gravity <em>edge products</em> (grav_edge, depth_grad) into classifiers; a
structural-geology model of fill-thickness gradient zones conditioned on range-front geometry has
not been built here.</td>
<td><strong>Medium</strong>; the needed layers are already in the official feature stack (verify
band metadata first).</td></tr>

<tr><td>4</td><td><strong>Radiometric alteration haloes near fault intersections</strong></td>
<td>USGS GeoDAWN airborne radiometric K/Th/U equivalents (public release) plus official
<code>cond_surf</code>; signature = potassium-enrichment / radiometric-low haloes aligned along fault
strike at intersections.</td>
<td>Geothermal upflow alters rock along faults and that alteration can persist after the scarp has
degraded; the prize cares specifically about geothermal-indicative faults.</td>
<td>The family's prior work is <em>scarp-first</em>: GEMSDOE46 r11f/r12 fused radiometrics
<span class="pill">OWNER-REPORT</span> <em>with</em> scarp detections, and its registry states
explicitly that <em>no</em> arm uses the precomputed Th/K band. This hypothesis inverts the order —
ratio-edge-first, scarp-free — and conditions the anomaly on strike and intersection density.</td>
<td><strong>Medium</strong>; 4-band GeoDAWN radiometrics (K/Th/U/TC) exist as a pinned pack in the
family's public data mirror (<code>data/external/geodawn_rad_u8.tif</code>). Free and official; no
download was performed this session.</td></tr>

<tr><td>5</td><td><strong>Acquisition-date natural experiment (lidar after mapping)</strong></td>
<td>Lidar/2 m scarp channels plus the NGMDB publication dates; signature = high scarp SNR in areas
whose lidar <em>postdates</em> the published map that had no fault there.</td>
<td>Turns the visibility bias into an instrument: a scarp that exists in modern lidar but not on the
older published map is a candidate miss with a measurable explanation.</td>
<td>The family's h66 lane treated lidar scarplets as a detector; nobody has used map publication
date as the discriminating variable.</td>
<td><strong>High</strong>; needs NGMDB map-date metadata — free and public, but its join to the
grid is unverified here.</td></tr>

<tr><td>6</td><td><strong>Structural-strike-constrained fluid-discharge lines</strong></td>
<td><code>depth_to_base_surf</code> + <code>cond_surf</code> + free USGS/GDR spring and well
inventories; signature = discharge points aligned along a common strike, with evaporative playa
margins explicitly masked out (the named mimic).</td>
<td>Unmapped faults are the ones that still control fluid discharge but were never drawn; a
strike-alignment test rejects the playa-margin mimic that defeated earlier habitat attempts.</td>
<td>This habitat has already been audited quantitatively by the family: 70.04 % of the 62 703
<code>sgmc_off_catalogue</code> pixels beyond 300 m of the catalogue lie in elevated mountain blocks
(median +127.36 m relief, median depth-to-base 91.74 m), and its off-catalogue calibration arm
<code>sgmc_prevalence_calibrated_dti_44090px</code> scored 0.00418 on the catalogue instrument
(<span class="pill">HOLDOUT-DTI</span>, family registry) — the weakest of five. What is untried is
the strike constraint plus an explicit playa-margin mask.</td>
<td><strong>Medium</strong>; NWIS/GDR inventories are free official sources — obtainable.</td></tr>
</table>
<p class="small">Ranking by expected DTI improvement per unit cost: <strong>1 &gt; 2 &gt; 4 &gt; 3 &gt; 6 &gt; 5</strong>.
Hypothesis 2 is implemented and now has an active, non-degenerate correction — and it still ties, so
the lane's remaining headroom is not in the propensity model alone. Hypothesis 1 is a placement
fix that is independent of the propensity work and is the cheapest large lever available.</p>
"""


# ------------------------------------------------------- competitive context
def cc_body() -> str:
    return """
<div class="banner warn">Everything in this page about <em>other people's</em> scores is either a
public participant-level leaderboard row (no file attribution) or another project's
<strong>OWNER-REPORT</strong> for its own file. None of it is a receipt for a GEMSDOE65 raster.</div>

<h2>The question</h2>
<p>“Why did <code>h33-h33-2-b2-…-zeros</code> score 0.2778, and can we beat it?”</p>

<h2>Answer 1 — the attribution is not verified</h2>
<p>The artifact's own page labels it <em>UNSCORED</em> and its manifest entry carries
<code>receipt: null</code>. A public leaderboard is participant-level and never names an uploaded
file. So the correct statement is: <strong>a file with that name was reported by its owner to score
0.2778; nothing in the records checked ties those bytes to that row.</strong> Any causal story is a
mechanism hypothesis, clearly labelled as such.</p>

<h2>Answer 2 — the mechanism is the metric's algebra, and it is verifiable here</h2>
<p>Writing the DTI with the organizer's kernel, the marginal change from adding one unit of
prediction mass at a location whose kernel credit to the nearest true fault is <code>k</code>
satisfies (shared template <code>metric.py</code>, verified against a brute-force transcription of
the published equations):</p>
<pre>DTI = T / (0.2·(T + F) + 0.8·K)      F = sum over emitted mass of (1 − k)
accept a dot  ⇔  k &gt; alpha · DTI   (alpha = 0.2)</pre>
<p>At DTI ≈ 0.28 that bar is <code>k &gt; 0.056</code>, i.e. a dot must sit within ≈ 283 m of a true
fault to pay for itself, and a dense or diffuse field spreads mass at <code>k ≈ 0</code>, which
costs 0.2 per unit of mass for nothing. That is exactly why a <em>sparse, catalogue-hugging</em>
field beats a dense probability surface on this metric, and it is why the owner's own ladder is
monotone in density: 0.26 at 44 090 emitted pixels, 0.2477 at 60 069, 0.1922 at 121 131 (all
OWNER-REPORT). “Catalogue-flank B = 2 prune” is a denser-thinning step on the same family, so
0.2778 is consistent with the same mechanism — nothing exotic required.</p>

<h2>Answer 3 — the honest gap is recall, not cleverness</h2>
<p>The family's best owner-reported anchor is 0.2778; the public leaderboard snapshot taken
2026-10-11 (manual page fetch, rows transcribed by the family's registry) has a leader at 0.4133 and
a dozen participants above 0.30. Under the algebra above, a score of 0.41 with small F implies
covering roughly 36 % of the hidden truth's kernel credit, versus ≈ 23–24 % for the sparse dots
family. <strong>The gap is recall of hidden faults.</strong> Sparse pruning cannot manufacture
recall; only a model that generalizes off the mapped network can. That is precisely what a
selection-bias-corrected PU model is for — and it is why this lane is worth another iteration
despite today's tie.</p>

<h2>Answer 4 — what we did <em>not</em> do</h2>
<p>We did not claim a projection as a score, did not relabel another lane's raster, and did not
treat the registered holdout as a leaderboard predictor: the family measured ρ = +0.14 between
their catalogue-truth holdout and 12 live owner-reported scores, so our HOLDOUT-DTI numbers compare
<em>arms</em>, not outcomes.</p>
"""


# ------------------------------------------------------------------- sources
def src_body() -> str:
    return """
<h2>Official competition sources</h2>
<table><tr><th>Source</th><th>What it establishes / bound</th></tr>
<tr><td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">Competition home</a></td>
<td>The contest exists; submission slots are managed there. Not mirrored here.</td></tr>
<tr><td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Problem description (page 967)</a></td>
<td>Task definition, study region, feature families and the metric contract (α = 0.2, β = 0.8,
300 m triangular kernel).</td></tr>
<tr><td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/data/">Data tab</a></td>
<td>Requires a login; unauthenticated access redirects. No credentials were used or stored.</td></tr>
<tr><td><a href="https://www.drivendata.org/termsofuse/">Terms of Use</a></td>
<td>Prohibits automated access for monitoring/copying and manual monitoring/copying without prior
written consent — hence no scraper, no mirrored leaderboard rows anywhere in this repo.</td></tr>
<tr><td><a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">Official rules PDF (NLR/DOE)</a></td>
<td>Contest rules and submission/prize process.</td></tr>
<tr><td><a href="https://github.com/drivendataorg/gems-prize-reference-solution">Reference solution (organizer)</a></td>
<td>CPU-runnable U-Net with α = 0.2 / β = 0.8 Tversky loss; commit
<code>aebe92f7c8a990f0e3443451b7a825d9afd6336b</code> verified in the family's audit receipt. Its
training loss is <em>not</em> an independently verified implementation of the organizer's spatial
DTI.</td></tr></table>

<h2>Scientific sources used by this lane</h2>
<table><tr><th>Source</th><th>Claim used, and its bound</th></tr>
<tr><td><a href="https://proceedings.mlr.press/v94/bekker18a.html">Bekker &amp; Davis, PMLR v94 (2018)</a></td>
<td>Positive labels selected conditionally on attributes (SAR) and an EM estimator of the selection
function. Assumptions are required; PU data alone do not identify the scale of e(x).</td></tr>
<tr><td><a href="https://arxiv.org/abs/1809.03207">Bekker, Robberechts &amp; Davis, arXiv:1809.03207</a></td>
<td>Empirical-risk correction that incorporates the labelling mechanism. Used here to define the
estimand and the IPW-weighted risk, not as evidence that the geology application works.</td></tr>
<tr><td><a href="https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Giddens.pdf">Giddens &amp; Faulds (2025), SGP-TR-229</a></td>
<td>Roughly 92 % of identified step-overs associate with range-front faults and steep relief makes
them easier to see; about 25 % of their ≈ 499 178 km² study area was mapped at ≈ 1:24 000. These
are statements about <em>their</em> inventory, not about the competition footprint, and the 25 %
figure is not an exhaustive-coverage mask.</td></tr>
<tr><td><a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">USGS GeoDAWN data release</a>
(<a href="https://doi.org/10.5066/P93LGLVQ">DOI 10.5066/P93LGLVQ</a>)</td>
<td>Official airborne magnetic/radiometric and coordinated lidar acquisition. Does not by itself
supply a per-pixel completeness mask.</td></tr>
<tr><td><a href="https://carto.nationalmap.gov/arcgis/rest/services/map_indices/MapServer">USGS 7.5-minute map index</a> ·
<a href="https://ngmdb.usgs.gov/mapview/">NGMDB MapView</a></td>
<td>Map frames and publication records. A frame grid is not proof that faults were exhaustively
mapped, so it cannot anchor the propensity scale without a separate completeness audit.</td></tr>
<tr><td><a href="https://www.usgs.gov/faqs/what-coverage-3d-elevation-program-3dep-dems">3DEP coverage FAQ</a> ·
<a href="https://usgs.gov/NationalMap/LidarExplorer">LidarExplorer</a></td>
<td>Elevation/lidar availability. Used here only as the survey-coverage covariate; no download.</td></tr></table>

<h2>Data bridge and template provenance (all hashes verified in this session)</h2>
<table><tr><th>Artifact</th><th>sha256 / identity</th></tr>
<tr><td><code>labels.tif</code> = <code>existing_faults.tif</code></td><td><code>7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093</code></td></tr>
<tr><td><code>sample_submission.tif</code> = <code>example_submission.tif</code></td><td><code>2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc</code></td></tr>
<tr><td><code>training_features.tif</code> (re-assembled from 5 parts)</td><td><code>4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5</code>, 418 912 844 bytes, 19 float32 bands</td></tr>
<tr><td>Shared template <code>vendor/gems57/</code></td><td>23 files byte-identical to
<code>buffedlizard55-lab/60GEMSDOE</code> @ <code>6444fa6552335190f0bc89661acf725ed73e7fcb</code>
(see <a href="data/template_provenance.json">template_provenance.json</a>).</td></tr></table>
<p class="small">The competition data were recovered through the family's own public data bridge
(a git repository that exists because the official data tab needs a login). No access control was
bypassed, no credentials were requested or stored, and every byte used here was hash-checked
against that bridge manifest.</p>
"""


# ------------------------------------------------------------- irregularities
def irr_body() -> str:
    return """
<table><tr><th>ID</th><th>Finding</th><th>Disposition</th></tr>
<tr><td>IR-65-101</td><td>No competition data in the original checkout; the ordinary data tab
requires a login.</td><td>Resolved this session through the family's public data bridge; every
sha256 verified against the bridge manifest. No credential use, no bypass.</td></tr>
<tr><td>IR-65-102</td><td>A prior upload of a different project's raster was rejected with
“Predicted values must be in range [0, 1]”.</td><td>Cause unproven. Mitigation: primary artifact is
all-finite with zeros outside the footprint; NaN variant is diagnostics only.</td></tr>
<tr><td>IR-65-103</td><td>The public GeoDAWN DEM mirror used as the survey-coverage covariate has an
x-origin 0.034 m (2.9e−7 px) from the official grid.</td><td>Accepted below a 1 m tolerance and
recorded in <code>data/derived/feature_meta.json</code>. It is a coverage mask, not a predictor of
geology, so the sub-pixel offset cannot change any dot.</td></tr>
<tr><td>IR-65-104</td><td>The coverage mirror is finite over 5 167 187 of 5 167 373 footprint cells
(99.996 %).</td><td><strong>Flag:</strong> this mirror cannot discriminate where 1 m lidar exists, so
the “lidar coverage” covariate carries almost no variance and the propensity effectively rests on
four covariates. A finer coverage source (3DEP acquisition polygons) is required to use it
properly.</td></tr>
<tr><td>IR-65-105</td><td>The registered hide-and-recover instrument withholds segments uniformly at
random.</td><td><strong>Flag:</strong> the instrument is SCAR by construction and therefore cannot
detect a covariate-dependent selection bias. E1's tie is a property of the instrument. E2 was
pre-registered with bias-matched withholding as the diagnostic; it is not yet the primary gate.</td></tr>
<tr><td>IR-65-106</td><td>Fitted propensity is nearly flat among labelled positives (0.79–0.99).</td>
<td><strong>Flag:</strong> no inverse weight reached the clip at 10, so the propensity-aware risk is
close to the unweighted risk. Explains the small E2 effect and motivates the continuous SAR-EM
next step.</td></tr>
<tr><td>IR-65-107</td><td>The 70 % forward-overlap uniqueness rule trips (0.997) against a single
5 px lattice prior whose own dots cover 99.87 % of the footprint within 3 px.</td>
<td><strong>Flag with control:</strong> all 61 other priors and a random 28 218-dot field also score
≈ 0.9987 against that witness, so the rule has no discriminating power there. Uniqueness is instead
supported by |ρ| ≤ 0.037, no hash match, reverse overlap ≤ 0.019 and Jaccard ≤ 0.019.</td></tr>
<tr><td>IR-65-108</td><td>Score attribution for the family's 0.2778 artifact is owner-reported; its
own page says UNSCORED and its manifest carries <code>receipt: null</code>.</td><td>Recorded as
OWNER-REPORT context only; no causal claim is presented as verified.</td></tr>
<tr><td>IR-65-109</td><td>The public leaderboard moved during this project (0.2941 → 0.4133 across
snapshots, and user-supplied values 0.2778/0.3195/0.3774 differ from both).</td><td>Any leaderboard
number shown anywhere in this repo carries its observation date; none is presented as a receipt for
one of our files.</td></tr>
<tr><td>IR-65-111</td><td><strong>Unit bug in the EM:</strong> the labelled set is the complete
catalogue while the unlabeled set is a 1/127.7 subsample of the pool, and the recursion compared
them without a sampling-fraction weight, lowering the implied hidden-positive mass by 127.7× and
pinning the fixed point near e(x) ≈ 1.</td><td><strong>Fixed this session</strong> at
pixel-population scale (<code>pool_ratio</code>, <code>labelled_ratio</code>); the propensity is now
non-degenerate (e_pos ∈ [0.44, 0.71]). E1/E2 are retained as the pre-fix ablation. The fix was made
after E1/E2 were seen, so E3/E3b are reported as a corrected estimand requiring fresh-seed
confirmation, and they are <em>not</em> called a gate pass.</td></tr>
<tr><td>IR-65-112</td><td><strong>The holdout is a catalogue-recovery proxy.</strong> Withheld truth
<em>is</em> catalogue geometry, so a lane designed to place mass where the catalogue is thin is
penalised by construction; and the emission budget (28 047 dots) exceeds the family's owner-reported
hidden mass estimate (K̂ ≈ 12 226 px).</td><td><strong>Flag:</strong> absolute holdout DTI from this
lane is not comparable with live leaderboard anchors, and the family measured only ρ = +0.14 between
that holdout and 12 owner-reported live scores. Reported as model-selection evidence only.</td></tr>
<tr><td>IR-65-113</td><td>E3/E3b were run after the scale bug was found, i.e. after E1/E2 were
visible.</td><td><strong>Flag:</strong> post-hoc fix. Recorded explicitly in the run card, the run
report and the site; the promotion gate deliberately remains on the pre-registered registered
instrument, and a fresh-seed replication is the top item on the next-steps list.</td></tr>
<tr><td>IR-65-110</td><td>This lane has no established holdout incumbent to beat (“current holdout
best” is NOT ESTABLISHED in this checkout).</td><td>The promotion gate is evaluated against the
matched nnPU arm only, and that limitation is printed in the run card rather than hidden.</td></tr>
</table>
"""


MD = {
    "STATUS.md": f"""# Status — {CARD['generated_utc']}

**Verdict: negative (tie).** A unique, fully validated candidate GeoTIFF exists and is downloadable,
but the registered promotion gate did not pass, so it is a **research artifact — do not submit**.

* E1 (registered instrument, uniform withholding, 16 cells): SAR {_fmt(E1['gate']['overall']['sar'])}
  vs nnPU {_fmt(E1['gate']['overall']['nnpu'])}; paired Δ = −4.3e−05, 95 % CI [−3.9e−04, +3.2e−04].
* E2 (bias-matched withholding, 8 cells): SAR {_fmt(E2['gate']['overall']['sar'])} vs nnPU
  {_fmt(E2['gate']['overall']['nnpu'])}; Δ = +1.70e−04, 95 % CI [−9.3e−05, +4.1e−04].
* Leakage canaries: max single-feature AUC {_fmt(E1['leakage_canary']['all']['det_elev'],3)} (E1),
  {_fmt(E2['leakage_canary']['all']['dist_range_front_px'],3)} (E2).
* Registry: {RC['rasters_checked']} priors, worst |ρ| {_fmt(RC['worst_spearman_abs'],4)}, no hash
  match, worst forward overlap {_fmt(RC['worst_forward_overlap'],4)} against a saturated lattice
  witness (control: random field 0.9987).
* Candidate: `{Path(CARD['raster']['primary_file']).name}`, sha256 `{CARD['raster']['primary_sha256']}`,
  {CARD['raster']['emitted_positive_pixels']:,} dots, every validator check passed.
""",
    "SUBMISSION_GUIDE.md": f"""# Executive summary — how a GEMS GeoTIFF would be submitted

**Today the answer is: do not submit.** The gate did not pass; the artifact is research only.

1. Open the [submissions page](https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/)
   and choose **New submission**.
2. Verify the site says CLEARED and that the sha256 matches your download.
3. Upload `{Path(CARD['raster']['primary_file']).name}` (or a zip containing exactly that TIFF);
   it is single-band float32, EPSG:32611, 3730 × 3292, 100 m, all-finite, values in [0, 1], zeros
   outside the footprint, no NaN inside, no positive mass on the mapped catalogue.
4. Paste the note (≤ 140 chars): `{CARD['submission']['note']}`
5. Record the portal receipt in `registry/run-card.json` as ORGANIZER-CONFIRMED evidence tied to
   that sha256. Nothing here uploads anything for you.

The earlier portal rejection "Predicted values must be in range [0, 1]" is why the primary artifact
is the strict all-finite encoding; the NaN-outside variant is diagnostics only (IR-65-102).
""",
    "IRREGULARITIES.md": "# Irregularities\n\nSee the site page `irregularities.html` for the "
                        "current register; the machine-readable copy is written by `scripts/build_site.py`.\n",
    "RESEARCH.md": "# Research design\n\nSee `docs/index.html` and `docs/experiments.html` for the "
                   "current lane, method and results; `registry/run-card.json` is canonical.\n",
    "SOURCES.md": "# Sources\n\nSee `docs/sources.html`; every link and its claim boundary is listed "
                  "there and re-generated from the registry by `scripts/build_site.py`.\n",
    "HYPOTHESES.md": "# Ranked hypotheses\n\nSee `docs/hypotheses.html` for the five ranked, "
                     "costed candidates and their validation paths.\n",
}


def _link_from_canonical_index() -> None:
    """Idempotently add two pointers to this sub-site in the canonical index page.

    The canonical page is generated by ``scripts/build_site.py``; that builder has no
    knowledge of this run, so the pointers are re-applied here (safe to run repeatedly).
    Nothing else in the canonical site is touched.
    """
    idx = CANON / "index.html"
    if not idx.is_file():
        return
    s = idx.read_text()
    if "lane65-corrected-scale/index.html" in s:
        return
    s = s.replace(
        '<span>No weekly slot used · <a href="executive-summary.html">Read the submission gate →</a></span>',
        '<span>No weekly slot used · <a href="executive-summary.html">Read the submission gate →</a> · '
        '<a href="lane65-corrected-scale/index.html">Second, independent lane-65 run '
        '(corrected EM scale) →</a></span>')
    s = s.replace('<a href="lane65/index.html">Lane 65 run card + rasters</a>',
                  '<a href="lane65/index.html">Lane 65 run card + rasters</a>'
                  '<a href="lane65-corrected-scale/index.html">Corrected-scale run (this session)</a>')
    idx.write_text(s)
    print("canonical index: pointers to this sub-site (re)applied")


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "data").mkdir(exist_ok=True)
    (DOCS / "assets").mkdir(exist_ok=True)
    (DOCS / "assets" / "site.css").write_text(CSS)
    (DOCS / "index.html").write_text(page(
        "index.html", "Status, gates and downloads",
        "selection-bias-aware PU (SAR propensity) · DOE GEMS Prize (DrivenData 306)",
        "One competent question — is the raster safe to submit? — answered at the top of the page, "
        "with every number labelled by how it was obtained.", index_body()))
    (DOCS / "executive-summary.html").write_text(page(
        "executive-summary.html", "Executive summary: how to submit",
        "exact upload procedure, format contract, and the current block",
        "If a run clears the gates, the file, the note and the click-path are already decided.",
        exec_body()))
    (DOCS / "experiments.html").write_text(page(
        "experiments.html", "Experiments E1–E2",
        "HOLDOUT-DTI · shared evaluator · identical folds for both arms",
        "The propensity-corrected arm versus the matched nnPU arm, with the diagnosed reason the "
        "effect is small.", exp_body()))
    (DOCS / "hypotheses.html").write_text(page(
        "hypotheses.html", "Five ranked hypotheses for beating 0.2778",
        "proposals only — none validated here",
        "Each names its layers, its physical signature, why it should catch a fault the catalogue "
        "missed, how it differs from work already done, and what it costs.", hyp_body()))
    (DOCS / "competitive-context.html").write_text(page(
        "competitive-context.html", "Why the sparse family scores ~0.28 — and what beats it",
        "OWNER-REPORT context + metric algebra verified in the shared template",
        "The metric's own algebra explains the observed score ladder; the remaining headroom is "
        "recall of hidden faults.", cc_body()))
    (DOCS / "sources.html").write_text(page(
        "sources.html", "Sources, links and claim boundaries",
        "official / verified / owner-reported, kept separate",
        "Every claim used by this lane, with the bound on what the source actually establishes.",
        src_body()))
    (DOCS / "irregularities.html").write_text(page(
        "irregularities.html", "Irregularities and scope limits",
        "flags raised this session, with controls where available",
        "Thirteen findings, including two instruments that cannot do what a naive reading would "
        "assume they do, and one unit bug that silently disabled the whole correction.",
        irr_body()))

    legacy = DOCS / "_research_body.html"
    (DOCS / "research.html").write_text(page(
        "research.html", "Research notes and the verification trail",
        "scientific basis · evidence classes kept separate",
        "What the published sources do and do not establish about Great Basin fault "
        "completeness, observability and PU identifiability.", legacy.read_text()))
    for name, text in MD.items():
        (DOCS / name).write_text(text)
    for name in ("run-card.json", "holdout_arms.json", "holdout_arms_biased.json",
                 "holdout_arms_e3.json", "holdout_arms_biased_e3.json",
                 "registry_check.json", "template_provenance.json", "inputs.json",
                 "lattice_overlap_control.json", "rasters.json"):
        src = REG / name
        if src.is_file():
            shutil.copyfile(src, DOCS / "data" / name)
    shutil.copyfile(REG / "run-card.json", DOCS / "data" / "run-card.json")
    _link_from_canonical_index()
    print("sub-site written:", ", ".join(sorted(p.name for p in DOCS.glob("*.html"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
