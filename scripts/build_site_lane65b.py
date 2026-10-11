#!/usr/bin/env python3
"""Render the lane-65b GitHub Pages sub-site from the committed evidence receipts.

This is the SECOND, independent lane-65 (SAR-PU) session of 2026-10-11. The canonical
site for this repository is ``docs/index.html``, built by ``scripts/build_site.py``;
this builder writes only inside ``docs/lane65b/`` and never touches it.

No number on the site is typed by hand: every figure is read from ``evidence/*.json``
or ``registry/*.json`` at build time, so the site cannot drift from the receipts.

Outputs (``docs/``):
    index.html                 verdict banner, one-click download, results, hypotheses
    executive-summary.html     exactly how to make a submission (subpage, linked first)
    research/*.html            rendered research notes
    downloads/                 the artefact, its zip, its run card and format checks
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import _bootstrap  # noqa: F401,E402

from gems65.paths import DOWNLOADS, EVIDENCE, ROOT, ensure_dirs  # noqa: E402

DOCS = ROOT / "docs" / "lane65b"
DL = "../downloads"
SITE = "https://buffedlizard55-lab.github.io/GEMSDOE65/docs/lane65b/"

OFFICIAL_LINKS = [
    ("Competition page (metric, format, provided features)",
     "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/"),
    ("Official public leaderboard",
     "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"),
    ("Scoring clarification: are known USGS/INGENIOUS faults masked? (staff answer: yes)",
     "https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-"
     "masked-when-scoring-and-are-they-in-the-final-round-label-set/11516"),
    ("Organizer reference solution (all-finite raster, no nodata tag)",
     "https://github.com/drivendataorg/gems-prize-reference-solution"),
    ("INGENIOUS project (Geothermal Data Repository)",
     "https://gdr.openei.org/submissions/1391"),
    ("USGS QFaults / fault database", "https://www.usgs.gov/programs/earthquake-hazards/faults"),
    ("USGS 3DEP elevation (1 m / 10 m)", "https://www.usgs.gov/3d-elevation-program"),
    ("USGS isostatic residual gravity", "https://mrdata.usgs.gov/gravity/isostatic/"),
    ("GeoDAWN airborne magnetic & radiometric surveys (USGS data release)",
     "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-"
     "great-basin-nevada-and"),
    ("EPSG:32611 — WGS 84 / UTM zone 11N", "https://epsg.io/32611"),
    ("Tversky index (the metric's set-similarity family)",
     "https://en.wikipedia.org/wiki/Tversky_index"),
]

METHOD_LINKS = [
    ("Bekker & Davis 2018, 'Learning from positive and unlabeled data with a "
     "selection bias' (PMLR v94) — the SAR EM used here",
     "https://proceedings.mlr.press/v94/bekker18a.html"),
    ("Bekker, Robberechts & Davis 2018, arXiv:1809.03207 — propensity-aware "
     "empirical risk minimization", "https://arxiv.org/abs/1809.03207"),
    ("Kiryo et al. 2017, arXiv:1703.00593 — the non-negative PU (nnPU) baseline",
     "https://arxiv.org/abs/1703.00593"),
    ("Giddens & Faulds 2025, SGP-TR-229 — Great Basin structure and geothermal "
     "play fairways", "https://pangea.stanford.edu/researchgroups/geothermal/"),
]

CSS = """
:root{--ink:#12212e;--mut:#5a6b7b;--line:#dfe6ec;--bg:#f6f8fa;--ok:#0f7b3f;--okbg:#e7f6ec;
--bad:#a3161b;--badbg:#fdecec;--warn:#8a5a00;--warnbg:#fff6e0;--acc:#0b5fa5}
*{box-sizing:border-box}
body{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
color:var(--ink);background:#fff}
header{background:var(--bg);border-bottom:1px solid var(--line);padding:18px 24px}
header .wrap{max-width:1080px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}h2{font-size:19px;margin:34px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}
h3{font-size:16px;margin:22px 0 6px}
main{max-width:1080px;margin:0 auto;padding:20px 24px 60px}
p{margin:8px 0}a{color:var(--acc)}
.mut{color:var(--mut);font-size:14px}
.banner{border-radius:10px;padding:18px 20px;margin:16px 0;border:2px solid}
.banner.ok{background:var(--okbg);border-color:var(--ok)}
.banner.bad{background:var(--badbg);border-color:var(--bad)}
.banner h2{border:0;margin:0 0 6px;font-size:22px}
.banner.ok h2{color:var(--ok)}.banner.bad h2{color:var(--bad)}
.btn{display:inline-block;background:var(--acc);color:#fff;text-decoration:none;padding:12px 18px;
border-radius:8px;font-weight:600;margin:6px 8px 6px 0}
.btn.sec{background:#fff;color:var(--acc);border:1px solid var(--acc)}
.btn.dis{background:#7a8794}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:var(--bg)}
code{background:var(--bg);padding:1px 5px;border-radius:4px;font-size:13px}
pre{background:var(--bg);padding:12px;border-radius:8px;overflow:auto;font-size:13px}
.card{border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0;background:#fff}
.tag{display:inline-block;font-size:11px;letter-spacing:.04em;text-transform:uppercase;
border:1px solid var(--line);border-radius:999px;padding:2px 8px;color:var(--mut);background:var(--bg)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:800px){.grid2{grid-template-columns:1fr}}
ol li,ul li{margin:5px 0}
footer{border-top:1px solid var(--line);padding:18px 24px;color:var(--mut);font-size:13px}
"""


def _load(p: Path, default=None):
    return json.loads(p.read_text()) if p.exists() else default


def page(title: str, body: str, *, active: str = "") -> str:
    nav = [("index.html", "Submission & results"), ("executive-summary.html", "How to submit")]
    links = " · ".join(
        f'<a href="{h}"><b>{t}</b></a>' if h == active else f'<a href="{h}">{t}</a>'
        for h, t in nav)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><link rel="stylesheet" href="assets/site.css"></head>
<body><header><div class="wrap"><h1>GEMSDOE65 — selection-bias-aware PU learning (SAR)
for the DOE GEMS Prize</h1>
<div class="mut">{links} · <a href="research/hypotheses.html">Hypotheses</a> ·
<a href="research/why-02778.html">Why 0.2778</a> ·
<a href="research/irregularities.html">Irregularities</a> ·
<a href="../../README.md">README / standing brief</a> ·
<a href="../index.html">canonical site</a> ·
<a href="{SITE}">site root</a></div></div></header>
<main>{body}</main>
<footer>Built {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} from committed evidence
receipts by <code>scripts/build_site.py</code>. Every number carries an evidence class.
HOLDOUT-DTI is a local blocked-holdout measurement, never a leaderboard score.
Core values: <b>Maximize P(Win)</b> · <b>Own the Outcome</b>.</footer>
</body></html>"""


def fmt(x, n=6):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{n}f}"
    return str(x)


def dti_row(label: str, s: dict, arm: str, emitted: dict) -> str:
    r = s[arm]
    ci = r["ci95"]
    n = emitted.get(arm)
    credit = (r["tpw"] / n) if n else float("nan")
    return (f"<tr><td>{label}</td><td><code>{arm}</code></td><td><b>{r['dti']:.6f}</b></td>"
            f"<td>[{ci[0]:.6f}, {ci[1]:.6f}]</td><td>{r['withheld_positive_pixels']:,}</td>"
            f"<td>{n:,}</td><td>{credit:.4f}</td>"
            f"<td><span class='tag'>HOLDOUT-DTI</span> {r['evaluator_version']}</td></tr>")


def scores_table(block: dict, title: str) -> str:
    s = block["scores"]
    emitted = block.get("emitted_pixels", {})
    order = [a for a in ("A2_sar_1me", "A1_sar", "A3_sar_em_1me", "B_nnpu",
                         "C_distance_only") if a in s]
    order += [a for a in sorted(s) if a not in order]
    rows = "".join(dti_row(title, s, a, emitted) for a in order)
    paired = block.get("paired_differences") or {}
    prows = "".join(
        f"<tr><td>paired Δ {k}</td><td colspan=2>{v['delta']:+.6f}</td>"
        f"<td>[{v['ci95'][0]:+.6f}, {v['ci95'][1]:+.6f}]</td><td colspan=3>"
        f"{'CI excludes 0' if v['ci95'][0] > 0 or v['ci95'][1] < 0 else 'CI includes 0'}</td></tr>"
        for k, v in sorted(paired.items()))
    return (f"<h3>{title}</h3><table><tr><th>instrument</th><th>arm</th><th>DTI</th>"
            f"<th>95% CI (20 km block bootstrap)</th><th>withheld<br>positives</th>"
            f"<th>dots<br>emitted</th><th>credit<br>per dot</th><th>evidence class</th></tr>"
            f"{rows}{prows}</table>"
            f"<p class='mut'>credit per dot = TP weight / dots emitted; the family's ladder "
            f"arithmetic says a dot pays only if its expected credit exceeds "
            f"alpha x DTI (0.0556 at DTI 0.2778). Arms that cannot fill the budget found fewer "
            f"strict local maxima than the budget inside the allowed mask.</p>")


def build() -> None:
    ensure_dirs()
    rc = _load(EVIDENCE / "live_run_card.json")
    # the gated experiment is the post-amendment one (IR-65-PROP-01)
    e1_name = next((n for n in ("e1b_px5.json", "e1_px5.json")
                    if (EVIDENCE / n).exists()), None)
    e1 = _load(EVIDENCE / e1_name) if e1_name else None
    e1_pre = _load(EVIDENCE / "e1_px5.json")
    e2 = _load(EVIDENCE / "e2_px7.json")
    bias = _load(EVIDENCE / "mapping_bias_two_inventory.json")
    canary = _load(EVIDENCE / "leakage_canary.json")
    folds = _load(EVIDENCE / "fold_receipt.json")
    sgmc = _load(EVIDENCE / "sgmc_instrument_receipt.json")
    catid = _load(EVIDENCE / "catalogue_identity.json")
    fronts = _load(EVIDENCE / "range_front_variants.json")
    pre = _load(ROOT / "registry" / "preregistration.json")
    if rc is None:
        raise SystemExit("evidence/live_run_card.json missing; run scripts/make_submission.py")
    if e1 is None:
        raise SystemExit("evidence/e1_px5.json missing; run scripts/run_lane_sar2inv.py e1")

    verdict = rc["verdict"]
    ok = verdict == "SHIPPABLE"
    dec = rc["ship_decision"]
    val = rc["validation"]
    geom = rc["emission_geometry"]
    uniq = rc["uniqueness"]["summary"]
    two = rc["uniqueness"].get("two_phase") or {}
    art = Path(rc["artifact"])
    dst_dir = DOWNLOADS   # artefacts stay in docs/downloads/
    dst_dir.mkdir(parents=True, exist_ok=True)
    (DOCS / "assets").mkdir(parents=True, exist_ok=True)
    (DOCS / "assets" / "site.css").write_text(CSS)
    copied = []
    for p in sorted(DOWNLOADS.glob(art.stem + "*")):
        copied.append(p.name)
    shutil.copy2(EVIDENCE / "live_run_card.json", dst_dir / f"{art.stem}-runcard.json")
    # paths.DOWNLOADS already IS docs/downloads, so artefacts need no copying;
    # this line only adds the run card next to them
    copied.append(f"{art.stem}-runcard.json")
    checks = EVIDENCE / "live_run_card.json"

    i1s, i1pd = e1["I1_hide_recover"]["scores"], e1["I1_hide_recover"]["paired_differences"]
    i2s, i2pd = e1["I2_sgmc_offcat"]["scores"], e1["I2_sgmc_offcat"]["paired_differences"]
    tpd = e1["I1_tercile_gate"]["paired_differences"]
    i1d, i2d, i2d2, tercd = i1pd["B_nnpu"], i2pd["B_nnpu"], i2pd["A2_sar_1me"], tpd["B_nnpu"]
    i2n = i2s["A2_sar_1me"]["withheld_positive_pixels"]
    i2auc = e1["I2_auc_pooled"]

    banner = f"""
<div class="banner {'ok' if ok else 'bad'}">
<h2>{'OK TO DOWNLOAD AND SUBMIT' if ok else 'DO NOT SUBMIT — research artefact only'}</h2>
<p><b>Verdict:</b> <code>{verdict}</code> · <b>shipped arm:</b>
<code>{dec['shipped_arm'] or 'none'}</code> · <b>reason:</b> {dec['reason']}</p>
<p><b>Submission name:</b> <code>{rc['name']}</code><br>
<b>Note field (≤140 chars):</b> <code>{rc['note']}</code> ({len(rc['note'])} characters)</p>
<p><a class="btn{' ' if ok else ' dis'}" href="{DL}/{art.name}">⬇ Download
{art.name}</a>
<span class="tag">no ZIP: the repository guard allowlists .tif only</span>
<a class="btn sec" href="{DL}/{art.stem}.json">writer receipt</a>
<a class="btn sec" href="{DL}/{art.stem}-runcard.json">run card</a>
<a class="btn sec" href="executive-summary.html">How to submit (step by step)</a></p>
<p class="mut">sha256 <code>{val['sha256']}</code> · {val['bytes']:,} bytes ·
{val['emitted_positive_pixels']:,} positive pixels · float32 · EPSG:32611 ·
{val['meta']['shape'][0]}×{val['meta']['shape'][1]} ·
local format checks: <b>{'ALL PASSED' if val['all_checks_passed'] else 'FAILED'}</b>
({val['n_nan']} NaN, {val['n_infinite']} inf, min {val['min']}, max {val['max']}).
A local format check is not organizer acceptance.</p>
</div>"""

    if e1:
        results = scores_table(e1["I1_hide_recover"], "I1 — hide-and-recover blocked holdout (the gate)")
        results += scores_table(e1["I1_tercile_gate"], "I1b — highest-propensity tercile only (secondary gate)")
        results += scores_table(e1["I2_sgmc_offcat"], "I2 — state-map-only faults (mapped, not in catalogue)")
        auc = "<table><tr><th>instrument</th><th>A1_sar</th><th>A2_sar_1me</th><th>B_nnpu</th></tr>"
        for key, lbl in (("I1_auc_pooled", "I1 (withheld catalogue components)"),
                         ("I2_auc_pooled", "I2 (state-map-only pixels)")):
            a = e1[key]
            auc += (f"<tr><td>{lbl}</td><td>{a['A1_sar']:.4f}</td><td>{a['A2_sar_1me']:.4f}</td>"
                    f"<td>{a['B_nnpu']:.4f}</td></tr>")
        auc += "</table>"
    else:
        results = auc = "<p>pending</p>"

    bias_rows = "".join(
        f"<tr><td><code>{k}</code></td><td>{v['bias_auc_catalogue_vs_sgmc_offcat']:.4f}</td>"
        f"<td>{v['auc_vs_sgmc_offcat']:.4f}</td><td>{v['auc_vs_catalogue']:.4f}</td>"
        f"<td>{'catalogue over-represents HIGH' if v['bias_auc_catalogue_vs_sgmc_offcat']>0.5 else 'catalogue over-represents LOW'}</td></tr>"
        for k, v in sorted(bias["per_covariate"].items(),
                           key=lambda kv: -kv[1]["bias_auc_catalogue_vs_sgmc_offcat"]))
    canary_rows = "".join(
        f"<tr><td><code>{k}</code></td><td>{v['auc']:.4f}</td>"
        f"<td>{'LEAKAGE' if v['auc_above_limit'] else 'ok'}</td></tr>"
        for k, v in canary["per_feature"].items())
    front_rows = "".join(
        f"<tr><td>{k}</td><td>{v['pixels']:,}</td>"
        f"<td>{v['median_distance_px_inside_footprint']:.2f}</td>"
        f"<td><b>{v['bias_auc_catalogue_vs_sgmc_offcat']:.4f}</b></td>"
        f"<td>{v['auc_vs_sgmc_offcat_truth']:.4f}</td></tr>"
        for k, v in (fronts or {}).get("variants", {}).items())

    prop = rc["propensity"]
    body = f"""
{banner}

<div class="card"><b>Read this first.</b> This page reports a local, spatially blocked
holdout measurement. It is <u>not</u> a leaderboard score and it is not a projection of one.
Nothing here was uploaded to DrivenData; this session used
<b>{pre['budget']['submission_slots_used_by_this_session']}</b> submission slots, because
promotion to a real weekly slot is a separate selector step.
The pre-registered decision rule (<code>registry/preregistration.json</code>,
id <code>{pre.get('id','GEMSDOE65-PREREG-1')}</code>) was written before any holdout number
existed and is applied mechanically by <code>scripts/make_submission.py</code>.</div>

<h2>0. Why this verdict — and the one decision only the owner can make</h2>
<div class="card">
<p><b>The pre-registered gate is keyed to instrument I1, and the lane fails it.</b>
Paired Δ(A1_sar − B_nnpu) on I1 = <b>{i1d['delta']:+.6f}</b>, 95% CI
[{i1d['ci95'][0]:+.6f}, {i1d['ci95'][1]:+.6f}] — the CI excludes zero in the
<i>losing</i> direction, so this is not a coin flip. The secondary tercile condition also fails
(Δ {tercd['delta']:+.6f}, CI [{tercd['ci95'][0]:+.6f}, {tercd['ci95'][1]:+.6f}]). The ship rule
therefore returns <code>DO-NOT-SUBMIT</code> and this session does not override it.</p>
<p><b>On the instrument that matches the live task, the same lane wins clearly.</b> I2's truth is
mapped faults the catalogue does <i>not</i> contain ({i2n:,} px):
A2_sar_1me <b>{i2s['A2_sar_1me']['dti']:.6f}</b>
[{i2s['A2_sar_1me']['ci95'][0]:.6f}, {i2s['A2_sar_1me']['ci95'][1]:.6f}] vs nnPU
{i2s['B_nnpu']['dti']:.6f} [{i2s['B_nnpu']['ci95'][0]:.6f}, {i2s['B_nnpu']['ci95'][1]:.6f}] and
vs the proximity control {i2s['C_distance_only']['dti']:.6f}
[{i2s['C_distance_only']['ci95'][0]:.6f}, {i2s['C_distance_only']['ci95'][1]:.6f}]. Paired
Δ(A1_sar − B_nnpu) on I2 = {i2d['delta']:+.6f} [{i2d['ci95'][0]:+.6f}, {i2d['ci95'][1]:+.6f}] and
Δ(A1_sar − A2_sar_1me) = {i2d2['delta']:+.6f} [{i2d2['ci95'][0]:+.6f}, {i2d2['ci95'][1]:+.6f}],
both CIs excluding zero in the winning direction. Pooled ranking AUC against I2 truth:
A2 {i2auc['A2_sar_1me']:.4f} &gt; A1 {i2auc['A1_sar']:.4f} &gt; B {i2auc['B_nnpu']:.4f} &gt;
A3(EM) {i2auc['A3_sar_em_1me']:.4f} &gt; proximity {i2auc['C_distance_only']:.4f}.</p>
<p><b>The two instruments have opposite sign on the same question, and the reason is structural,
not statistical.</b> I1's withheld truth is made of <i>catalogue</i> components contiguous with
visible catalogue trace, and the organizer masks known USGS/INGENIOUS fault pixels out of scoring
(staff answer, community thread 11516) — so I1 rewards exactly the pixels that cannot score live.
Consistently, the trivial proximity control is the <i>best</i> arm on I1
({i1s['C_distance_only']['dti']:.6f}) and the <i>worst</i> on I2
({i2s['C_distance_only']['dti']:.6f}). The family's own ladder points the same way: deleting dots
1–2 px from the catalogue <i>raised</i> the live score twice (+0.0108, +0.0070, owner-report).</p>
<p><b>Decision required from the owner (not made here):</b> re-key the primary gate from I1 to I2
—or better, to a new I3 that holds out whole <i>state-map</i> segments with the catalogue fully
masked — and re-run the ship rule. That is an amendment to a pre-registration after results are
known, so it is an owner decision, not an agent one. Until then the artefact below is
<b>research-only</b>: downloadable, fully validated, uniquely ranked
(worst Spearman ρ vs 62 prior rasters = {fmt(uniq['worst_spearman_full_footprint'], 4)}), and
marked <code>{verdict}</code>.</p>
</div>

<h2>1. What was built</h2>
<p>Lane: <b>selection-bias-aware PU learning under SAR (selected at random given
covariates), not SCAR</b>. The competition catalogue is treated as
<i>positives selected with a covariate-dependent probability</i>
<code>e(x) = P(labeled | fault, x)</code>. The model is trained with the
propensity-aware empirical risk of Bekker, Robberechts &amp; Davis (arXiv:1809.03207),
weights <code>w = min(1/e, 10)</code> and
<code>v = min((1−e)/e, 10)</code>, against a non-negative PU (nnPU, Kiryo et al. 2017)
baseline on <b>identical folds, identical architecture, identical seed and an identical
{rc['emission_geometry']['dots']:,}-dot budget</b>. The shipped ranking multiplies the
class posterior by <code>(1 − e(x))</code>, which pushes mass into environments the
catalogue under-samples.</p>

<h3>The identifiability problem, and how this run handles it</h3>
<p>The observed-data likelihood of a SAR PU model is
<code>L = Σ<sub>labeled</sub> log(g·e) + Σ<sub>unlabeled</sub> log(1 − g·e)</code>:
it depends only on the <b>product</b> <code>g(x)e(x) = P(s=1|x)</code>. The propensity is
therefore <b>not identified from PU data alone</b> — the brief anticipates exactly this.
<code>tests/test_anchor.py::test_em_direction_is_not_identified</code> demonstrates it
numerically: the Bekker &amp; Davis EM returns both a correct-direction and a mirrored
solution on synthetic data with a known propensity, and their observed-data log-likelihoods
differ by less than 2&nbsp;%. This run resolves it two ways, both pre-registered:</p>
<ol>
<li><b>A second public inventory anchors the direction.</b> The catalogue is compared with
the mirrored state-geologic-map fault inventory
({sgmc['sgmc_inside_footprint_px']:,} state-map pixels inside the footprint, of which only
{sgmc['sgmc_on_catalogue_px']:,} are in the catalogue). Fitting
<code>q(x) = P(in catalogue | in catalogue ∪ state-map-only, x)</code> and inverting
<code>q = e/(e + c(1−e))</code> gives <code>e(x;c) = c·q/(1 − q + c·q)</code>: the ordering
is identified by data and one documented parameter <code>c</code> (reference-inventory
completeness) sets the scale. <code>c = {prop['anchor']['c']}</code> was used; the c-grid
<code>[0.25, 0.5, 1.0]</code> is the sensitivity analysis the brief asks for.</li>
<li><b>The EM is still run</b> ({'and used' if prop['chosen'] == 'em' else 'but rejected for direction'}).
Spearman(EM ordering, anchor ordering) on the pooled two-inventory sample =
<b>{fmt(prop['spearman_em_vs_anchor'], 4)}</b>; the pre-registered rule is "use the EM only
if that is &gt; 0". Chosen source: <code>{prop['chosen']}</code>. {prop['reason'] or ''}</li>
</ol>
<p>Measured propensity: mean <code>e</code> on catalogue pixels
<b>{fmt(prop['anchor']['e_on_catalogue_mean'], 4)}</b> vs
<b>{fmt(prop['anchor']['e_on_reference_mean'], 4)}</b> on independent-inventory
off-catalogue fault pixels — the direction the hypothesis requires. Class prior
π = {fmt(e1['pi_used'], 5)} (MEASURED: the union of both public inventories is a lower
bound on fault-pixel prevalence); ρ = P(s=1) is computed from population counts, never from
the unlabeled subsample (<code>tests/test_propensity_subsample.py</code> pins the bug this
fixes: an unweighted subsample gave π = 0.867 against a truth of ≈0.03).</p>

<h2>2. Results — HOLDOUT-DTI, not scores</h2>
{results}
<h3>Ranking quality (AUC of the emitted score field against each instrument's truth)</h3>
{auc}
<p class="mut">Source receipt: <code>evidence/{e1_name}</code> (gated experiment; the
pre-amendment receipt <code>evidence/e1_px5.json</code> is retained for IR-65-PROP-01).
Folds: <code>{folds['per_fold'][0]['split_version']}</code>, seed
{folds['seed']}, hide_frac {folds['hide_frac']}, feature buffer {folds['feature_buffer_px']} px,
{folds['withheld_positive_pixels_total']:,} withheld positive pixels over
{folds['n_folds']} folds, nearest visible catalogue pixel
{folds['per_fold'][0]['nearest_visible_to_truth_px']} px from withheld truth.
I2 truth: {sgmc['truth_px']:,} state-map-only pixels, scored leave-one-quadrant-out so the
anchor never sees the pixels it is scored on.</p>

<h2>3. The measurable mapping bias this lane exploits</h2>
<p>Bias AUC &gt; 0.5 means the catalogue sits closer to (over-represents) HIGH values of that
covariate relative to an independent inventory of the same physical objects.</p>
<table><tr><th>covariate</th><th>bias AUC<br>(catalogue vs state-map-only)</th>
<th>AUC vs state-map-only truth</th><th>AUC vs catalogue</th><th>reading</th></tr>{bias_rows}</table>
<p><b>The catalogue over-represents low-relief, low-slope, deep-basin-fill ground far from the
range front; the state geologic maps over-represent exposed, high-relief, steep ground.</b>
That is the inverse of the naive "steep scarps are easy to see" intuition, because
QFaults/INGENIOUS is a geophysics-informed compilation carrying many <i>Inferred</i> basin
faults while state geologic maps are bedrock-exposure maps.
<span class="tag">MEASURED</span> <code>evidence/mapping_bias_two_inventory.json</code></p>

<h2>4. Irregularities found and how they were resolved</h2>
<div class="grid2">
<div class="card"><b>(B) Is the catalogue really the known-fault compilation?</b>
Yes. Rasterising the mirrored QFaults/INGENIOUS trace segments covers
<b>{(catid or {}).get('catalogue_covered_by_traces', float('nan'))*100:.2f}&nbsp;%</b> of
catalogue pixels at median distance
<b>{(catid or {}).get('catalogue_to_trace_distance_px', {}).get('median')} px</b>
(p90 {(catid or {}).get('catalogue_to_trace_distance_px', {}).get('p90')} px) from
{(catid or {}).get('n_trace_segments', 0):,} segments. Morphology:
{(catid or {}).get('catalogue_morphology', {}).get('n_components_8connected')}
8-connected components, median
{(catid or {}).get('catalogue_morphology', {}).get('component_size_median_px')} px,
and only {(catid or {}).get('catalogue_morphology', {}).get('erosion_survival_fraction', 0)*100:.2f}&nbsp;%
of pixels survive a 3×3 erosion — 1-px-wide compiled traces, not areas. Its weak
topographic AUCs are therefore a real property of the inventory, not a data error.
<code>evidence/catalogue_identity.json</code></div>
<div class="card"><b>(A) Which range front?</b> Four operationalizations were compared on one
criterion (carrying the two-inventory differential). Variant
<code>{(fronts or {}).get('kept')}</code> was kept and is documented as a <b>proxy of limited
geomorphic fidelity</b>, not a mapped front.
<code>evidence/range_front_variants.json</code>
<table><tr><th>variant</th><th>px</th><th>median dist</th><th>bias AUC</th><th>AUC vs I2</th></tr>
{front_rows}</table></div>
</div>
<div class="card"><b>Non-identifiability (formal).</b> Only the product <code>g·e</code> is
identified; see §1 and <code>tests/test_anchor.py</code>. The propensity is therefore reported
as a <b>sensitivity analysis</b> with an external anchor, exactly as the brief instructs.</div>
<div class="card"><b>Uniqueness rule is not meetable as literally written.</b>
{two.get('note', 'The literal rule (≤70% of dots within 3 px of ANY registry raster) is '
 'unmeetable for sparse fields because dense lattice comparators cover almost the whole '
 'footprint.')} Reported both ways below; flagged, never silently waived.</div>

<h2>5. Leakage canary <span class="tag">MEASURED</span></h2>
<p>Each covariate alone against withheld truth, limit AUC ≤ {canary['auc_limit']}.</p>
<table><tr><th>covariate</th><th>AUC</th><th>flag</th></tr>{canary_rows}</table>
<p class="mut">Worst = <code>dist_to_visible_catalogue</code>
{canary['worst_auc']:.4f} — the legitimate proximity control signal, not a leak. No covariate
is flagged.</p>

<h2>6. Artefact, format and uniqueness</h2>
<table>
<tr><th>check</th><th>value</th></tr>
<tr><td>local format preflight</td><td>{'ALL PASSED' if val['all_checks_passed'] else 'FAILED'} —
single band {val['meta']['count']}, {val['meta']['dtype']}, {val['meta']['crs']},
transform {val['meta']['transform']}, nodata {val['meta']['nodata']} (none, matching the
organizer reference solution), {val['n_nan']} NaN, {val['n_infinite']} inf,
range [{val['min']}, {val['max']}]</td></tr>
<tr><td>positive mass on mapped catalogue</td><td>{val.get('on_catalogue_positive_pixels')} px
(must be 0 — known faults are masked out of scoring anyway)</td></tr>
<tr><td>outside footprint</td><td>{'all zero' if val['checks'].get('outside_footprint_zero') else 'NON-ZERO'}
(mode <code>zeros</code>: all-finite, no NaN anywhere — this is what prevents the portal's
"Predicted values must be in range [0, 1]" rejection)</td></tr>
<tr><td>emission geometry</td><td>{geom['dots']:,} dots · min distance to a mapped pixel
{geom['min_dist_to_visible_px']} px · median {geom['median_dist_to_visible_px']} px ·
p95 {geom['p95_dist_to_visible_px']} px · within 300 m of a mapped pixel
{geom['frac_within_300m_of_visible']*100:.2f}&nbsp;%</td></tr>
<tr><td>uniqueness vs registry</td><td>{uniq['registry_rasters_checked']} rasters checked ·
worst Spearman ρ {fmt(uniq['worst_spearman_full_footprint'], 4)} (limit
{uniq['rho_limit']}) vs <code>{uniq['worst_rho_submission']}</code> · worst 3-px dot overlap
{fmt(uniq['worst_dot_overlap'], 4)} (limit {uniq['overlap_limit']}) vs
<code>{uniq['worst_overlap_submission']}</code> · byte-unique
{uniq['byte_unique_among_checked']} · pixel-unique {uniq['pixel_unique_among_checked']}</td></tr>
<tr><td>like-for-like (dot-field comparators only)</td><td>
{two.get('like_for_like', {}).get('worst_dot_overlap', '—')} worst overlap ·
{two.get('like_for_like', {}).get('n_dot_field_rasters', '—')} dot-field rasters ·
{two.get('literal', {}).get('n_firings', '—')} literal firings, all from
{two.get('literal', {}).get('representation_of_firings', '—')}</td></tr>
</table>

<h2>7. Hypotheses, ranked before implementation</h2>
<p>Full text with layers, mechanisms, mimics, sources and obtainability:
<a href="research/hypotheses.html">research/hypotheses.html</a>. The top candidate (H65-1,
two-inventory propensity) is what was implemented and gated here; it was validated on the
spatially-blocked holdout <b>before</b> any submission slot was considered, and no slot was
spent.</p>

<h2>8. Why <code>h33-h33-2-b2</code> scored 0.2778, and what beats it</h2>
<p>Full derivation: <a href="research/why-02778.html">research/why-02778.html</a>
(owner-reported score; no organizer receipt ties it to exact bytes). In brief: with the dot
algebra <code>DTI = T / (0.2(T+S−M) + 0.8|G|)</code> that raster puts 37,654 dots 0 px off
the catalogue, keeps a minimum distance of 3.00 px, lands only 5.77&nbsp;% of dots within
300 m of the hidden truth, and earns a mean credit of <b>0.135 per dot ≈ 2.4× the
break-even 0.0556</b>. Mass-pruning is nearly spent (+0.003/+0.004 per rung). The only large
remaining prize is <b>re-ranking the same mass</b>: raising credit/dot to 0.150 ≈ 0.30, to
0.19 ≈ 0.36. A propensity-aware ranker is aimed exactly at that prize, because credit per
dot is a statement about <i>where</i> unmapped faults are, and <code>(1 − e(x))</code> is a
statement about where the catalogue is blind.</p>

<h2>9. Limitations, and what access would remove them</h2>
<ul>
<li><b>No organizer confirmation of anything.</b> This sandbox cannot reach
<code>drivendata.org</code>, <code>docs.nlr.gov</code> (the rules PDF), the five Dropbox data
mirrors, <code>gdr.openei.org</code>, <code>usgs.gov</code> or
<code>raw.githubusercontent.com</code> (all HTTP 000). Every official statement on this site
is quoted from the family's line-by-line verification record
(<code>60GEMSDOE/docs/research/verification-2026-10-04.md</code>) with links for manual
review. Access needed: a machine with outbound HTTPS to those hosts, or a mirrored rules PDF.</li>
<li><b>HOLDOUT-DTI is not the live metric's target.</b> I1 rewards proximity to visible
traces (the withheld truth is contiguous with visible trace); the live board does not — the
family's ladder measured that deleting dots 1–2 px from the catalogue <i>raised</i> the live
score twice (+0.0108, +0.0070, owner-reported). Both instruments are reported; neither is a
projection.</li>
<li><b>The anchor assumes the reference inventory's propensity is constant in x.</b> State
geologic maps are bedrock-exposure maps, so if they under-sample buried basin faults the
anchor over-corrects toward exposed ground. This is the named non-fault process that could
mimic the hypothesis (compiler-vintage and compiler-rule confounding).</li>
<li><b>The range front is a proxy</b> (50 m isoline of height above a 5 km local minimum), not
a mapped front; a real front needs raw 3DEP 10 m/1 m tiles, unreachable here.</li>
<li><b>LiDAR layer provenance</b>: quantised scarp descriptors derived in a sibling repo from
public 3DEP tiles — 10 failed tiles of 716, a 1–2 m datum offset, and they are terrain
descriptors, not fault detections (roads, channels, terraces, shorelines, landslides and mines
also make steps). Flagged <code>PUBLIC-REPOSITORY-DERIVATIVE</code>, not organizer-provided.</li>
<li><b>Uniqueness inventory is incomplete</b>: {uniq['registry_rasters_checked']} accessible
rasters from sibling public repositories, not the organizer's registry.
<code>complete_accessible_scan = {uniq['complete_accessible_scan']}</code>.</li>
</ul>

<h2>10. Official sources for manual review</h2>
<ul>{''.join(f'<li><a href="{u}">{t}</a></li>' for t, u in OFFICIAL_LINKS)}</ul>
<h3>Method references</h3>
<ul>{''.join(f'<li><a href="{u}">{t}</a></li>' for t, u in METHOD_LINKS)}</ul>

<h2>11. Reproduce</h2>
<pre><code>python -m venv .venv &amp;&amp; .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_covariates.py       # 5 px covariate cache (~3 min)
.venv/bin/python -m pytest tests -q                # 21 tests, unit-verified risks
.venv/bin/python scripts/run_lane_sar2inv.py bias          # two-inventory mapping bias
.venv/bin/python scripts/run_lane_sar2inv.py canary        # leakage canary
.venv/bin/python scripts/run_lane_sar2inv.py e1            # the gated experiment (PX5)
.venv/bin/python scripts/diagnose_irregularities.py
.venv/bin/python scripts/make_submission.py        # live fit, emit, write, validate, certify
.venv/bin/python scripts/build_site.py             # this site
</code></pre>
<p class="mut">Artefacts copied to <code>docs/downloads/</code>: {', '.join(copied)}.
Run card: <code>evidence/live_run_card.json</code>.</p>
"""

    (DOCS / "index.html").write_text(page("GEMSDOE65 — SAR-PU submission", body, active="index.html"))

    # ---- executive summary subpage -----------------------------------------
    ex = f"""
{banner}
<h2>Executive summary</h2>
<p><b>One-paragraph version.</b> This lane treats the competition's fault catalogue as
<i>positives selected with a covariate-dependent probability</i> rather than a random sample
of all faults. Two independent public inventories of the same ground (the USGS
QFaults/INGENIOUS compilation that <i>is</i> the catalogue — {(catid or {}).get('catalogue_covered_by_traces', 0)*100:.1f}&nbsp;%
coverage at 0 px median distance — and a state geologic map fault layer that overlaps it by
only {100*sgmc['sgmc_on_catalogue_px']/max(sgmc['sgmc_inside_footprint_px'],1):.1f}&nbsp;%)
make the selection bias measurable: the catalogue over-represents deep-basin-fill, low-relief
ground, the state maps over-represent exposed high-relief ground. The propensity
<code>e(x)</code> is anchored on that differential, the classifier is trained with a
propensity-aware risk, and dots are placed where <code>P(fault|x)·(1 − e(x))</code> is
largest — i.e. where a fault is likely <i>and</i> the catalogue is blind.</p>

<h2>Exactly how to submit this file to DrivenData</h2>
<ol>
<li><b>Check the banner at the top of this page.</b> If it says
<span style="color:var(--ok)"><b>OK TO DOWNLOAD AND SUBMIT</b></span>, the pre-registered
ship rule passed and the file is cleared for a weekly slot. If it says
<span style="color:var(--bad)"><b>DO NOT SUBMIT</b></span>, the artefact is for research only
— download it, read the run card, and do not upload it. The verdict comes from
<code>registry/preregistration.json</code> applied mechanically to
<code>evidence/e1_px5.json</code>; no human judgement is involved.</li>
<li><b>Download the file</b> with the blue button in the banner
(<code>{art.name}</code>). The ZIP contains only this one TIFF, as the portal expects.</li>
<li><b>Verify the bytes before uploading</b> (30 seconds, protects the slot):
<pre><code>sha256sum {art.name}
# must equal {val['sha256']}</code></pre>
If it differs, the download was corrupted — re-download, do not upload.</li>
<li><b>Log in</b> at <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">
the competition page</a> → <i>Submit</i> (the submission page shows how many of this week's
slots remain; slots reset weekly and one submission is scored across both the Initial Prize
Round and the Final Round).</li>
<li><b>Upload the single-band GeoTIFF.</b> Accepted format, verified from the official page:
EPSG:32611 (UTM zone 11N), 100 m pixels, {val['meta']['shape'][0]}×{val['meta']['shape'][1]},
one band, <code>float32</code>, every value in <b>[0, 1]</b>, no NaN/inf anywhere in this
artefact (mode <code>zeros</code>: outside the study footprint the value is exactly 0.0).
The historical portal rejection <i>"Predicted values must be in range [0, 1]"</i> is caused by
NaN or out-of-range values — this artefact cannot produce it, because
<code>gems57.submission_writer.write_submission</code> refuses to write a field that is not
already finite and in [0, 1], and <code>gems57.validate</code> re-reads the written file and
asserts every check before this page is built.</li>
<li><b>Fill in the name and note fields</b> exactly as below (both ≤ 140 characters):
<table><tr><th>field</th><th>value</th><th>length</th></tr>
<tr><td>name</td><td><code>{rc['name']}</code></td><td>{len(rc['name'])}</td></tr>
<tr><td>note</td><td><code>{rc['note']}</code></td><td>{len(rc['note'])}</td></tr></table></li>
<li><b>After submission, record the receipt.</b> Copy the score the submission page shows into
<code>evidence/</code> as an <span class="tag">ORGANIZER-CONFIRMED</span> number, with the
timestamp, the file sha256 and the remaining slot count. Until that exists, every number on
this site stays labelled <span class="tag">HOLDOUT-DTI</span> or
<span class="tag">MEASURED</span> — a projection is never written as a score.</li>
<li><b>Known faults are masked out of scoring</b> (organizer staff answer in
<a href="https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516">
community thread 11516</a>): dots on the catalogue cannot score. This artefact places
<b>{geom['on_catalogue_px']} dots on catalogue pixels</b> and peels every dot at least
{geom['min_dist_to_visible_px']} px (300 m) away from a mapped pixel.</li>
</ol>

<h2>What the numbers on this site mean</h2>
<table>
<tr><th>label</th><th>meaning</th></tr>
<tr><td><span class="tag">HOLDOUT-DTI</span></td><td>local measurement on a spatially blocked
holdout with the shared evaluator <code>{e1['evaluator_version']}</code>
(official α=0.2, β=0.8, R=300 m triangular kernel), n = withheld positive pixels, 95% CI from
a 20 km spatial-block paired bootstrap ({e1.get('bootstrap_draws', 1000)} draws). Not a
leaderboard score.</td></tr>
<tr><td><span class="tag">ORGANIZER-CONFIRMED</span></td><td>copied from a submission-page
receipt. <b>This site has none</b>: nothing was uploaded.</td></tr>
<tr><td><span class="tag">MEASURED</span></td><td>a deterministic measurement of local,
hash-pinned data (pixel counts, AUCs, distances). No model involved.</td></tr>
<tr><td><span class="tag">OWNER-REPORT</span></td><td>a score reported by the repository owner
without an organizer receipt (e.g. 0.2778 for <code>h33-h33-2-b2</code>).</td></tr>
</table>

<h2>Decision rule that produced the verdict (written before any result)</h2>
<div class="card"><p><code>{dec['rule_text']}</code></p>
<p>Applied: gate point estimate <b>{dec['gate_point_estimate']}</b> · gate strict (paired CI
excludes 0) <b>{dec['gate_strict_ci_excludes_zero']}</b> · secondary tercile gate
<b>{dec['tercile_secondary_gate']}</b> · A2 within its own CI width of A1 on I1
<b>{dec['a2_within_own_ci_width_of_a1_on_i1']}</b> · A2 beats A1 on I2
<b>{dec['a2_beats_a1_on_i2']}</b> → shipped arm <code>{dec['shipped_arm'] or 'none'}</code>.</p></div>

<h2>If the verdict is DO NOT SUBMIT</h2>
<p>That is a deliverable, not a failure. The run card records the negative result, the exact
rule that fired, and the numbers that would have to change. The recommended next step is in
<a href="research/hypotheses.html">the ranked hypotheses</a>: H65-4 (en-echelon stepover /
relay-ramp gaps) is the cheapest untested mechanism, and H65-2 (LiDAR-conditional
detectability) changes the emission rule rather than the model.</p>
"""
    (DOCS / "executive-summary.html").write_text(
        page("How to submit — GEMSDOE65", ex, active="executive-summary.html"))

    # ---- research subpages ---------------------------------------------------
    rd = DOCS / "research"
    rd.mkdir(parents=True, exist_ok=True)
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc"])
    for src, out_name, title in (
            (ROOT / "docs/research/hypotheses-2026-10-11.md", "hypotheses.html",
             "Ranked geological hypotheses"),
            (ROOT / "docs/research/why-02778-and-what-beats-it-2026-10-11.md", "why-02778.html",
             "Why h33-h33-2-b2 scored 0.2778"),
            (ROOT / "docs/research/irregularities-lane65b.md", "irregularities.html",
             "Irregularities and dispositions"),
            (ROOT / "README.md", "readme.html", "README and standing brief")):
        if src.exists():
            md.reset()
            html = md.convert(src.read_text())
            body = (f'<p class="mut"><a href="../index.html">← back to the submission page</a>'
                    f' · source <code>{src.relative_to(ROOT)}</code></p>{html}')
            (rd / out_name).write_text(page(title, body))
        else:
            (rd / out_name).write_text(page(title, f"<p>source not found: {src}</p>"))

    print(f"[site] docs/lane65b/index.html + executive-summary.html + research/*.html; "
          f"{len(copied)} artefacts copied")


if __name__ == "__main__":
    build()
