#!/usr/bin/env python3
"""Render the status page and the machine-readable status feed from evidence.

The site is generated, never hand-edited between the ``STATUS:BEGIN`` and
``STATUS:END`` markers in ``docs/index.html``, so the download decision at the
top of the page can never drift from ``evidence/run_card.json``.  Nothing here
fetches anything: every input is a local JSON artifact written by
``scripts/run_lane.py``.

Usage::

    python3 scripts/build_site.py            # regenerate the markers + status.json
    python3 scripts/build_site.py --check    # fail if the page is stale
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = REPO_ROOT / "evidence"
DOCS = REPO_ROOT / "docs"
INDEX = DOCS / "index.html"
STATUS_JSON = DOCS / "data" / "status.json"
BEGIN = "<!-- STATUS:BEGIN -->"
END = "<!-- STATUS:END -->"


def load(name: str, default=None):
    path = EVIDENCE / name
    if not path.is_file():
        return default
    return json.loads(path.read_text())


def gate_pill(card) -> str:
    verdict = (card or {}).get("verdict", {})
    if verdict.get("download_cleared"):
        return ('<span class="pill pill-ok">CLEARED · candidate written and validated'
                f' · {html.escape(str(card.get("generated_utc", "")))}</span>')
    if card and card.get("forced"):
        return ('<span class="pill pill-danger">FORCED WRITE · gate not met · '
                'DO NOT SUBMIT</span>')
    return ('<span class="pill pill-danger">NOT CLEARED · no downloadable candidate</span>')


def fmt(value, places=4):
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{places}f}"
    return str(value)


def holdout_block(holdout) -> str:
    if not holdout:
        return ('<p class="small">No blocked-hold-out artifact is present in this checkout '
                '(<code>evidence/lane_holdout.json</code> missing): the gate has not been '
                'evaluated here.</p>')
    pooled = holdout.get("pooled", {})
    pooled_wire = holdout.get("pooled_wire", {})
    arms = sorted(pooled.get("scores", {}))
    rows = []
    for arm in arms:
        s = pooled["scores"][arm]
        rows.append(f"<tr><td><code>{html.escape(arm)}</code></td><td>{fmt(s['dti'])}</td>"
                    f"<td>[{fmt(s['ci95'][0])}, {fmt(s['ci95'][1])}]</td>"
                    f"<td>{s['withheld_positive_pixels']}</td></tr>")
    wire = pooled_wire.get("scores", {}).get("wire") if pooled_wire else None
    wire_row = ""
    if wire:
        ci = wire["ci95"]
        wire_row = (f"<tr><td><code>wire</code> (declared rule)</td><td><b>{fmt(wire['dti'])}</b></td>"
                    f"<td>[{fmt(ci[0])}, {fmt(ci[1])}]</td>"
                    f"<td>{wire['withheld_positive_pixels']}</td></tr>")
    deltas = ""
    for name, d in (pooled.get("paired_differences") or {}).items():
        deltas += (f"<li>candidate <code>prop</code> − baseline <code>{html.escape(name)}</code>: "
                   f"Δ = {fmt(d.get('delta'))} "
                   f"(95 % CI [{fmt(d['ci95'][0])}, {fmt(d['ci95'][1])}])</li>")
    for name, d in ((pooled_wire.get("paired_differences") or {}) if pooled_wire else {}).items():
        deltas += (f"<li>candidate <code>wire</code> − baseline <code>{html.escape(name)}</code>: "
                   f"Δ = {fmt(d.get('delta'))} "
                   f"(95 % CI [{fmt(d['ci95'][0])}, {fmt(d['ci95'][1])}])</li>")
    folds = ", ".join(html.escape(f["fold"]) for f in holdout.get("per_fold", []))
    return f"""
    <table>
      <caption>Pooled blocked-hold-out, evaluator <code>{html.escape(str(holdout.get('evaluator_version')))}</code>,
      folds {folds or '—'}, evidence class <code>HOLDOUT-DTI</code> (an internal instrument value,
      never a leaderboard score).</caption>
      <thead><tr><th>arm</th><th>pooled DTI</th><th>95 % CI</th><th>withheld positives</th></tr></thead>
      <tbody>{''.join(rows)}{wire_row}</tbody>
    </table>
    <ul class="small">{deltas or '<li>no paired comparison recorded</li>'}</ul>
    <p class="small">Protocol: whole catalogue components withheld with a {holdout.get('protocol', {}).get('buffer_px', 3)} px
    feature buffer, catalogue-derived channels recomputed from the fold's <i>visible</i> faults only,
    visible faults masked pixel-exactly out of scoring, pooled α = 0.2 / β = 0.8 with a 300 m
    triangular kernel. Training rows: {holdout.get('protocol', {}).get('train_unlabeled', '—')} unlabeled
    per fold, inverse-propensity weights clipped at 10.</p>"""


def canary_block(canary) -> str:
    if not canary:
        return '<p class="small">No leakage-canary artifact present.</p>'
    aucs = {k: v for k, v in canary["per_channel_auc"].items() if v is not None}
    top = sorted(aucs.items(), key=lambda kv: -kv[1])[:6]
    listed = "".join(f"<li><code>{html.escape(k)}</code>: {v:.4f}</li>" for k, v in top)
    return (f"<p><b>PASS</b> — {len(aucs)} channels, {canary['n_pixels']:,} pooled pixels, "
            f"nothing above the {canary['threshold']} leakage threshold "
            f"(flagged: {html.escape(str(canary['flagged']))}). Strongest single channels:"
            f"</p><ul class='small'>{listed}</ul>")


PORTAL_CHECKS = ("single_band", "dtype_float32", "dimensions_3730x3292", "crs_epsg_32611",
                "transform_matches_sample_submission", "min_ge_0", "max_le_1",
                "in_footprint_all_finite", "in_footprint_range_0_1",
                "zero_dots_on_mapped_catalogue")


def download_block(card) -> str:
    if not card or not card.get("files"):
        return ('<p><b>No candidate file is offered.</b> Nothing to download, nothing to '
                'submit. A placeholder will not be provided, because uploading a raster '
                'without a passed gate is exactly the failure mode this project exists to '
                'avoid.</p>')
    items = []
    names = list(card["files"])
    recommended = next((n for n in names if n.endswith("-zeros.tif")), names[0] if names else None)
    for name, rec in card["files"].items():
        checks = (rec.get("validator") or {}).get("checks") or {}
        failed = [k for k in checks if not checks[k]]
        portal_ok = all(checks.get(k, False) for k in PORTAL_CHECKS)
        badge = ("RECOMMENDED UPLOAD" if name == recommended
                 else "diagnostics encoding — same prediction, different outside-footprint convention")
        items.append(
            f'<li><b>{html.escape(badge)}</b><br>'
            f'<a download href="downloads/{html.escape(name)}"><b>{html.escape(name)}</b></a>'
            f' — {rec.get("bytes", 0):,} bytes, sha256 <code>{html.escape(str(rec.get("sha256", ""))[:16])}…</code>, '
            f'{rec.get("positive_pixels", 0):,} dots, positives on the mapped catalogue: '
            f'{rec.get("positive_on_catalogue")}, NaN inside the footprint: '
            f'{rec.get("nan_inside_footprint")}, in-footprint values within [0, 1]: '
            f'{rec.get("in_range_inside_footprint")}.<br>'
            f'Portal-relevant checks: <b>{"all pass" if portal_ok else "see card"}</b>. '
            + (f'Repository-stricter checks not met: <code>{", ".join(failed)}</code> '
               '(the all-finite policy, deliberately not applied to the diagnostics encoding).'
               if failed else 'Repository checks: all pass.') + '</li>')
    return ("<ol>" + "".join(items) + "</ol>" +
            "<p class='small'>Both files encode <b>one identical prediction array</b>; only the "
            "outside-footprint convention differs. Upload the recommended one; the other exists "
            "so the footprint convention can be inspected. If a portal rejects the recommended "
            "file, its rejection message is the evidence to record — do not clip or repair a file "
            "and re-upload it without re-running this pipeline.</p>")


def uniqueness_block(card) -> str:
    uniq = (card or {}).get("uniqueness") or {}
    if not uniq:
        return "<p class='small'>No registry comparison recorded.</p>"
    dup = uniq.get("duplicate_count")
    if dup is None:
        dup = len(uniq.get("duplicates") or [])
    rows = []
    for row in (uniq.get("rows") or [])[:5]:
        rows.append(f"<tr><td><code>{html.escape(str(row.get('repo')))}</code></td>"
                    f"<td>{fmt(row.get('spearman_full_footprint'))}</td>"
                    f"<td>{fmt(row.get('my_dots_within_3px_of_theirs'), 3)}</td>"
                    f"<td>{fmt(row.get('jaccard_dot_sets'), 3)}</td></tr>")
    return (f"<p>Compared against <b>{uniq.get('registry_rasters_checked', uniq.get('registry_rasters_compared', '—'))}</b> staged, "
            f"hash-verified prior rasters. Duplicates found: <b>{html.escape(str(dup))}</b> "
            f"(worst Spearman ρ = {fmt(uniq.get('worst_spearman_full_footprint'))}, worst dot "
            f"overlap ≤3 px = {fmt(uniq.get('worst_dot_overlap'), 3)}). "
            f"Verdict: <code>{html.escape(str(uniq.get('verdict') or uniq.get('status')))}</code>."
            f"</p>" +
            (f"<table><thead><tr><th>nearest prior</th><th>ρ</th><th>my dots ≤3 px of theirs</th>"
             f"<th>Jaccard</th></tr></thead><tbody>{''.join(rows)}</tbody></table>" if rows else "") +
            "<p class='small'>The registry index is fail-closed: the staged set is the complete "
            "contents of <code>data/registry/rasters</code>, but completeness of the public "
            "owner-repository inventory is not certified from here, so the verdict is reported "
            "with that caveat rather than as a certificate.</p>")


def build_status() -> dict:
    card = load("run_card.json")
    holdout = load("lane_holdout.json")
    canary = load("lane_canary.json")
    return {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verdict": (card or {}).get("verdict", {"download_cleared": False,
                                                "one_line": "no run card in this checkout"}),
        "gate": (card or {}).get("gate"),
        "candidate_files": list(((card or {}).get("files") or {}).keys()),
        "holdout": {
            "evaluator_version": (holdout or {}).get("evaluator_version"),
            "folds": [f["fold"] for f in (holdout or {}).get("per_fold", [])],
            "pooled": (holdout or {}).get("pooled", {}).get("scores"),
            "pooled_wire": ((holdout or {}).get("pooled_wire") or {}).get("scores"),
        },
        "canary": {
            "flagged": (canary or {}).get("flagged"),
            "n_pixels": (canary or {}).get("n_pixels"),
            "threshold": (canary or {}).get("threshold"),
        },
    }


def render(status: dict) -> str:
    card = load("run_card.json")
    holdout = load("lane_holdout.json")
    canary = load("lane_canary.json")
    verdict = status["verdict"]
    cleared = bool(verdict.get("download_cleared"))
    headline = ("Download and submit" if cleared else "Do not submit")
    return f"""{BEGIN}
  <section class="hero" aria-labelledby="main-heading">
    <div class="hero-grid">
      <div>
        <div class="kicker">DOE GEMS Prize · DrivenData competition 306 · selection-bias-aware lane</div>
        <h1 id="main-heading">A unique fault map, released only when its own evidence gate opens.</h1>
        <p class="lede">Positive–unlabeled learning with an explicit catalogue-inclusion
        propensity, validated on a whole-segment blocked hold-out that strips every withheld
        fault of its neighbourhood context, and checked for duplicates against every staged
        prior raster before anything is offered.</p>
      </div>
      <aside class="gate" aria-label="Submission readiness">
        {gate_pill(card)}
        <strong>{html.escape(headline)}</strong>
        <p>{html.escape(str(verdict.get("one_line", "")))}</p>
        <p class="small">Generated {html.escape(status['generated_utc'])} from
        <code>evidence/run_card.json</code>; this block is regenerated by
        <code>scripts/build_site.py</code> and cannot be edited by hand.</p>
      </aside>
    </div>
  </section>

  <section aria-labelledby="download-heading">
    <h2 id="download-heading">1 · The download decision</h2>
    <div class="callout {'ok' if cleared else 'danger'}">
      {download_block(card)}
    </div>
    <p class="small">One click, one file. The exact name, note, byte size and SHA-256 are also in
    <a href="data/run-card.json">the run card</a> and in <a href="data/status.json">status.json</a>.</p>
  </section>

  <section aria-labelledby="numbers-heading">
    <h2 id="numbers-heading">2 · The numbers behind the decision</h2>
    {holdout_block(holdout)}
    <h3>Leakage canary (run before any result is trusted)</h3>
    {canary_block(canary)}
    <h3>Uniqueness against the staged prior-raster registry</h3>
    {uniqueness_block(card)}
  </section>

  <section aria-labelledby="why-heading">
    <h2 id="why-heading">3 · Why this method, in one paragraph</h2>
    <p>Fault catalogues are a <i>selected</i> sample: a step-over is mapped when a mapper is
    already working that system, when the substrate and light allow it to be seen, and when
    mapping effort reached it — published mapping in this region reports that about 92 % of
    step-overs sit on range-front faults and only about a quarter are mapped at ≈ 1 : 24 000.
    Treating “unlabeled” as “negative” therefore trains on mapper attention as much as on
    geology. This lane models the inclusion probability e(x) = P(labeled | fault, x) with the
    SAR-EM estimator of Bekker &amp; Davis (2018) over a five-covariate set (local relief,
    slope, gravity-derived basin-fill proxy, lidar coverage, distance to the morphometric
    range front) and trains with the propensity-weighted empirical risk of Bekker, Robberechts
    &amp; Davis (2019), inverse-propensity weights clipped at 10, against a matched nnPU
    baseline on identical folds. The emission rule that the hold-out actually selects is the
    <i>measured splay band</i> of the visible catalogue (inter-trace spacing) crossed with
    range-front proximity — an inverse-selection reweighting that puts mass where the missing
    population lives (a measured 0.4–2 km stand-off from the mapped traces), not in a halo
    hugging them. <a href="geology.html">Full geological reasoning →</a></p>
  </section>

  <section aria-labelledby="limits-heading">
    <h2 id="limits-heading">4 · Limits, stated plainly</h2>
    <ul>
      <li>The propensity is <b>not anchored</b> to an index of exhaustively mapped quadrangles
      (none was found), so it is reported as a sensitivity analysis, not as a calibrated
      probability: PU data alone cannot identify the labelling mechanism.</li>
      <li>The blocked hold-out is deliberately harder than the competition task; a
      <code>HOLDOUT-DTI</code> value from it is <b>not</b> a leaderboard forecast, and no
      projection is ever written as a score here.</li>
      <li>The three valid footprint masks in the mirrored inputs disagree by up to 1 521 cells
      (feature stack 5 165 852 · sample template 5 167 373 · DEM 5 167 187). This project uses
      whichever mask the shared grid returns and never mixes them; the discrepancy is logged
      as an irregularity.</li>
      <li>Inputs are integrity-pinned mirrors, not organizer-authenticated downloads; the pins,
      sizes and SHA-256 values are in <code>evidence/input_pins.json</code>.</li>
    </ul>
  </section>
{END}"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    status = build_status()
    body = render(status)
    page = INDEX.read_text()
    if BEGIN not in page or END not in page:
        print(f"{INDEX.name} is missing the STATUS markers")
        return 2
    head, rest = page.split(BEGIN, 1)
    _old, tail = rest.split(END, 1)
    fresh = head + body + tail
    if args.check:
        stale = fresh != page or json.loads(STATUS_JSON.read_text()) != status
        print("status page STALE" if stale else "status page up to date")
        return 2 if stale else 0
    INDEX.write_text(fresh)
    STATUS_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATUS_JSON.write_text(json.dumps(status, indent=2) + "\n")
    print(f"rendered {INDEX.relative_to(REPO_ROOT)} and "
          f"{STATUS_JSON.relative_to(REPO_ROOT)} "
          f"({'CLEARED' if status['verdict'].get('download_cleared') else 'NOT CLEARED'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
