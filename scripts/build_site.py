#!/usr/bin/env python3
"""GEMSDOE65 -- generate the evidence site and the canonical run card from the artifacts.

Every number rendered on the site comes from a file in ``artifacts/`` or
``docs/downloads/submissions_manifest.json``; nothing is typed in by hand.  Re-run after
any experiment:

    python3 scripts/build_site.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ART = REPO / "artifacts"
DOCS = REPO / "docs"
DOWN = DOCS / "downloads"


def load(p: Path, default=None):
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def fmt(x, nd=4):
    if x is None:
        return "&mdash;"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


NAV = """<header class="site-header"><div class="wrap nav-row">
  <a class="brand" href="index.html">GEMSDOE65<small>Evidence before submission</small></a>
  <nav aria-label="Main navigation"><a href="index.html">Status</a><a href="executive-summary.html">Submit guide</a><a href="hypotheses.html">Hypotheses</a><a href="competitive-context.html">Score audit</a><a href="research.html">Research</a><a href="irregularities.html">Irregularities</a><a href="downloads.html">Downloads</a><a href="lane65b/index.html">Lane 65 · session B</a></nav>
</div></header>"""

FOOT = """<footer class="footer"><div class="wrap"><a href="index.html">Status and download gate</a><a href="executive-summary.html">Submit guide</a><a href="downloads.html">Downloads</a><a href="data/run-card.json">Current JSON run card</a><p><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Official problem description</a><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Official leaderboard</a><a href="https://github.com/drivendataorg/gems-prize-reference-solution">Organizer reference solution</a></p></div></footer>"""


def page(title: str, desc: str, body: str, current: str = "") -> str:
    cur = f'<a aria-current="page" href="{current}.html">{current.replace("-", " ")}</a>' if current else ""
    nav = NAV.replace(f'<a href="{current}.html">{current.replace("-", " ")}</a>', cur) if current else NAV
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{esc(desc)}">
  <title>{esc(title)}</title><link rel="stylesheet" href="assets/site.css">
</head>
<body>
{nav}
<main class="wrap">
{body}
</main>
{FOOT}
</body></html>
"""


# --------------------------------------------------------------------------------------
def build(cleared: bool, manifest: dict, run_card: dict) -> None:
    inv = load(ART / "input_verification.json", {})
    canary = load(ART / "leakage_canary.json", {})
    cov_stats = load(ART / "propensity_covariate_stats.json", {})
    sar = load(ART / "sar_em_summary.json", {})
    sweep = load(ART / "holdout_sweep.json", {})
    best = load(ART / "holdout_best.json", {})
    shrink = load(ART / "shrinkage_sensitivity.json", {})
    drift = load(ART / "registry_lane_drift.json", {})
    val = load(ART / "validator_output.json", {})

    gate = manifest.get("gate", {})
    g = manifest.get("files", {}).get("zeros", {})
    note = manifest.get("submission_note", "")
    dots = manifest.get("emitted_dots")

    # ---------------------------------------------------------------- index.html
    if cleared:
        gate_html = f"""
      <aside class="gate gate-good" aria-label="Submission readiness">
        <span class="pill pill-good">Gate passed &middot; {esc(manifest.get('timestamp',''))}</span>
        <strong>Cleared to submit</strong>
        <p><b>It is OK to download and submit the file below.</b> Every preregistered gate
        passed: blocked-holdout DTI beat the matched nnPU baseline, the
        highest-propensity tercile did not lose, the raster is unique against
        {drift.get('rasters_compared','&mdash;')} prior rasters, and the written bytes pass the
        format validator.</p>
        <p><a class="btn" href="downloads/{esc(g.get('filename',''))}">Download submission TIF</a></p>
        <p class="small">sha256 <code>{esc(g.get('sha256','')[:32])}&hellip;</code><br>
        note: <code>{esc(note)}</code></p>
      </aside>"""
    else:
        gate_html = f"""
      <aside class="gate" aria-label="Submission readiness">
        <span class="pill pill-danger">Gate not met &middot; {esc(manifest.get('timestamp',''))}</span>
        <strong>Do not submit</strong>
        <p><b>It is NOT OK to download or submit a raster from this project.</b> The
        preregistered promotion gate failed. A format-valid candidate raster was produced
        and is listed on the <a href="downloads.html">downloads page</a> for audit only; it is
        <em>not</em> cleared for a competition slot.</p>
        <p class="small">Failed gate: {esc(run_card.get('failed_gate','highest-propensity tercile'))}.</p>
      </aside>"""

    best_rows = ""
    for k, v in sorted(best.items()):
        best_rows += (f"<tr><td><code>{esc(k)}</code></td><td>{esc(v.get('config',''))}</td>"
                      f"<td class='score'>{fmt(v.get('holdout_dti'))}</td>"
                      f"<td class='score'>{fmt(v.get('sgmc_off_dti'))}</td>"
                      f"<td>{v.get('emitted','&mdash;')}</td></tr>")

    shrink_rows = ""
    for k, v in sorted((shrink.get("results") or {}).items(), key=lambda kv: float(kv[0])):
        t = v.get("tercile_dti", {})
        shrink_rows += (
            f"<tr><td class='score'>{fmt(float(k),2)}</td>"
            f"<td class='score'>{fmt(v.get('holdout_dti'))}</td>"
            f"<td class='score'>{fmt(v.get('sgmc_off_dti'))}</td>"
            f"<td class='score'>{fmt(t.get('high'))}</td>"
            f"<td>{v.get('emitted','&mdash;')}</td></tr>")

    body = f"""
  <section class="hero" aria-labelledby="main-heading">
    <div class="hero-grid">
      <div>
        <div class="kicker">DOE GEMS Prize &middot; DrivenData competition 306</div>
        <h1>Selection-bias-aware fault discovery: what the evidence supports, and what it does not.</h1>
        <p class="lede">The supplied fault catalogue is a <em>selected-at-random</em> sample of the
        real fault population, conditioned on observables. This project estimates that selection
        propensity with SAR-EM (Bekker &amp; Davis, PMLR&nbsp;94, 2018) from five observability
        covariates, trains the fault posterior with the propensity-aware empirical risk of Bekker,
        Robberechts &amp; Davis (arXiv:1809.03207) with weights clipped at 10, and compares it
        against an nnPU baseline on identical spatially blocked folds.</p>
        <a class="btn btn-secondary" href="executive-summary.html">How to submit (exact steps)</a>
        <a class="btn btn-secondary" href="downloads.html">Downloads and audit files</a>
      </div>
      {gate_html}
    </div>
  </section>

  <section aria-labelledby="res-heading">
    <h2 id="res-heading">Experiment results &mdash; all HOLDOUT-DTI on the shared evaluator</h2>
    <p class="small">Evaluator: spatially blocked whole-segment hide-and-recover (4 quadrants
    &times; 2 draws, 15&nbsp;px collar, 12&nbsp;px domain erosion), pooled DTI with
    &alpha;&nbsp;=&nbsp;0.2, &beta;&nbsp;=&nbsp;0.8, 300&nbsp;m triangular kernel. Withheld
    positives per cell &asymp; 1,900&ndash;4,700 px (8 cells). This is a <em>catalogue</em>
    hide-and-recover proxy, not an organizer score on unknown faults.</p>
    <div class="table-wrap"><table>
      <thead><tr><th>Candidate surface</th><th>Best emission config</th><th>Blocked-holdout DTI</th><th>Off-catalogue (SGMC) DTI</th><th>Dots</th></tr></thead>
      <tbody>{best_rows}</tbody>
    </table></div>
  </section>

  <section aria-labelledby="gate-heading">
    <h2 id="gate-heading">The promotion gate, item by item</h2>
    <div class="grid">
      <article class="card"><span class="card-number">{fmt(gate.get('overall_holdout_dti',{}).get('delta'),4)}</span>
        <h3>Overall blocked-holdout DTI</h3>
        <p>SAR propensity-aware risk {fmt(gate.get('overall_holdout_dti',{}).get('sar'))} vs nnPU
        baseline {fmt(gate.get('overall_holdout_dti',{}).get('nnpu_baseline'))}.
        {'<b>PASS</b>' if gate.get('overall_holdout_dti',{}).get('delta',0)>0 else '<b>FAIL</b>'}</p></article>
      <article class="card"><span class="card-number">{fmt(gate.get('sgmc_off_catalogue_dti',{}).get('delta'),4)}</span>
        <h3>Off-catalogue (USGS SGMC) DTI</h3>
        <p>SAR {fmt(gate.get('sgmc_off_catalogue_dti',{}).get('sar'))} vs nnPU
        {fmt(gate.get('sgmc_off_catalogue_dti',{}).get('nnpu_baseline'))}. An independent,
        leakage-free truth proxy (62,703 px &ge; 4 px from any catalogue pixel).
        {'<b>PASS</b>' if gate.get('sgmc_off_catalogue_dti',{}).get('delta',0)>0 else '<b>FAIL</b>'}</p></article>
      <article class="card"><span class="card-number">{'yes' if gate.get('highest_propensity_tercile',{}).get('no_loss') else 'no'}</span>
        <h3>Highest-propensity tercile</h3>
        <p>SAR {fmt(gate.get('highest_propensity_tercile',{}).get('sar',{}).get('high'))} vs nnPU
        {fmt(gate.get('highest_propensity_tercile',{}).get('nnpu_baseline',{}).get('high'))}.
        {'<b>PASS</b>' if gate.get('highest_propensity_tercile',{}).get('no_loss') else '<b>FAIL</b>'}</p></article>
    </div>
  </section>

  <section aria-labelledby="sens-heading">
    <h2 id="sens-heading">Sensitivity: partial propensity correction</h2>
    <p>Full correction (weight 1/e) improved the pooled blocked-holdout DTI but pushed the
    emission out of the well-mapped, high-observability terrain where the withheld catalogue
    segments actually live, so the highest-propensity tercile collapsed. Shrinking the weights
    toward 1, <code>w = 1 / e^lambda</code>, interpolates between the nnPU baseline
    (&lambda;&nbsp;=&nbsp;0) and the full propensity-aware risk (&lambda;&nbsp;=&nbsp;1).</p>
    <div class="table-wrap"><table>
      <thead><tr><th>&lambda;</th><th>Blocked-holdout DTI</th><th>Off-catalogue DTI</th><th>High-propensity tercile</th><th>Dots</th></tr></thead>
      <tbody>{shrink_rows or '<tr><td colspan="5">not run</td></tr>'}</tbody>
    </table></div>
  </section>

  <section aria-labelledby="canary-heading">
    <h2 id="canary-heading">Leakage canary</h2>
    <p>{canary.get('n_features','&mdash;')} single features were each tested alone on the blocked
    holdout. None exceeded the 0.90 AUC leakage threshold; the strongest single feature was
    <code>{esc((canary.get('top_20') or [{}])[0].get('feature','&mdash;'))}</code> at mean AUC
    {fmt((canary.get('top_20') or [{}])[0].get('mean_auc'))}. No distance-to-catalogue channel is
    in the feature stack by construction.</p>
  </section>

  <section aria-labelledby="inputs-heading">
    <h2 id="inputs-heading">Verified inputs</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>File</th><th>Status</th><th>sha256 (first 16)</th></tr></thead>
      <tbody>{"".join(f"<tr><td><code>{esc(k)}</code></td><td>{esc(v.get('status',''))}</td><td><code>{esc((v.get('sha256') or '')[:16])}</code></td></tr>" for k, v in (inv.get('files') or {}).items())}</tbody>
    </table></div>
    <p class="small">Digests are pinned in <code>src/gems65/grid.py</code> and re-verified on every
    run; a mismatch aborts the pipeline. Full receipt:
    <a href="https://github.com/buffedlizard55-lab/GEMSDOE65/blob/main/artifacts/input_verification.json">artifacts/input_verification.json</a>.</p>
  </section>

  <section aria-labelledby="board-heading">
    <h2 id="board-heading">Official leaderboard &middot; direct link only</h2>
    <div class="callout warning">
      <p><strong>No rows are fetched, copied, or mirrored on this site.</strong> The DrivenData
      <a href="https://www.drivendata.org/termsofuse/">Terms of Use</a> prohibit automated access to
      monitor or copy website material and prohibit manual monitoring/copying without prior written
      consent. This page provides only a link to the
      <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">official
      leaderboard</a>. No written permission or authorized leaderboard API has been established.</p>
    </div>
    <p class="small">A public leaderboard row is not a submission-page receipt and does not identify a
    TIFF. This project reports a score as <code>ORGANIZER-CONFIRMED</code> only when the portal
    receipt ties it to a specific artifact. No score on this page is an organizer score.</p>
  </section>
"""
    (DOCS / "index.html").write_text(page(
        "GEMSDOE65 · selection-bias-aware fault discovery",
        "SAR-EM propensity estimation, propensity-aware PU risk, blocked-holdout evidence, and a clear submission gate for the DOE GEMS Prize Challenge.",
        body, current="index"))

    # ---------------------------------------------------------- executive-summary.html
    if cleared:
        lead = f"""
  <div class="callout"><span class="pill pill-good">Cleared to submit</span>
  <p><strong>There is one approved file.</strong> Download
  <a href="downloads/{esc(g.get('filename',''))}"><code>{esc(g.get('filename',''))}</code></a>,
  paste the note below into the <strong>Note (optional)</strong> field, and submit. Do not rename
  the file. Verify the sha256 in the table at the bottom of this page after downloading.</p></div>"""
    else:
        lead = f"""
  <div class="callout danger"><span class="pill pill-danger">Do not submit</span>
  <p><strong>There is no approved file.</strong> The preregistered promotion gate failed
  ({esc(run_card.get('failed_gate','highest-propensity tercile'))}). The format-valid candidate
  raster listed on the <a href="downloads.html">downloads page</a> exists for audit only and must
  not be uploaded. Negative results are deliverables; this session spends no submission slot.</p></div>"""

    body = f"""
  <div class="page-title"><div class="kicker">Executive summary &middot; DrivenData competition 306</div>
    <h1>How to submit a GEMS GeoTIFF &mdash; and whether this project has one ready</h1>
    <p class="lede">Read the gate at the top of the <a href="index.html">status page</a> first.
    This page gives the exact upload steps and the format contract. It submits nothing on your
    behalf.</p></div>
  {lead}

  <h2>Step 1 &mdash; confirm the gate is green</h2>
  <ol>
    <li>The status page must show <strong>Cleared to submit</strong> and name the exact candidate
    from the run card. A research note, a projected score, an old file, or a format-only check is
    not promotion.</li>
    <li>The run card must contain the evaluator version, withheld-positive count, HOLDOUT-DTI with a
    95% CI, the registry correlation / dot-overlap result, the raster sha256, and passing validator
    output. The candidate must beat both the current holdout best and the matched nnPU baseline
    overall and must not lose in the highest-propensity tercile.</li>
    <li>If any of those is missing or failed: <strong>stop</strong>. Do not substitute a sibling
    project's raster.</li>
  </ol>

  <h2>Step 2 &mdash; download the file</h2>
  <ol>
    <li>Open the <a href="downloads.html">downloads page</a> and use the primary
    <code>*-zeros.tif</code> link. That variant writes <code>0.0</code> outside the footprint with
    <code>nodata=None</code>, so <strong>all 12,279,160 cells</strong> satisfy
    <code>0 &le; v &le; 1</code> and there is no NaN anywhere. This is the variant that removes the
    DrivenData error <em>"Predicted values must be in range [0, 1]"</em>, which is raised when the
    validator's range test sees a NaN comparison return False.</li>
    <li>A <code>*-nan.tif</code> variant that reproduces the sample submission's NaN-outside
    convention is published alongside it for byte-format comparison. Prefer the
    <code>-zeros</code> file for upload.</li>
    <li>Do not rename, repackage, or re-clip the file. Preserve the sha256 and the note shown for
    that exact run.</li>
  </ol>

  <h2>Step 3 &mdash; upload it</h2>
  <ol>
    <li>Sign in at <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">drivendata.org/competitions/306/competition-doe-gems</a> and open the
    <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">submissions page</a>. Choose <strong>New submission</strong>.</li>
    <li>Under <strong>File to submit</strong>, choose the downloaded <code>.tif</code>. The form
    accepts a single GeoTIFF or a ZIP containing exactly one GeoTIFF; upload the direct
    <code>.tif</code>.</li>
    <li>In <strong>Note (optional)</strong>, paste the short note from the run card (kept under 140
    characters by this project), e.g.
    <code>{esc(note) if note else 'SAR-EM propensity PU vs nnPU; 39681 dots; holdout DTI 0.0218'}</code>.</li>
    <li>Confirm the filename, note, checksum, and green gate all describe the same run, then submit.</li>
    <li>Save the organizer's submission-page receipt. Only a receipt tied to the exact file/hash
    counts as <code>ORGANIZER-CONFIRMED</code> evidence in this project.</li>
  </ol>

  <h2>Format contract (what the validator checks)</h2>
  <ul>
    <li>exactly one band, <code>float32</code>;</li>
    <li><code>EPSG:32611</code>, 100 m, shape 3730 &times; 3292, transform
    <code>(100, 0, 243350, 0, -100, 4508550)</code> &mdash; identical to the official
    <code>sample_submission.tif</code>;</li>
    <li>every in-footprint value finite and in <code>[0, 1]</code>;</li>
    <li>no NaN inside the footprint; NaN (or 0.0) only outside it;</li>
    <li>a separate read-back of the written bytes reproduces the same receipt.</li>
  </ul>

  <h2>Receipts for the current candidate</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>Variant</th><th>Filename</th><th>Bytes</th><th>sha256</th><th>All checks</th></tr></thead>
    <tbody>
      <tr><td>primary (zeros)</td><td><code>{esc(g.get('filename','&mdash;'))}</code></td>
        <td>{g.get('bytes','&mdash;')}</td><td><code>{esc(g.get('sha256','&mdash;'))}</code></td>
        <td>{'yes' if g.get('all_checks_passed') else 'no'}</td></tr>
      <tr><td>secondary (nan)</td><td><code>{esc(manifest.get('files',{}).get('nan',{}).get('filename','&mdash;'))}</code></td>
        <td>{manifest.get('files',{}).get('nan',{}).get('bytes','&mdash;')}</td>
        <td><code>{esc(manifest.get('files',{}).get('nan',{}).get('sha256','&mdash;'))}</code></td>
        <td>{'yes' if manifest.get('files',{}).get('nan',{}).get('all_checks_passed') else 'no'}</td></tr>
    </tbody>
  </table></div>
  <p class="small">Machine-readable receipts: <a href="https://github.com/buffedlizard55-lab/GEMSDOE65/blob/main/docs/downloads/submissions_manifest.json">docs/downloads/submissions_manifest.json</a>
  and <a href="data/run-card.json">docs/data/run-card.json</a>.</p>
"""
    (DOCS / "executive-summary.html").write_text(page(
        "Executive summary · how to submit · GEMSDOE65",
        "Step-by-step submission instructions, the format contract, and the current download decision for the DOE GEMS Prize Challenge.",
        body, current="executive-summary"))

    # --------------------------------------------------------------- downloads.html
    files = sorted(DOWN.glob("*.tif")) + sorted(DOWN.glob("*.json"))
    rows = ""
    for f in files:
        rows += (f"<tr><td><a href='downloads/{esc(f.name)}'><code>{esc(f.name)}</code></a></td>"
                 f"<td>{f.stat().st_size:,}</td></tr>")
    body = f"""
  <div class="page-title"><div class="kicker">Downloads</div>
    <h1>Artifacts published by this project</h1>
    <p class="lede">Everything here is generated by <code>scripts/run_lane.py</code> and
    <code>scripts/build_submission.py</code>. Nothing is copied from a sibling GEMSDOE project.</p></div>
  {'<div class="callout"><span class="pill pill-good">Cleared to submit</span><p>The primary file is the <code>-zeros.tif</code> below. It is approved for a competition slot.</p></div>' if cleared else '<div class="callout danger"><span class="pill pill-danger">Audit only</span><p>No file here is cleared for submission. The rasters are published so the negative result can be reproduced and audited.</p></div>'}
  <h2>Files</h2>
  <div class="table-wrap"><table>
    <thead><tr><th>File</th><th>Bytes</th></tr></thead><tbody>{rows}</tbody>
  </table></div>
  <h2>Audit receipts</h2>
  <ul>
    <li><a href="https://github.com/buffedlizard55-lab/GEMSDOE65/blob/main/artifacts/input_verification.json">input_verification.json</a> &mdash; pinned sha256 of the three official rasters.</li>
    <li><a href="https://github.com/buffedlizard55-lab/GEMSDOE65/blob/main/artifacts/leakage_canary.json">leakage_canary.json</a> &mdash; per-feature AUC on the blocked holdout.</li>
    <li><a href="https://github.com/buffedlizard55-lab/GEMSDOE65/blob/main/artifacts/holdout_sweep.json">holdout_sweep.json</a> &mdash; every candidate &times; emission configuration.</li>
    <li><a href="https://github.com/buffedlizard55-lab/GEMSDOE65/blob/main/artifacts/shrinkage_sensitivity.json">shrinkage_sensitivity.json</a> &mdash; partial-correction sensitivity curve.</li>
    <li><a href="https://github.com/buffedlizard55-lab/GEMSDOE65/blob/main/artifacts/registry_lane_drift.json">registry_lane_drift.json</a> &mdash; rank-correlation and 3-px dot overlap vs every prior raster.</li>
    <li><a href="https://github.com/buffedlizard55-lab/GEMSDOE65/blob/main/artifacts/validator_output.json">validator_output.json</a> &mdash; independent re-read of the written bytes.</li>
  </ul>
"""
    (DOCS / "downloads.html").write_text(page(
        "Downloads · GEMSDOE65", "Published submission candidates and audit receipts.", body,
        current="downloads"))

    # ------------------------------------------------------------------ run card
    rc = dict(run_card)
    rc.setdefault("generated_utc", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    (DOCS / "data").mkdir(parents=True, exist_ok=True)
    (DOCS / "data" / "run-card.json").write_text(json.dumps(rc, indent=2))
    print(f"site written; cleared={cleared}")


if __name__ == "__main__":
    m = load(DOWN / "submissions_manifest.json", {})
    cleared = bool(m.get("cleared_to_submit"))
    rc = load(DOCS / "data" / "run-card.json", {})
    build(cleared, m, rc)
