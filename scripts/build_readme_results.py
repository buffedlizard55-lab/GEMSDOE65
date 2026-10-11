#!/usr/bin/env python3
"""Regenerate this session's RESULTS block in README.md from the committed receipts.

The README's numbers are generated, not typed: this script reads
``evidence/e1b_px5.json`` (the gated experiment), ``evidence/e1_px5.json`` (the
pre-amendment experiment retained for IR-65-PROP-01), ``evidence/live_run_card.json``
and the measurement receipts, and replaces the ``<!--RESULTS-->`` marker (or the
previously generated block) with the current values.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import _bootstrap  # noqa: F401,E402

from gems65.paths import EVIDENCE  # noqa: E402

ORDER = ["A2_sar_1me", "A1_sar", "A3_sar_em_1me", "B_nnpu", "C_distance_only"]
BEGIN = "<!--RESULTS-BEGIN-->"
END = "<!--RESULTS-END-->"


def load(name: str):
    p = EVIDENCE / name
    return json.loads(p.read_text()) if p.exists() else None


def tbl(e1: dict, key: str, label: str) -> str:
    b = e1[key]
    s, em = b["scores"], b["emitted_pixels"]
    rows = []
    for a in ORDER:
        if a not in s:
            continue
        r = s[a]
        rows.append(f"| `{a}` | {r['dti']:.6f} | [{r['ci95'][0]:.6f}, {r['ci95'][1]:.6f}] | "
                    f"{em[a]:,} | {r['tpw'] / em[a]:.4f} |")
    prows = [f"| paired Δ(A1_sar − {k}) | {v['delta']:+.6f} | "
             f"[{v['ci95'][0]:+.6f}, {v['ci95'][1]:+.6f}] | "
             f"{'excludes 0' if v['ci95'][0] > 0 or v['ci95'][1] < 0 else 'includes 0'} | — |"
             for k, v in b["paired_differences"].items()]
    n = s[[a for a in ORDER if a in s][0]]["withheld_positive_pixels"]
    caveat = ("\n*credit/dot here divides by the full dot budget, not by the dots that fall "
              "inside the tercile, so it is a lower bound; the tercile restricts the scoring "
              "domain only.*\n" if key == "I1_tercile_gate" else "")
    return (f"**{label}** — evaluator `{b['evaluator_version']}`, n = {n:,} withheld positive "
            f"pixels, 20 km spatial-block paired bootstrap\n\n"
            "| arm | HOLDOUT-DTI | 95% CI | dots | credit/dot |\n|---|---:|---|---:|---:|\n"
            + "\n".join(rows + prows) + "\n" + caveat)


def build() -> str:
    e1 = load("e1b_px5.json") or load("e1_px5.json")
    e1a = load("e1_px5.json")
    rc = load("live_run_card.json")
    can, ci, rf = load("leakage_canary.json"), load("catalogue_identity.json"), \
        load("range_front_variants.json")
    if e1 is None or rc is None:
        raise SystemExit("run scripts/run_lane_sar2inv.py e1b and scripts/make_submission.py first")
    dec, val, g = rc["ship_decision"], rc["validation"], rc["emission_geometry"]
    uq, two, prop = rc["uniqueness"]["summary"], rc["uniqueness"]["two_phase"], rc["propensity"]
    art = Path(rc["artifact"]).name
    q = prop["e_grid_quantiles"]
    qa = e1a["propensity_e_grid"]["quantiles_over_footprint"] if e1a else {}
    i1s, i2s = e1["I1_hide_recover"]["scores"], e1["I2_sgmc_offcat"]["scores"]
    return f"""{BEGIN}
## Results (this session)

**Verdict: `{dec['verdict']}`** — {dec['reason']}. The pre-registered ship rule
(`registry/preregistration.json`) was applied mechanically to `evidence/{'e1b_px5' if load('e1b_px5.json') else 'e1_px5'}.json`
by `scripts/make_submission.py`; no human or agent judgement entered it. **Zero submission slots
were spent and nothing was uploaded.** The artefact is published for research and clearly marked;
the site banner says the same thing in one line.

**Artefact:** [`docs/downloads/{art}`](docs/downloads/{art}) · sha256 `{val['sha256']}` ·
{val['bytes']:,} bytes · float32 · EPSG:32611 · {val['meta']['shape'][0]}×{val['meta']['shape'][1]} ·
{val['emitted_positive_pixels']:,} positive pixels (value 1.0), everything else exactly 0.0 ·
**local format checks: all {'passed' if val['all_checks_passed'] else 'FAILED'}** ({val['n_nan']} NaN,
{val['n_infinite']} inf, range [{val['min']}, {val['max']}],
{val.get('on_catalogue_positive_pixels')} dots on mapped catalogue pixels).
**Name:** `{rc['name']}` · **Note ({len(rc['note'])} chars):** `{rc['note']}`

{tbl(e1, 'I1_hide_recover', 'I1 — hide-and-recover blocked holdout (the pre-registered primary gate)')}
{tbl(e1, 'I1_tercile_gate', 'I1b — highest-propensity tercile only (the secondary gate)')}
{tbl(e1, 'I2_sgmc_offcat', 'I2 — mapped faults the catalogue does NOT contain (the instrument that matches the live task)')}

Pooled ranking AUC — I1: {", ".join(f'`{a}` {e1["I1_auc_pooled"][a]:.4f}' for a in ORDER if a in e1['I1_auc_pooled'])}
· I2: {", ".join(f'`{a}` {e1["I2_auc_pooled"][a]:.4f}' for a in ORDER if a in e1['I2_auc_pooled'])}.

**The gate fails on I1 and the lane wins on I2, and the reason is structural.** I1's withheld
truth is made of *catalogue* components contiguous with visible trace, and the organizer masks
known USGS/INGENIOUS fault pixels out of scoring, so I1 rewards exactly the pixels that cannot
score live. Consistently, the trivial proximity control is the best arm on I1
({i1s['C_distance_only']['dti']:.6f}) and the worst on I2 ({i2s['C_distance_only']['dti']:.6f}).
Re-keying the gate is an amendment to a pre-registration after results are known: **an owner
decision, not an agent one.** The site's §0 gives the full argument.

**Propensity.** Source `{prop['chosen']}` (two-inventory anchor; the EM alone is the sensitivity
arm `A3_sar_em_1me`). Spearman(EM ordering, anchor ordering) on the pooled two-inventory sample =
{prop['spearman_em_vs_anchor']:+.4f}. Anchored e: mean {prop['anchor']['e_on_catalogue_mean']:.4f}
on catalogue pixels vs {prop['anchor']['e_on_reference_mean']:.4f} on independent-inventory
off-catalogue fault pixels — the direction the hypothesis requires — spanning p01 {q['p01']:.4f} →
p99 {q['p99']:.4f} over the footprint. The EM alone collapsed to e ∈ [{qa.get('p01', float('nan')):.4f},
{qa.get('p99', float('nan')):.4f}]: irregularity **IR-65-PROP-01**, fixed by pre-registration
amendment `GEMSDOE65-PREREG-1-A1`, with both experiments retained (`evidence/e1_px5.json`,
`evidence/e1b_px5.json`). π = {e1['pi_used']:.5f} (MEASURED lower bound: the union of both public
inventories, {e1['pi_receipt']['union_px']:,} px of {e1['pi_receipt']['scored_px']:,}); ρ = P(s=1)
from population counts; weights clipped at 10; c = {prop['anchor']['c']}.

**Emission geometry** (live field): {g['dots']:,} dots, {g['on_catalogue_px']} on mapped pixels,
min distance to a mapped pixel {g['min_dist_to_visible_px']} px (300 m), median
{g['median_dist_to_visible_px']:.2f} px, {g['frac_within_300m_of_visible'] * 100:.2f} % within
300 m. The proximity control's field agrees with the shipped field on only
{rc['control_distance_only']['dot_agreement_with_shipped_field'] * 100:.2f} % of dots, so this is
not a proximity field in disguise.

**Uniqueness** ({uq['registry_rasters_checked']} accessible registry rasters; inventory
incomplete, `complete_accessible_scan = {uq['complete_accessible_scan']}`): worst Spearman ρ
**{uq['worst_spearman_full_footprint']:.4f}** (limit {uq['rho_limit']}) vs `{uq['worst_rho_submission']}`;
worst Jaccard {uq['worst_jaccard_dot_sets']:.4f} (limit {uq['jaccard_limit']}); byte-unique
{uq['byte_unique_among_checked']}, pixel-unique {uq['pixel_unique_among_checked']}. Worst forward
3-px dot overlap {two['literal_reading']['worst_forward_overlap']:.4f} (limit
{two['thresholds']['forward_overlap']}) against the dense lattice comparator
`{two['literal_reading']['worst_overlap_submission']}` — **IR-65-UNIQ-01**: that rule cannot be met
by any sparse field while dense lattice comparators are in the registry (the family measured
0.9985 for its own best candidate). Flagged for the owner, not waived.

**Leakage canary** (limit AUC ≤ {can['auc_limit']}): worst single covariate {can['worst_auc']:.4f}
(`dist_to_visible_catalogue`, the legitimate proximity control); nothing flagged.

**Catalogue identity** (MEASURED): rasterised QFaults/INGENIOUS segments cover
{ci['catalogue_covered_by_traces'] * 100:.2f} % of catalogue pixels at median distance
{ci['catalogue_to_trace_distance_px']['median']:.0f} px (max
{ci['catalogue_to_trace_distance_px']['max']:.0f} px);
{ci['catalogue_morphology']['n_components_8connected']:,} components, median
{ci['catalogue_morphology']['component_size_median_px']:.0f} px, 1-px-wide lines. Range-front
variant kept: `{rf['kept']}` ({rf['variants'][rf['kept']]['pixels']:,} isoline px, bias AUC
{rf['variants'][rf['kept']]['bias_auc_catalogue_vs_sgmc_offcat']:.4f}), byte-identical to the
stored covariate.

Full receipts: [`evidence/`](evidence/) · this session's pages:
[`docs/lane65b/index.html`](docs/lane65b/index.html)
(<https://buffedlizard55-lab.github.io/GEMSDOE65/docs/lane65b/>) · irregularities:
[`docs/research/irregularities-lane65b.md`](docs/research/irregularities-lane65b.md) ·
pass-3 re-check: [`docs/research/review-pass3.md`](docs/research/review-pass3.md) ·
shared-template divergence: [`vendor/template60/PROVENANCE.md`](vendor/template60/PROVENANCE.md) ·
cross-session drift: [`evidence/cross_session_drift.json`](evidence/cross_session_drift.json)
{END}"""


def main() -> None:
    p = ROOT / "README.md"
    s = p.read_text()
    block = build()
    if BEGIN in s and END in s:
        s = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), block, s, flags=re.S)
    elif "<!--RESULTS-->" in s:
        s = s.replace("<!--RESULTS-->", block)
    else:
        # the canonical README (from the first lane-65 session) has no marker:
        # append this session's block instead of rewriting anything
        s = s.rstrip("\n") + "\n\n---\n\n## Second independent lane-65 session " \
            "(`arena/98cb5eb2-gemsdoe65`, 2026-10-11)\n\n" \
            "Merged into the canonical repository without overwriting any of it: the first\n" \
            "lane-65 session (`arena/1217c9a0-gemsdoe65`, PRs #7 and #9) keeps the canonical\n" \
            "site, run card, guards and tests; this session's pages live under\n" \
            "[`docs/lane65b/`](docs/lane65b/index.html) and its receipts are separately named.\n" \
            "Both sessions reached a **negative** verdict by different routes, and the\n" \
            "cross-session drift check shows the two fields are not duplicates.\n\n" \
            + block + "\n"
    p.write_text(s)
    print(f"[readme] results block regenerated ({len(block):,} chars)")


if __name__ == "__main__":
    main()
