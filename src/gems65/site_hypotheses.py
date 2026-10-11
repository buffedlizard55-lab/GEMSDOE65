"""The ranked candidate-hypothesis page, kept out of site.py for readability.

Renders ``evidence/hypotheses.json`` (written by ``scripts/hypotheses.py``) and
the same content as ``HYPOTHESES.md`` for GitHub readers, so the page and the
markdown can never disagree.
"""
from __future__ import annotations

from pathlib import Path

from .site import chip, esc, fmt, page, table

UNRUN = '<span class="chip warn">NOT YET RUN</span>'


def _status(c: dict, tp: dict | None) -> str:
    if not c.get("validated_here"):
        return UNRUN
    if tp and not tp.get("supported"):
        return '<span class="chip bad">REJECTED</span>'
    return chip(True, "SUPPORTED", "REJECTED")


def hypotheses_page(ev: dict, dec: dict, root: str = "") -> str:
    h = ev.get("hypotheses") or {}
    q = h.get("qfault_offset_measurement") or {}
    tp = h.get("thermal_pathway_result")
    dist = q.get("fraction_further_than_px") or {}
    cnt = q.get("count_further_than_px") or {}

    rows = [[f"#{c['rank']}",
             f"<b>{esc(c['name'])}</b><br><span class='mut'>{esc(c['layers'])}</span>",
             esc(c["expected_dti_gain"]), esc(c["implementation_cost"]),
             _status(c, tp)] for c in h.get("hypotheses", [])]

    detail = []
    for c in h.get("hypotheses", []):
        src = c.get("external_source") or {}
        link = src.get("doi") or src.get("url") or ""
        src_line = esc(src.get("name", "none needed"))
        if link:
            src_line += f' — <a href="{link}">{esc(link)}</a>'
        detail.append(f"""<h3>#{c['rank']} — {esc(c['name'])} {_status(c, tp)}</h3>
<div class="kv">
<p><b>Layers</b> {esc(c['layers'])}</p>
<p><b>Physical signature</b> {esc(c['physical_signature'])}</p>
<p><b>Why it catches a fault missing from the catalogue</b> {esc(c['why_it_catches_a_missing_fault'])}</p>
<p><b>How it differs from what this repo family has already done</b> {esc(c['difference_from_repo'])}</p>
<p><b>Expected DTI gain</b> {esc(c['expected_dti_gain'])} &nbsp;&nbsp;
   <b>Implementation cost</b> {esc(c['implementation_cost'])}</p>
<p><b>External source</b> {src_line}</p>
<p><b>Obtainable?</b> {esc(src.get('obtainability', 'n/a'))}</p>
<p><b>Validated here?</b> {esc(c.get('validation_note', ''))}</p>
</div>""")

    if tp:
        tp_block = (
            "<p>The thermal-fluid pathway layer (hot springs, well temperatures and "
            "geothermometry) was blended into the emission ranking at predeclared weights, "
            "holding the fitted model and the propensity field completely fixed, so only the "
            "order the emission rule walks changes:</p>"
            + table(["Blend weight lambda", "Dots", "HOLDOUT-DTI", "TP_w"],
                    [[str(r["lambda"]), f"{r['n_dots']:,}", fmt(r["holdout_dti"]), fmt(r["tpw"], 0)]
                     for r in tp["rows"]]
                    + [["<b>decision</b>",
                        f"<b>{'supported' if tp['supported'] else 'not supported'}</b>",
                        f"<b>baseline {fmt(tp['baseline_lambda0_dti'])}</b>", ""]])
            + "<p class='mut'>Every weight above zero makes the file worse, so the layer is "
              "<b>not</b> promoted and no submission slot is spent on it. The layer alone is "
              "informative — hot sites carry "
            + fmt(100 * ((tp.get("canary") or {}).get("rate_where_feature_nonzero") or 0), 3)
            + "% withheld truth against a " + fmt(100 * ((tp.get("canary") or {}).get("base_rate") or 0), 3)
            + "% base rate — but it is redundant with the existing design at the margin that "
              "decides the score. A negative result, kept as a deliverable.</p>")
    else:
        tp_block = "<p>Not yet run.</p>"

    body = f"""
<h1>Candidate hypotheses, ranked</h1>
<p>{esc(h.get('ranking_rule', ''))}</p>
<p class="mut">Generated from <code>evidence/hypotheses.json</code>. This register exists because
the protocol forbids promoting an unvalidated layer into a submission, so the ranking is written
to be acted on in order, not read as a wish list.</p>

<h2>Summary</h2>
{table(["Rank", "Hypothesis and layers", "Expected gain", "Cost", "Status here"], rows)}

<h2>Measured prior for the top-ranked hypothesis</h2>
<p>The rules state the scored labels come from the <b>USGS Quaternary Fault and Fold Database</b>
plus expert-identified new faults, while the training labels came from the <b>INGENIOUS</b> Great
Basin compilation. Measuring the USGS side against the training catalogue, using the clipped trace
table already on disk ({esc(q.get('in_footprint'))} traces with a centroid inside the footprint):</p>
{table(["Distance of the trace centroid from the nearest catalogue pixel", "Traces", "Share"],
       [["more than 1 px (100 m)", f"{cnt.get('1', 0)}", f"{100 * dist.get('1', 0):.1f}%"],
        ["more than 2 px (200 m)", f"{cnt.get('2', 0)}", f"{100 * dist.get('2', 0):.1f}%"],
        ["more than 3 px (300 m) — the metric's own kernel radius",
         f"{cnt.get('3', 0)}", f"{100 * dist.get('3', 0):.1f}%"],
        ["more than 5 px (500 m)", f"{cnt.get('5', 0)}", f"{100 * dist.get('5', 0):.1f}%"],
        ["more than 10 px (1 km)", f"{cnt.get('10', 0)}", f"{100 * dist.get('10', 0):.1f}%"]])}
<p class="mut">Stated caveat: a centroid is a summary point of a clipped trace, so a long trace can
still touch the catalogue at one end. This is an upper bound on the opportunity, not an estimate
of it.</p>

<h2>The locally runnable candidate was tested and rejected</h2>
{tp_block}

<h2>The candidates in full</h2>
{''.join(detail)}

<h2>What happens next, in order</h2>
<p>{esc(h.get('next_action', ''))}</p>
<p class="mut">Nothing above may be promoted into a submission before it beats the current arm on
the same blocked draw — which is why the multi-seed repeat is the first item of remaining work.</p>
"""
    return page("Hypotheses — GEMSDOE65", "hypotheses.html", body, root=root)


def render_md(ev: dict) -> str:
    h = ev.get("hypotheses") or {}
    q = h.get("qfault_offset_measurement") or {}
    tp = h.get("thermal_pathway_result")
    L = ["# Candidate hypotheses, ranked", "",
         f"_{h.get('ranking_rule', '')}_", "",
         "Generated from `evidence/hypotheses.json` by `src/gems65/site_hypotheses.py`; "
         "do not edit by hand.", "",
         "| Rank | Hypothesis | Expected gain | Cost | Status here |", "|---|---|---|---|---|"]
    for c in h.get("hypotheses", []):
        if not c.get("validated_here"):
            status = "not yet run"
        elif tp and not tp["supported"]:
            status = "REJECTED on the blocked holdout"
        else:
            status = "SUPPORTED"
        L.append(f"| {c['rank']} | {c['name']} | {c['expected_dti_gain']} | "
                 f"{c['implementation_cost']} | {status} |")
    if q:
        L += ["", "## Measured prior: the organisers' own second inventory is largely absent "
                  "from the training labels", "",
              f"{q.get('in_footprint')} traces have a centroid inside the footprint. Share whose "
              "centroid lies beyond each distance from the nearest catalogue pixel:", "",
              "| Distance | Traces | Share |", "|---|---|---|"]
        for t in ("1", "2", "3", "5", "10"):
            L.append(f"| > {t} px | {(q.get('count_further_than_px') or {}).get(t)} | "
                     f"{100 * (q.get('fraction_further_than_px') or {}).get(t, 0):.1f}% |")
        L += ["", "A centroid is a summary point of a clipped trace, so this is an upper bound.",
              ""]
    if tp:
        L += ["## The locally runnable candidate was rejected", "",
              "| Blend weight lambda | Dots | HOLDOUT-DTI | TP_w |", "|---|---|---|---|"]
        for r in tp["rows"]:
            L.append(f"| {r['lambda']} | {r['n_dots']:,} | {r['holdout_dti']:.6f} | {r['tpw']:.0f} |")
        L += ["", f"Decision: **{'supported' if tp['supported'] else 'not supported'}** "
                  f"(baseline lambda = 0 at {tp['baseline_lambda0_dti']:.6f}). The layer is not "
                  "promoted and no submission slot is spent on it.", ""]
    L += ["## Full register", ""]
    for c in h.get("hypotheses", []):
        src = c.get("external_source") or {}
        L += [f"### #{c['rank']} — {c['name']}", "",
              f"- **Layers:** {c['layers']}",
              f"- **Physical signature:** {c['physical_signature']}",
              f"- **Why it catches a fault missing from the catalogue:** "
              f"{c['why_it_catches_a_missing_fault']}",
              f"- **Difference from this repo family:** {c['difference_from_repo']}",
              f"- **Expected DTI gain:** {c['expected_dti_gain']}",
              f"- **Implementation cost:** {c['implementation_cost']}",
              f"- **External source:** {src.get('name', 'none needed')} "
              f"{src.get('doi') or src.get('url', '')}",
              f"- **Obtainable?** {src.get('obtainability', 'n/a')}",
              f"- **Validated here?** {c.get('validation_note', '')}", ""]
    L += ["## Next action", "", h.get("next_action", ""), ""]
    return "\n".join(L)


def write_md(ev: dict, path: Path) -> Path:
    path = Path(path)
    path.write_text(render_md(ev), encoding="utf-8")
    return path
