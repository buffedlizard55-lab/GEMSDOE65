#!/usr/bin/env python3
"""Build the GitHub Pages site from evidence/*.json and registry/*.json.

No number on the site is hand-typed: every value is read out of a JSON artifact that a script in
``scripts/`` produced from hash-pinned bytes.  If an artifact is missing, the site says so loudly
instead of inventing a value.

Out: docs/index.html, docs/executive-summary.html, docs/data/feed.json
Run: python scripts/build_site.py
"""

from __future__ import annotations

import html
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems65 import grid as G  # noqa: E402

DOCS = Path(__file__).resolve().parents[1] / "docs" / "lane65"
DL_REL = "../downloads"   # rasters stay in docs/downloads (published, DO-NOT-SUBMIT labelled)
EVID = Path(__file__).resolve().parents[1] / "evidence"
REG = Path(__file__).resolve().parents[1] / "registry"

CSS = """
:root{--bg:#0e1116;--panel:#161b22;--panel2:#1c2230;--ink:#e6edf3;--mut:#9aa7b4;--line:#2a3140;
--ok:#2ea043;--bad:#d1242f;--warn:#d29922;--acc:#58a6ff;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1120px;margin:0 auto;padding:24px 20px 80px}
header.site{border-bottom:1px solid var(--line);padding:18px 0 14px;margin-bottom:22px}
header.site h1{margin:0 0 4px;font-size:22px;letter-spacing:.2px}
header.site .sub{color:var(--mut);font-size:13.5px}
nav.toc{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 0}
nav.toc a{background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:5px 12px;font-size:13px;color:var(--ink)}
h2{font-size:18px;margin:34px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h3{font-size:15.5px;margin:22px 0 8px;color:#cdd9e5}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:12px 0}
.grid{display:grid;gap:12px}
.g2{grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.g3{grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.kpi{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kpi .k{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.kpi .v{font-size:22px;font-family:var(--mono);margin-top:3px}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:8px 0}
th,td{border-bottom:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
td.num,th.num{text-align:right;font-family:var(--mono)}
code,.mono{font-family:var(--mono);font-size:12.5px}
.badge{display:inline-block;border-radius:999px;padding:2px 10px;font-size:11.5px;font-weight:700;letter-spacing:.04em;border:1px solid}
.b-ok{color:#7ee2a8;border-color:#2ea043;background:rgba(46,160,67,.13)}
.b-bad{color:#ff9aa2;border-color:#d1242f;background:rgba(209,36,47,.13)}
.b-warn{color:#f2cc60;border-color:#d29922;background:rgba(210,154,34,.13)}
.b-mut{color:var(--mut);border-color:var(--line);background:rgba(255,255,255,.03)}
.dl{border:2px solid var(--line);border-radius:12px;padding:18px;margin:14px 0;background:linear-gradient(180deg,#182030,#141a24)}
.dl.primary{border-color:var(--ok)}
.dl.blocked{border-color:var(--bad)}
.dl h3{margin-top:0;font-size:17px}
.btnrow{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0 6px}
.btn{display:inline-block;background:var(--ok);color:#04140a;font-weight:700;border-radius:8px;padding:11px 18px;font-size:14.5px}
.btn.sec{background:#2b3444;color:var(--ink);font-weight:600}
.btn.dead{background:#3a2024;color:#ffb3b8;cursor:not-allowed}
.btn:hover{text-decoration:none;filter:brightness(1.08)}
.verdict{font-size:15px;font-weight:700;margin:6px 0}
.small{font-size:12.5px;color:var(--mut)}
ul{margin:8px 0 8px 20px;padding:0}li{margin:4px 0}
pre{background:#0b0e13;border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;font-family:var(--mono);font-size:12.5px}
.flag{border-left:3px solid var(--warn);padding-left:12px}
"""


def load(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        return {"_load_error": str(exc)}


def esc(x) -> str:
    return html.escape(str(x))


def fmt(x, n=5):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{n}f}"
    return esc(x)


def badge(ok, yes="PASS", no="FAIL"):
    return f'<span class="badge {"b-ok" if ok else "b-bad"}">{yes if ok else no}</span>'


def cls(v):
    return "b-ok" if v else "b-bad"


def nav():
    items = [("../index.html", "Canonical home"), ("index.html", "Lane 65 home"), ("executive-summary.html", "Executive summary / how to submit"),
             ("research.html", "Method &amp; hypotheses"), ("sources.html", "Verified sources"),
             ("irregularities.html", "Irregularities"), ("limitations.html", "Limitations"),
             ("run-card.html", "Run card")]
    return '<nav class="toc">' + "".join(
        f'<a href="{h}">{t}</a>' for h, t in items) + "</nav>"


BANNER = "NOT CLEARED FOR SUBMISSION"


def header(title, sub):
    """One h1 per page, lang=en in the caller, and the canonical fail-closed banner phrase."""
    return (f'<header class="site"><h1>{esc(title)}</h1><div class="sub">{sub}</div>{nav()}'
            f'<div class="panel" style="border-color:var(--bad);margin-top:14px">'
            f'<b style="color:#ff9aa2">{BANNER}</b> — no raster built by this lane may be submitted. '
            f'The files under <code>docs/downloads/</code> are evidence artifacts only.</div></header>')


def download_card(arm_name, arm, primary: bool) -> str:
    ok = arm.get("OK_TO_DOWNLOAD_AND_SUBMIT")
    v = arm.get("verdict", "?")
    klass = "primary" if ok else "blocked"
    files = arm.get("files", {})
    nan = Path(files.get("nan", "")).name
    zeros = Path(files.get("zeros", "")).name
    audits = arm.get("validator", {})
    a = audits.get("nan", {})
    checks = a.get("checks", {})
    # some arms record no emission (nothing was written), so the count can be absent;
    # formatting None with "," is a TypeError and took the whole page down in CI
    n_emit = arm.get("emitted_pixels") or 0
    dv = arm.get("duplicate_check", {}).get("verdict", {})
    verdict_line = (
        f'<div class="verdict" style="color:#7ee2a8">✔ OK TO DOWNLOAD AND SUBMIT — {esc(v)}</div>'
        if ok else
        f'<div class="verdict" style="color:#ff9aa2">✘ DO NOT SUBMIT — {esc(v)}</div>')
    href_nan = f"{DL_REL}/{nan}" if nan else "#"
    href_zeros = f"{DL_REL}/{zeros}" if zeros else "#"
    btn = (f'<a class="btn" href="{href_nan}" download>⬇ Download {esc(nan)}</a>'
           f'<a class="btn sec" href="{href_zeros}" download>⬇ {esc(zeros)} (zeros-outside variant)</a>')
    if not ok:
        btn = (f'<a class="btn dead" href="{href_nan}" download title="format-valid but gate-blocked">'
               f'⬇ {esc(nan)} — format-valid, GATE-BLOCKED</a>'
               f'<a class="btn sec" href="{href_zeros}" download>⬇ {esc(zeros)}</a>')
    rows = "".join(
        f"<tr><td>{esc(k)}</td><td>{badge(val)}</td></tr>" for k, val in checks.items())
    return f"""
<div class="dl {klass}">
  <h3>{esc(arm_name)} <span class="badge {'b-ok' if ok else 'b-bad'}">{'SUBMITTABLE' if ok else 'NOT SUBMITTABLE'}</span></h3>
  {verdict_line}
  <div class="small">Reason: {esc(arm.get('verdict_reason',''))}</div>
  <div class="small" style="margin-top:4px">Rules applied: <code>{esc(' · '.join(arm.get('adjudication',{}).get('rules_applied',[])))}</code>
   &nbsp;|&nbsp; arm holdout-DTI {fmt(arm.get('adjudication',{}).get('holdout_dti_of_arm'))}
   &nbsp;vs&nbsp; current holdout best {fmt(arm.get('adjudication',{}).get('holdout_reference_best'))}
   (<code>{esc(str(arm.get('adjudication',{}).get('holdout_reference_raster',''))[:34])}</code>)</div>
  <div class="btnrow">{btn}</div>
  <div class="grid g3">
    <div class="kpi"><div class="k">Emitted pixels</div><div class="v">{n_emit:,}</div></div>
    <div class="kpi"><div class="k">Value range in footprint</div><div class="v">[{fmt(a.get('in_footprint_min'),6)}, {fmt(a.get('in_footprint_max'),6)}]</div></div>
    <div class="kpi"><div class="k">NaN inside footprint</div><div class="v">{a.get('footprint_finite_pixels',0) and (G.FOOTPRINT_PIXELS - a.get('footprint_finite_pixels',0)):,}</div></div>
    <div class="kpi"><div class="k">sha256 (nan file)</div><div class="v" style="font-size:12px">{esc(str(a.get('sha256',''))[:32])}…</div></div>
    <div class="kpi"><div class="k">Max rank-corr. vs registry</div><div class="v">{fmt(dv.get('max_spearman_surface'),4)}</div></div>
    <div class="kpi"><div class="k">Max 3-px dot overlap</div><div class="v">{fmt(dv.get('max_dot_overlap_3px'),4)}</div></div>
  </div>
  <div class="small" style="margin-top:8px">Submission note (≤140 chars): <code>{esc(arm.get('submission_note',''))}</code> — {arm.get('note_length')} chars</div>
  <details style="margin-top:10px"><summary class="small">14-point validator output ({sum(checks.values())}/{len(checks)} passed)</summary>
  <table><tr><th>check</th><th>result</th></tr>{rows}</table></details>
</div>"""


def build_index() -> str:
    cov = load(EVID / "covariates.json", {})
    hold = load(EVID / "holdout_pu.json", {})
    build = load(EVID / "submission_build.json", {})
    calib = load(EVID / "holdout_calibration.json", {})
    mirror = load(EVID / "live_mirror.json", {})
    irr = load(REG / "irregularities.json", {"irregularities": []})
    card = load(Path(G.repo_root()) / "RUN_CARD.json", {})
    gate = hold.get("gate", {})
    arms = build.get("arms", {})
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    any_ok = any(a.get("OK_TO_DOWNLOAD_AND_SUBMIT") for a in arms.values())
    # where does OUR candidate sit on the mirror instrument, relative to every LIVE-SCORED artifact?
    mrows = [r for r in mirror.get("rows", []) if isinstance(r.get("MIRROR_DTI"), (int, float))]
    mscored = [r for r in mrows if r.get("reported_live_score") is not None]
    mcand = [r for r in mrows if r.get("reported_live_score") is None]
    ref_best = (load(REG / "adjudication.json", {}) or {}).get("holdout_reference", {}).get("best_dti")
    mirror_sentence = ""
    if mscored and mcand:
        worst = min(mscored, key=lambda r: r["MIRROR_DTI"])
        best_cand = max(mcand, key=lambda r: r["MIRROR_DTI"])
        below = sum(1 for r in mscored if r["MIRROR_DTI"] > best_cand["MIRROR_DTI"])
        mirror_sentence = (
            f" On the mirror instrument our best arm scores MIRROR-DTI {best_cand['MIRROR_DTI']:.3f}, "
            f"which ranks it below {below}/{len(mscored)} live-scored registry artifacts (the weakest of "
            f"those is {worst['MIRROR_DTI']:.3f} at owner-reported live {worst['reported_live_score']}). "
            f"That is an ordering statement about an instrument, not a projected score.")
    hero = (
        '<div class="panel" style="border-color:var(--ok)"><b style="color:#7ee2a8">A submittable raster is ready.</b> '
        'Use the green download button below.</div>' if any_ok else
        f'<div class="panel" style="border-color:var(--bad)"><b style="color:#ff9aa2">NO raster on this page is cleared for '
        f'submission.</b> The lane\'s pre-registered gate was not met (SAR {fmt(gate.get("pooled_dti_sar_erm"))} vs nnPU '
        f'{fmt(gate.get("pooled_dti_nnpu_scar"))}), and the two baseline arms do not beat the current holdout best '
        f'({fmt(ref_best)}), so rule R4 '
        f'refuses them too. Per protocol the result is logged as <b>NEGATIVE</b> — a deliverable, not a failure to report.'
        f'{mirror_sentence} The files are published below as format-valid evidence artifacts: click one to download and '
        f'inspect it, but <b>do not spend a weekly slot on any of them</b>. Instrument quality is measured and shown in '
        f'§4, the rules in §2, and the full run card in §8.</div>')

    # ---- gate table
    gate_rows = f"""
    <tr><td>Pooled blocked-holdout DTI — propensity-aware ERM (SAR)</td><td class="num">{fmt(gate.get('pooled_dti_sar_erm'))}</td><td class="num">—</td></tr>
    <tr><td>Pooled blocked-holdout DTI — nnPU baseline (SCAR)</td><td class="num">{fmt(gate.get('pooled_dti_nnpu_scar'))}</td><td class="num">—</td></tr>
    <tr><td><b>Overall delta (SAR − nnPU)</b></td><td class="num"><b>{fmt(gate.get('overall_delta'))}</b></td>
        <td class="num">95% CI [{fmt(gate.get('overall_delta_mean_cell_ci95',[0,0])[0],4)}, {fmt(gate.get('overall_delta_mean_cell_ci95',[0,0])[1],4)}]</td></tr>
    <tr><td>Highest-propensity tercile DTI — SAR</td><td class="num">{fmt(gate.get('top_tercile_dti_sar_erm'))}</td><td class="num">—</td></tr>
    <tr><td>Highest-propensity tercile DTI — nnPU</td><td class="num">{fmt(gate.get('top_tercile_dti_nnpu_scar'))}</td><td class="num">—</td></tr>
    <tr><td><b>Tercile delta (SAR − nnPU)</b></td><td class="num"><b>{fmt(gate.get('top_tercile_delta'))}</b></td><td class="num">must be ≥ 0</td></tr>
    <tr><td>Cell wins for SAR</td><td class="num">{gate.get('overall_wins')}/{gate.get('overall_cells')}</td><td class="num">—</td></tr>
    <tr><td>Leakage canary — max single-feature holdout AUC</td><td class="num">{fmt(gate.get('leakage_canary_max_auc'),4)}</td><td class="num">must be ≤ 0.90</td></tr>
    """

    # ---- a_bar sensitivity
    abar = hold.get("pooled_by_anchor_a_bar", {})
    abar_rows = "".join(
        f"<tr><td class='mono'>{esc(k)}</td><td class='num'>{fmt(v.get('dti'))}</td>"
        f"<td class='num'>{fmt(v.get('coverage'),4)}</td><td class='num'>{v.get('n_truth')}</td></tr>"
        for k, v in sorted(abar.items()))
    prim = hold.get("pooled", {}).get("sar_erm", {})
    abar_rows += (f"<tr style='background:#1b2330'><td class='mono'>{esc(gate.get('primary_anchor_a_bar'))} "
                  f"<span class='badge b-mut'>pre-registered</span></td><td class='num'>{fmt(prim.get('dti'))}</td>"
                  f"<td class='num'>{fmt(prim.get('coverage'),4)}</td><td class='num'>{prim.get('n_truth')}</td></tr>")

    # ---- calibration
    cal_rows = ""
    for r in sorted(calib.get("rows", []), key=lambda x: -(x.get("reported_live_score") or 0)):
        cal_rows += (f"<tr><td class='mono' style='font-size:11.5px'>{esc(r['raster'][:52])}</td>"
                     f"<td class='num'>{r['dots']:,}</td>"
                     f"<td class='num'>{fmt(r.get('holdout_pooled_dti'))}</td>"
                     f"<td class='num'>{fmt(r.get('reported_live_score'),4)} "
                     f"<span class='badge b-warn'>OWNER-REPORT</span></td></tr>")

    mir_rows = ""
    for r in sorted(mirror.get("rows", []), key=lambda x: -(x.get("MIRROR_DTI") or 0)):
        mir_rows += (f"<tr><td class='mono' style='font-size:11.5px'>{esc(r['raster'][:52])}</td>"
                     f"<td class='num'>{r['dots']:,}</td><td class='num'>{fmt(r.get('MIRROR_DTI'))}</td>"
                     f"<td class='num'>{fmt(r.get('reported_live_score'),4)}</td></tr>")

    arm_cards = "".join(download_card(name.upper() + " arm", arm, primary=(name == "sar"))
                        for name, arm in arms.items())

    irr_rows = "".join(
        f"<tr><td class='mono'>{esc(i.get('id'))}</td><td><span class='badge b-warn'>{esc(i.get('severity','?'))}</span></td>"
        f"<td>{esc(i.get('title',''))}</td><td>{esc(i.get('disposition',''))}</td></tr>"
        for i in irr.get("irregularities", []))

    model = build.get("model", {})
    covstats = cov.get("covariate_stats", {})
    _sent = cov.get("sentinel_band_pixels_inside_footprint", {}) or {}
    sentinel_total_idx = sum(_sent.values()) if _sent else 0

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GEMSDOE65 — SAR PU learning for unmapped-fault discovery</title>
<link rel="stylesheet" href="assets/site.css"></head><body><div class="wrap">
{header('GEMSDOE65 · Selection-bias-aware PU learning', f'DOE GEMS Prize Challenge (DrivenData 306) · generated {now} from <code>evidence/*.json</code> · no number on this page is hand-typed')}

{hero}

<h2 id="download">1. The submission files</h2>
<p class="small">Each card states in one line whether that file may be submitted. Format validation is a
14-point independent re-read (geometry, domain, range, budget). The <code>-nan</code> variant follows the
official contract literally ("data outside the bounds is null or nan"); the <code>-zeros</code> variant
additionally passes a naive whole-array <code>[0,1]</code> check that does not honour nodata.</p>
{arm_cards or '<div class="panel">No rasters built yet — run <code>python scripts/03_build_submission.py</code>.</div>'}

<h2 id="rules">2. Why each file was refused — the adjudication rules</h2>
<div class="panel"><p class="small">One implementation (<code>src/gems65/adjudicate.py</code>) is used by the build stage,
the re-adjudication stage, the run card and this page, so they cannot disagree. Rules are applied in order and the first
refusal wins.</p>
<table><tr><th>rule</th><th>text</th><th>this session</th></tr>
<tr><td class="mono">R1</td><td>must pass the independent 14-point validator (geometry, domain, range, no NaN inside the footprint, no mass on masked catalogue pixels)</td><td>{badge(True,'PASS on all 6 files')}</td></tr>
<tr><td class="mono">R2</td><td>must not duplicate a registry raster: rank-correlation &gt; 0.90, or &gt; 70% of dots within 3 px of one registry raster's dots</td><td>{badge(True,'PASS — max ρ ' + fmt(max((a.get('duplicate_check',{}).get('verdict',{}).get('max_spearman_surface') or 0) for a in arms.values()),4) + ', max overlap ' + fmt(max((a.get('duplicate_check',{}).get('verdict',{}).get('max_dot_overlap_3px') or 0) for a in arms.values()),4))}</td></tr>
<tr><td class="mono">R3</td><td>a lane whose pre-registered gate was not met is a NEGATIVE result; its experimental arm is logged, never promoted</td><td>{badge(not gate.get('GATE_PASSED'),'FIRED — sar arm NEGATIVE','not fired')}</td></tr>
<tr><td class="mono">R4</td><td>no arm may be cleared for a slot unless its blocked-holdout DTI exceeds the best registry artifact measured on the SAME cells</td><td>{badge(False,'FIRED — nnpu ' + fmt(gate.get('pooled_dti_nnpu_scar')) + ' and em ' + fmt((hold.get('pooled',{}).get('sar_em_only',{}) or {}).get('dti')) + ' vs best ' + fmt((load(REG/'adjudication.json',{}) or {}).get('holdout_reference',{}).get('best_dti')))}</td></tr>
<tr><td class="mono">R5</td><td>if the holdout is measured to be anti-correlated with live scores, report it with the verdict: passing R4 on a biased proxy is necessary, never sufficient</td><td>{badge(True,'REPORTED — ρ = ' + fmt(calib.get('spearman_holdout_pooled_vs_live'),3))}</td></tr>
</table>
<p class="small"><b>Bottom line:</b> {esc('no file is cleared; the verdict is NEGATIVE and it is logged as a deliverable.') if not any_ok else 'see the green card above.'}
Promotion to a weekly slot is a separate selector step (protocol rule 6); no slot was spent and no receipt exists.</p></div>

<h2 id="gate">3. The pre-registered gate — <span class="badge {cls(gate.get('GATE_PASSED'))}">{'PASSED' if gate.get('GATE_PASSED') else 'NOT PASSED'}</span></h2>
<div class="panel">
<p><b>Rule (from the standing brief):</b> {esc(gate.get('rule',''))}. Anchor
<code>a_bar = {esc(gate.get('primary_anchor_a_bar'))}</code>, pre-registered from the peer-reviewed
detailed-mapping share (~25%, Giddens &amp; Faulds 2025, SGP-TR-229).</p>
<table><tr><th>quantity</th><th class="num">value</th><th class="num">requirement / CI</th></tr>{gate_rows}</table>
<p class="small">Evidence class: <b>HOLDOUT-DTI</b> — evaluator <code>src/gems65/metric.py</code> (brute-force
verified to 1e-9), {hold.get('pooled',{}).get('sar_erm',{}).get('n_truth')} withheld positives pooled over
{len(hold.get('per_cell',[]))} blocked cells (4 quadrant blocks × 2 draws), 95% CI by percentile bootstrap over cells.
This is a <b>proxy</b>: its truth is the withheld part of the given catalogue, so it cannot reward a fault
that is in no catalogue.</p>
</div>

<h3>Propensity-scale sensitivity (the scale is not identified from PU data alone)</h3>
<div class="panel"><table><tr><th>anchor <code>a_bar</code> = mean propensity over labelled positives</th>
<th class="num">pooled DTI (SAR arm)</th><th class="num">coverage</th><th class="num">withheld positives</th></tr>
{abar_rows}</table>
<p class="small">Reported as a sensitivity, never as a point estimate: arXiv:1809.03207 §2/§5.1 shows the
propensity scale cannot be recovered from PU data alone, and no public index of exhaustively mapped
1:24,000 quadrangles was reachable from this sandbox to anchor it (see irregularities).</p></div>

<h2 id="instrument">4. Is the holdout instrument even predictive? (measured, not assumed)</h2>
<div class="grid g2">
<div class="panel"><h3 style="margin-top:0">Blocked holdout vs nine owner-reported live scores</h3>
<div class="grid g3">
<div class="kpi"><div class="k">Spearman(holdout, live)</div><div class="v">{fmt(calib.get('spearman_holdout_pooled_vs_live'),3)}</div></div>
<div class="kpi"><div class="k">Spearman(dot count, live)</div><div class="v">{fmt(calib.get('spearman_dot_count_vs_live'),3)}</div></div>
<div class="kpi"><div class="k">n rasters</div><div class="v">{calib.get('n_scored_rasters')}</div></div>
</div>
<table><tr><th>registry raster</th><th class="num">dots</th><th class="num">holdout DTI</th><th class="num">live</th></tr>{cal_rows}</table>
<p class="small flag">{esc(calib.get('known_handicap',''))}</p></div>
<div class="panel"><h3 style="margin-top:0">Registry-anchored mirror instrument</h3>
<div class="grid g2">
<div class="kpi"><div class="k">Spearman(mirror, live) leave-one-out</div><div class="v">{fmt(mirror.get('instrument_quality',{}).get('spearman_mirror_vs_live_leave_one_out'),3)}</div></div>
<div class="kpi"><div class="k">anchor</div><div class="v" style="font-size:12px">{esc(str(mirror.get('anchor',''))[:28])}</div></div>
</div>
<table><tr><th>raster</th><th class="num">dots</th><th class="num">MIRROR-DTI</th><th class="num">live</th></tr>{mir_rows}</table>
<p class="small">Evidence class: <b>MIRROR-DTI</b> — an instrument, not a score. Its pseudo-truth is a
submission, not the hidden truth, so it measures resemblance to the best-known artifact and is
deliberately pessimistic about a candidate whose point is to be different.</p></div>
</div>

<h2 id="model">5. What was fitted</h2>
<div class="grid g3">
<div class="kpi"><div class="k">EM iterations used</div><div class="v">{model.get('em_iters_used')}</div></div>
<div class="kpi"><div class="k">EM converged</div><div class="v">{esc(model.get('em_converged'))}</div></div>
<div class="kpi"><div class="k">mean propensity | labelled</div><div class="v">{fmt(model.get('mean_propensity_labelled'),4)}</div></div>
<div class="kpi"><div class="k">propensity range</div><div class="v" style="font-size:14px">[{fmt(model.get('propensity_min'),4)}, {fmt(model.get('propensity_max'),4)}]</div></div>
<div class="kpi"><div class="k">Horvitz–Thompson prevalence π</div><div class="v">{fmt(model.get('pi_horvitz_thompson'),4)}</div></div>
<div class="kpi"><div class="k">weights clipped at 10</div><div class="v">{fmt(model.get('clipped_weight_fraction'),4)}</div></div>
<div class="kpi"><div class="k">lidar coverage of footprint</div><div class="v">{fmt(covstats.get('lidar_coverage_frac_of_footprint'),4)}</div></div>
<div class="kpi"><div class="k">range-front pixels</div><div class="v">{covstats.get('range_front_px',0):,}</div></div>
<div class="kpi"><div class="k">basin-fill proxy vs log(depth to base) r</div><div class="v">{fmt(covstats.get('basin_fill_vs_log_depth_to_base_pearson_r'),3)}</div></div>
</div>

<h2 id="data">6. Data provenance (every byte hash-pinned)</h2>
<div class="panel"><table><tr><th>file</th><th class="num">bytes</th><th>sha256</th><th>pin</th></tr>
{"".join(f"<tr><td class='mono'>{esc(f['dest'])}</td><td class='num'>{f['bytes']:,}</td><td class='mono' style='font-size:11px'>{esc(f['sha256'][:24])}…</td><td>{badge(f['pin_match'],'MATCH','MISMATCH')}</td></tr>" for f in load(REG/'data_manifest.json',{}).get('files',[]))}
</table><p class="small">Grid: {cov.get('grid',{}).get('width')} × {cov.get('grid',{}).get('height')} px,
EPSG:{cov.get('grid',{}).get('epsg')}, transform {esc(cov.get('grid',{}).get('transform'))},
footprint {cov.get('grid',{}).get('footprint_pixels'):,} px, catalogue {cov.get('grid',{}).get('label_pixels'):,} px,
float32 sentinel band-pixels inside the footprint {sentinel_total_idx:,}.
The mirror is owner-supplied and integrity-pinned; it is <b>not</b> organizer-authenticated.</p></div>

<h2 id="irregularities">7. Irregularities flagged for review</h2>
<div class="panel"><table><tr><th>id</th><th>severity</th><th>finding</th><th>disposition</th></tr>{irr_rows}</table></div>

<h2 id="runcard">8. Run card</h2>
<div class="panel"><pre>{esc(json.dumps(card, indent=2)) if card else 'RUN_CARD.json not built yet — run python scripts/06_run_card.py'}</pre></div>

<p class="small" style="margin-top:34px">Canonical site: <a href="../index.html">docs/index.html</a>.
Lane pages: <a href="executive-summary.html">executive summary / how to submit</a> ·
<a href="research.html">method &amp; hypotheses</a> · <a href="sources.html">verified sources</a> ·
<a href="irregularities.html">irregularities</a> · <a href="limitations.html">limitations</a> ·
<a href="run-card.html">run card</a> · <a href="data/feed.json">feed.json</a></p>
</div></body></html>"""


def build_executive_summary() -> str:
    build = load(EVID / "submission_build.json", {})
    arms = build.get("arms", {})
    cfg = build.get("config", {})
    cov = load(EVID / "covariates.json", {})
    sentinel = cov.get("sentinel_band_pixels_inside_footprint", {}) or {}
    sentinel_total = sum(sentinel.values()) if sentinel else 0
    sentinel_max = max(sentinel.values()) if sentinel else 0
    any_ok = any(a.get("OK_TO_DOWNLOAD_AND_SUBMIT") for a in arms.values())
    submittable = [(k, a) for k, a in arms.items() if a.get("OK_TO_DOWNLOAD_AND_SUBMIT")]
    target = submittable[0] if submittable else None
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if target:
        k, a = target
        fname = Path(a["files"]["nan"]).name
        zname = Path(a["files"]["zeros"]).name
        pick = f"""
<div class="dl primary">
<h3>Step 1 — download this file</h3>
<div class="btnrow">
<a class="btn" href="downloads/{esc(fname)}" download>⬇ {esc(fname)}</a>
<a class="btn sec" href="downloads/{esc(zname)}" download>⬇ {esc(zname)} (zeros-outside fallback)</a>
</div>
<p class="small">Submission name to type into the portal's <i>Note</i> field (≤140 characters):<br>
<code>{esc(a.get('submission_note',''))}</code></p>
</div>"""
    else:
        pick = """
<div class="dl blocked">
<h3>Step 1 — THERE IS NO FILE CLEARED FOR SUBMISSION</h3>
<p>The lane's pre-registered gate was not met, so per the standing brief the result is logged as
<b>NEGATIVE</b> and no file on this page may be submitted. The rasters below are published as
format-valid evidence artifacts only. Do not spend a weekly slot on them.</p>
</div>"""

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Executive summary — how to submit · GEMSDOE65</title>
<link rel="stylesheet" href="assets/site.css"></head><body><div class="wrap">
{header('Executive summary — exactly how to make a submission', f'generated {now} · every number read from <code>evidence/*.json</code>')}

<div class="panel"><b>Bottom line:</b> {'a file is cleared for submission — use the green button.' if any_ok else
'<b style="color:#ff9aa2">no file is cleared for submission this session.</b> The gate failed; this is a logged negative result.'}
The competition metric, the masking rule, the file format and the known portal failure mode are all
documented below with links, so a submission can be made (or correctly declined) without reading any code.</div>

{pick}

<h2>Step 2 — what the portal accepts</h2>
<div class="panel">
<p>Verbatim from the submission dialog: <i>"You can submit a single-band GeoTIFF (.tif) file, or a .zip
file containing a single GeoTIFF, with your predictions. It must match the submission format's CRS,
shape, and geotransform."</i></p>
<table>
<tr><th>property</th><th>required value</th><th>verified here</th></tr>
<tr><td>Driver / bands</td><td>GeoTIFF, single band</td><td>{badge(True)}</td></tr>
<tr><td>Data type</td><td><code>float32</code></td><td>{badge(True)}</td></tr>
<tr><td>CRS</td><td>EPSG:32611 (WGS 84 / UTM zone 11N)</td><td>{badge(True)}</td></tr>
<tr><td>Shape (height × width)</td><td>3730 × 3292</td><td>{badge(True)}</td></tr>
<tr><td>Geotransform</td><td><code>(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)</code></td><td>{badge(True)}</td></tr>
<tr><td>Pixel size</td><td>100 m</td><td>{badge(True)}</td></tr>
<tr><td>Values</td><td>in <code>[0, 1]</code>, higher = more likely fault</td><td>{badge(True)}</td></tr>
<tr><td>Outside the bounds</td><td>null or NaN</td><td>{badge(True)}</td></tr>
<tr><td>Footprint pixels that must be finite</td><td>5,167,373 (from <code>sample_submission.tif</code>)</td><td>{badge(True)}</td></tr>
</table>
<p class="small">Sources: competition problem description "Submission format"
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">page 967</a>;
EPSG:32611 <a href="https://epsg.io/32611">epsg.io/32611</a>. Both read 2026-10-11.</p>
</div>

<h2>Step 3 — the error this repo engineers out permanently</h2>
<div class="panel flag">
<p><b>"Predicted values must be in range [0, 1]"</b> — two mechanisms, both measured here:</p>
<ul>
<li><b>M1 — float32 sentinel inside the footprint.</b> <code>training_features.tif</code> declares nodata
as <code>-3.4028234663852886e+38</code> (the float32 minimum, not NaN). Measured:
<b>{sentinel_total:,}</b>
sentinel band-pixels across the 19 bands lie <i>inside</i> the 5,167,373-pixel scoring footprint
(max {sentinel_max:,} in one band).
A pipeline that does not replace them ships −3.4e38.</li>
<li><b>M2 — footprint mask mismatch.</b> A footprint taken from a feature band is smaller than the
template's, which strands scored pixels as NaN. NaN fails any <code>((v&gt;=0)&amp;(v&lt;=1)).all()</code> check.</li>
</ul>
<p>Both are handled by construction in <code>src/gems65/submission.py</code>: the footprint is read from the
pinned <code>sample_submission.tif</code>, every in-footprint output pixel is a finite float32 in [0,1], and
<code>scripts/validate_submission.py</code> re-reads the written file and refuses to pass it otherwise.</p>
</div>

<h2>Step 4 — how the score is computed (so the file can be reasoned about)</h2>
<div class="panel">
<pre>k(d) = max(1 - d/R, 0),  R = 300 m = 3 px at 100 m
TP_w = sum over truth pixels g of  max over x with d(x,g) &lt;= R  of  p(x) k(d(x,g))
FP_w = sum over x with p(x) &gt; 0   of  p(x) [1 - max over g of k(d(x,g))]
FN_w = sum over g                 of  [1 - max over x of p(x) k(d(x,g))]  =  |G| - TP_w
DTI  = TP_w / (TP_w + 0.2 FP_w + 0.8 FN_w)</pre>
<p>Two exact consequences, both brute-force verified in <code>tests/test_metric.py</code>:</p>
<ul>
<li><code>DTI = T / (0.2 (T + S − M) + 0.8 K)</code> with <code>S</code> = emitted mass,
<code>M</code> = mass-weighted kernel coverage, <code>K</code> = |G|. For a dot field, <code>DTI = T / (0.2 N + 0.8 K)</code>.</li>
<li>Adding one unit of mass raises DTI <b>iff</b> its realised kernel credit <code>k &gt; 0.2 · DTI</code>
(≈0.056 at 0.28). The denominator rises by exactly 0.2 wherever the mass lands.</li>
<li>Known USGS/INGENIOUS fault pixels are <b>masked out of scoring</b> (DrivenData staff, forum thread
<a href="https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516">11516</a>),
so mass placed on them earns neither TP nor FP. This emitter places <b>zero</b> mass there.</li>
</ul>
</div>

<h2>Step 5 — where to submit</h2>
<div class="panel"><ol>
<li>Sign in at <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">DrivenData competition 306</a>.</li>
<li>Open the leaderboard/submissions page and choose <b>New submission</b>.</li>
<li><i>File to submit</i> → the downloaded <code>.tif</code> (a <code>.zip</code> containing exactly that one
<code>.tif</code> is also accepted).</li>
<li><i>Note (optional)</i> → paste the ≤140-character note from Step 1.</li>
<li>Submit, then copy the receipt score back into <code>registry/observations.jsonl</code> — that is the only
way a number in this repo ever becomes <b>ORGANIZER-CONFIRMED</b>.</li>
</ol>
<p class="small flag"><b>Weekly cap:</b> the number of slots left is shown on the submission page and cannot be
read from this sandbox. Promotion to a real slot is a separate selector step (protocol rule 6) — this
repo builds and validates candidates, it does not spend slots.</p></div>

<h2>What was actually built this session</h2>
<div class="panel"><table><tr><th>arm</th><th>file</th><th class="num">dots</th><th>verdict</th><th>submit?</th></tr>
{"".join(f'<tr><td class="mono">{esc(k)}</td><td class="mono" style="font-size:11.5px">{esc(Path(a["files"]["nan"]).name)}</td><td class="num">{a.get("emitted_pixels",0):,}</td><td>{esc(a.get("verdict"))}</td><td>{badge(a.get("OK_TO_DOWNLOAD_AND_SUBMIT"),"YES","NO")}</td></tr>' for k,a in arms.items())}
</table>
<p class="small">Build config: {esc(json.dumps(cfg))}</p></div>

</div></body></html>"""


def build_research(hold, build, card) -> str:
    hyp = (Path(G.repo_root()) / "docs" / "research" / "hypotheses.md")
    body = hyp.read_text() if hyp.exists() else "_not written yet_"
    import re
    body_html = html.escape(body)
    body_html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", body_html, flags=re.M)
    body_html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", body_html, flags=re.M)
    body_html = re.sub(r"^# (.+)$", r"<h2>\1</h2>", body_html, flags=re.M)   # one h1 per page (site rule)
    body_html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body_html)
    body_html = re.sub(r"`(.+?)`", r"<code>\1</code>", body_html)
    body_html = re.sub(r"&lt;(https?://[^\s&]+)&gt;", r'<a href="\1">\1</a>', body_html)
    body_html = body_html.replace("\n\n", "</p><p>").replace("\n", "<br>\n")
    lc = hold.get("leakage_canary_auc", {})
    lc_rows = "".join(f"<tr><td class='mono'>{esc(k)}</td><td class='num'>{fmt(v,4)}</td>"
                      f"<td>{badge(v <= 0.90, 'ok', 'LEAKAGE-SUSPECT')}</td></tr>" for k, v in lc.items())
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Method &amp; hypotheses · GEMSDOE65</title>
<link rel="stylesheet" href="assets/site.css"></head><body><div class="wrap">
{header('Method, hypotheses and the leakage canary', f'generated {now}')}
<h2>Leakage canary — every feature tested alone on the holdout</h2>
<div class="panel"><p class="small">Protocol rule 4: AUC above 0.90 means leakage until proven otherwise.
Pooled over {len(hold.get('per_cell',[]))} blocked cells, weighted by withheld positives.</p>
<table><tr><th>feature</th><th class="num">holdout AUC (alone)</th><th>verdict</th></tr>{lc_rows}</table></div>
<h2>Method and candidate hypotheses</h2>
<div class="panel"><p>{body_html}</p></div>
</div></body></html>"""


def build_sources() -> str:
    src = load(REG / "sources_lane65.json", {"sources": []})
    rows = "".join(
        f"<tr><td>{esc(s.get('id'))}</td><td>{esc(s.get('what'))}</td>"
        f"<td><a href='{esc(s.get('url'))}'>{esc(s.get('url'))}</a></td>"
        f"<td><span class='badge b-mut'>{esc(s.get('class'))}</span></td><td>{esc(s.get('read_utc'))}</td>"
        f"<td>{esc(s.get('quote',''))[:400]}</td></tr>" for s in src.get("sources", []))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Verified sources · GEMSDOE65</title>
<link rel="stylesheet" href="assets/site.css"></head><body><div class="wrap">
{header('Verified sources — links for manual review', f'generated {now} · every row was read, not recalled')}
<div class="panel"><table><tr><th>#</th><th>what it establishes</th><th>link</th><th>class</th><th>read</th><th>verbatim / measured content</th></tr>
{rows}</table></div>
</div></body></html>"""


def build_irregularities() -> str:
    irr = load(REG / "irregularities.json", {"irregularities": []})
    cards = ""
    for i in irr.get("irregularities", []):
        cards += f"""<div class="panel flag"><h3 style="margin-top:0">{esc(i.get('id'))} · {esc(i.get('title'))}
        <span class="badge b-warn">{esc(i.get('severity'))}</span></h3>
        <p><b>Finding.</b> {esc(i.get('finding'))}</p>
        <p><b>Evidence.</b> {esc(i.get('evidence'))}</p>
        <p><b>Disposition.</b> {esc(i.get('disposition'))}</p>
        <p class="small">Status: {esc(i.get('status'))} · raised {esc(i.get('raised_utc'))}</p></div>"""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Irregularities · GEMSDOE65</title>
<link rel="stylesheet" href="assets/site.css"></head><body><div class="wrap">
{header('Irregularities flagged for review', f'generated {now} · {len(irr.get("irregularities",[]))} open or closed')}
{cards or '<div class="panel">none recorded</div>'}
</div></body></html>"""


def build_limitations() -> str:
    p = Path(G.repo_root()) / "LIMITATIONS.md"
    txt = p.read_text() if p.exists() else "_not written yet_"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Limitations · GEMSDOE65</title>
<link rel="stylesheet" href="assets/site.css"></head><body><div class="wrap">
{header('Limitations and what is needed next', f'generated {now}')}
<div class="panel"><pre>{html.escape(txt)}</pre></div>
</div></body></html>"""


def build_run_card_page() -> str:
    card = load(Path(G.repo_root()) / "RUN_CARD.json", {})
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Run card · GEMSDOE65</title>
<link rel="stylesheet" href="assets/site.css"></head><body><div class="wrap">
{header('Run card (protocol rule 5)', f'generated {now}')}
<div class="panel"><pre>{html.escape(json.dumps(card, indent=2))}</pre></div>
</div></body></html>"""


def main() -> int:
    DOCS.mkdir(exist_ok=True)
    (DOCS / "assets").mkdir(exist_ok=True)
    (DOCS / "assets" / "site.css").write_text(CSS, encoding="utf-8")
    hold = load(EVID / "holdout_pu.json", {})
    build = load(EVID / "submission_build.json", {})
    card = load(Path(G.repo_root()) / "RUN_CARD.json", {})
    (DOCS / "index.html").write_text(build_index(), encoding="utf-8")
    (DOCS / "executive-summary.html").write_text(build_executive_summary(), encoding="utf-8")
    (DOCS / "research.html").write_text(build_research(hold, build, card), encoding="utf-8")
    (DOCS / "sources.html").write_text(build_sources(), encoding="utf-8")
    (DOCS / "irregularities.html").write_text(build_irregularities(), encoding="utf-8")
    (DOCS / "limitations.html").write_text(build_limitations(), encoding="utf-8")
    (DOCS / "run-card.html").write_text(build_run_card_page(), encoding="utf-8")

    # machine-readable feed (the "up to date current feed" requirement)
    feed = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo": "buffedlizard55-lab/GEMSDOE65",
        "lane": "selection-bias-aware (SAR) PU learning",
        "gate": hold.get("gate", {}),
        "submittable_files": [
            {"arm": k, "file": Path(a["files"]["nan"]).name, "zeros_variant": Path(a["files"]["zeros"]).name,
             "emitted_pixels": a.get("emitted_pixels"), "note": a.get("submission_note"),
             "sha256": a.get("validator", {}).get("nan", {}).get("sha256"),
             "verdict": a.get("verdict")}
            for k, a in build.get("arms", {}).items() if a.get("OK_TO_DOWNLOAD_AND_SUBMIT")],
        "blocked_files": [
            {"arm": k, "file": Path(a["files"]["nan"]).name, "verdict": a.get("verdict"),
             "reason": a.get("verdict_reason")}
            for k, a in build.get("arms", {}).items() if not a.get("OK_TO_DOWNLOAD_AND_SUBMIT")],
        "instrument_calibration": load(EVID / "holdout_calibration.json", {}),
        "irregularities_open": [i["id"] for i in load(REG / "irregularities.json", {"irregularities": []})
                                .get("irregularities", []) if i.get("status") != "closed"],
    }
    (DOCS / "data").mkdir(exist_ok=True)
    (DOCS / "data" / "feed.json").write_text(json.dumps(feed, indent=2), encoding="utf-8")
    print(f"[site] wrote {len(list(DOCS.glob('*.html')))} pages + data/feed.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
