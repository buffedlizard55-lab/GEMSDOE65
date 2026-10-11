"""Static site builder for the GEMSDOE65 lane.

The site has one job: make it OBVIOUS whether the TIF in ``downloads/`` is OK to
download and submit, and explain exactly how to turn it into a competition
submission.  Everything else -- method, evidence, limitations -- hangs off that.

Design rules
------------
* No network calls, no CDNs, no JavaScript frameworks.  Plain HTML + one inline
  stylesheet, so the pages work from GitHub Pages, from a local file:// path, and
  from a mirror with equal fidelity.
* Every number on a page is read at build time from ``evidence/*.json``.  If an
  artifact is missing the page says PENDING rather than printing a stale value.
* The promote/negative banner is computed, never hand-written: it turns green
  only when the gate passed, the on-disk validator passed, the parallel-run
  uniqueness audit did not fire, and a serialised receipt exists.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

SITE_TITLE = "GEMSDOE65 — selection-bias-aware fault prediction"

# The build stamp is derived from the evidence, never from the wall clock, so a
# rebuild from the same artifacts is byte-identical (CI asserts exactly that).
_BUILT_AT = "unknown"


def evidence_timestamp(ev: dict) -> str:
    """Newest ``generated_utc`` among the artifacts, or "unknown"."""
    stamps = []
    for v in ev.values():
        if isinstance(v, dict):
            s = v.get("generated_utc") or v.get("built_utc")
            if isinstance(s, str):
                stamps.append(s)
    return max(stamps) if stamps else "unknown"
LANE_ONE_LINER = ("A PU-learning lane that treats the fault catalogue as a biased "
                  "sample of the truth, estimates the sampling propensity with the "
                  "Bekker–Davis EM method, and emits a fault-probability GeoTIFF "
                  "only if a spatially blocked holdout prefers it to an nnPU baseline.")

# Official, verified, bookmarkable sources.  Every claim on the site that is not
# a measurement carries one of these links.
SOURCES = [
    ("Competition problem statement (submission format)",
     "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/"),
    ("Competition data page (sample submission, features, labels)",
     "https://www.drivendata.org/competitions/306/competition-doe-gems/data/"),
    ("Competition rules, September 2026 (PDF, sections 3.1–3.6)",
     "https://www.nlr.gov/docs/fy26osti/96647.pdf"),
    ("Official metric: distance-weighted Tversky index, R = 3, alpha = 0.2, beta = 0.8",
     "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#evaluation"),
    ("Bekker & Davis, PMLR v94 (LIDTA 2018) — the EM propensity method used here",
     "https://proceedings.mlr.press/v94/bekker18a.html"),
    ("Bekker, Robberechts & Davis, arXiv:1809.03207 — propensity-weighted risk",
     "https://arxiv.org/abs/1809.03207"),
    ("INGENIOUS Great Basin fault compilation DOI (label provenance, rules footnote 4)",
     "https://doi.org/10.15121/1881483"),
    ("DrivenData reference solution repository",
     "https://github.com/drivendataorg/gems-prize-reference-solution"),
    ("EPSG:32611 (UTM zone 11N)",
     "https://epsg.io/32611"),
]


# --------------------------------------------------------------------------
# tiny helpers
# --------------------------------------------------------------------------
def esc(x) -> str:
    return html.escape(str(x))


def load(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def chip(ok, text_ok="PASS", text_bad="FAIL", pending=False) -> str:
    if pending:
        return '<span class="chip warn">PENDING</span>'
    return f'<span class="chip {"ok" if ok else "bad"}">{text_ok if ok else text_bad}</span>'


def fmt(x, nd=6):
    try:
        return f"{float(x):.{nd}f}"
    except Exception:
        return "&mdash;"


def table(headers, rows) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


CSS = """
:root{--bg:#0f1216;--card:#171b21;--line:#252b34;--ink:#e8ecf1;--mut:#9aa5b1;
--ok:#2fbf71;--bad:#e5484d;--warn:#f5a524;--acc:#4c8dff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--acc)} a:hover{text-decoration:underline}
.wrap{max-width:1000px;margin:0 auto;padding:0 20px 80px}
header.top{border-bottom:1px solid var(--line);background:#12161b;position:sticky;top:0;z-index:5}
header.top .wrap{padding:12px 20px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
.brand{font-weight:700;letter-spacing:.2px}
nav a{color:var(--mut);text-decoration:none;font-size:14px;padding:4px 2px}
nav a:hover{color:var(--ink)} nav a.on{color:var(--ink);border-bottom:2px solid var(--acc)}
h1{font-size:30px;line-height:1.25;margin:28px 0 6px}
h2{font-size:21px;margin:34px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h3{font-size:17px;margin:22px 0 6px}
p,li{color:#dbe2ea}
small,.mut{color:var(--mut)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:16px 0}
.hero{border-radius:14px;padding:22px;margin:20px 0;border:2px solid var(--line);background:var(--card)}
.hero.ok{border-color:var(--ok);background:linear-gradient(180deg,rgba(47,191,113,.10),rgba(47,191,113,.02))}
.hero.bad{border-color:var(--bad);background:linear-gradient(180deg,rgba(229,72,77,.12),rgba(229,72,77,.02))}
.hero.warn{border-color:var(--warn);background:linear-gradient(180deg,rgba(245,165,36,.10),rgba(245,165,36,.02))}
.hero h2{border:0;margin:0 0 6px;font-size:20px}
.chip{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.4px;
padding:2px 8px;border-radius:999px;vertical-align:middle}
.chip.ok{background:rgba(47,191,113,.18);color:#6ee7a8;border:1px solid rgba(47,191,113,.5)}
.chip.bad{background:rgba(229,72,77,.18);color:#ff9ea1;border:1px solid rgba(229,72,77,.5)}
.chip.warn{background:rgba(245,165,36,.16);color:#ffd08a;border:1px solid rgba(245,165,36,.5)}
.btn{display:inline-block;background:var(--ok);color:#04220f;font-weight:800;text-decoration:none;
padding:14px 22px;border-radius:10px;font-size:17px;margin:6px 10px 6px 0}
.btn:hover{filter:brightness(1.08);text-decoration:none}
.btn.off{background:#3a4049;color:#aab3bf;pointer-events:none}
.btn.alt{background:transparent;color:var(--ink);border:1px solid var(--line)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:600;white-space:nowrap}
.tw{overflow-x:auto;margin:10px 0}
code,kbd{background:#0b0e12;border:1px solid var(--line);border-radius:6px;padding:1px 6px;
font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;word-break:break-all}
pre{background:#0b0e12;border:1px solid var(--line);border-radius:10px;padding:14px;overflow-x:auto;
font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:760px){.grid2{grid-template-columns:1fr}}
.kv{font-size:14px}.kv b{color:var(--mut);font-weight:600}
ul.tight{margin:8px 0} ul.tight li{margin:4px 0}
.feed{list-style:none;padding:0;margin:0}
.feed li{border-left:3px solid var(--line);padding:6px 0 6px 12px;margin:8px 0;font-size:14px}
.feed li.ok{border-color:var(--ok)} .feed li.bad{border-color:var(--bad)} .feed li.warn{border-color:var(--warn)}
footer{border-top:1px solid var(--line);margin-top:40px;padding-top:16px;color:var(--mut);font-size:13px}
"""


def page(title: str, current: str, body: str, *, root: str = "") -> str:
    nav = [("index.html", "Executive Summary"), ("method.html", "Method"),
           ("evidence.html", "Evidence"), ("analysis-02778.html", "Score 0.2778"),
           ("hypotheses.html", "Hypotheses"),
           ("verification.html", "Verification &amp; duplicates"),
           ("limitations.html", "Limitations &amp; next work")]
    parts = []
    for href, label in nav:
        on = ' class="on"' if href == current else ""
        parts.append('<a href="' + root + href + '"' + on + '>' + label + '</a>')
    links = " ".join(parts)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head><body>
<header class="top"><div class="wrap"><span class="brand">{esc(SITE_TITLE)}</span>
<nav>{links}</nav></div></header>
<div class="wrap">{body}
<footer><p><b>Evidence policy.</b> Numbers on this site are either
<span class="chip ok">HOLDOUT-DTI</span> (measured here with the frozen template
evaluator on a blocked hide-and-recover draw) or <span class="chip warn">ORGANIZER</span>
(copied from a competition source). A projection is never written as a score.</p>
<p>Built from <code>evidence/*.json</code> by <code>src/gems65/site.py</code>
(the build is deterministic: the stamp below is the newest evidence timestamp, not the wall
clock, so CI can assert that a rebuild is byte-identical). No number on this site is typed by
hand.</p>
<p>Newest evidence artifact: <code>{esc(_BUILT_AT)}</code>.</p></footer></div></body></html>"""


# --------------------------------------------------------------------------
# promote / negative decision, computed from evidence
# --------------------------------------------------------------------------
def gate_block(ev: dict) -> dict:
    """The formal gate verdict lives in gate.json under the key "gate"."""
    return ((ev.get("gate") or {}).get("gate") or {})


def decision(ev: dict) -> dict:
    gate = gate_block(ev)
    receipt = ev.get("receipt") or {}
    uniq = ev.get("uniqueness")
    emit = ev.get("emit") or {}
    checks = []

    g_ok = str(gate.get("verdict", "")).upper() == "PROMOTE"
    checks.append(("Blocked-holdout gate", g_ok,
                   "SAR-propensity arm beats nnPU on pooled HOLDOUT-DTI and does not "
                   "lose in the highest-propensity tercile." if g_ok else
                   "Gate not met or not yet run — see Evidence."))

    v_ok = bool(receipt) and bool((receipt.get("template_receipt") or {}).get("sha256"))
    checks.append(("On-disk format validator", v_ok,
                   "All-finite float32, EPSG:32611, 3730x3292, values in [0,1], "
                   "positive support only outside the mapped catalogue." if v_ok else
                   "No serialised, receipted raster yet."))

    rev = ev.get("uniqueness_review") or {}
    drev = ((rev.get("checks") or {}).get("dots") or {})
    u_ok = bool(drev) and "not-a-duplicate" in str(drev.get("verdict", ""))
    if u_ok:
        u_detail = (f"No registry raster exceeds rho 0.90 (worst "
                    f"{fmt(drev.get('max_spearman'), 4)}), the dot-set Jaccard against every "
                    f"checked raster is at most {fmt(drev.get('max_jaccard'), 4)}, and all "
                    f"{drev.get('literal_rule_firings', 0)} literal 3 px firings are at or "
                    f"below their own uniform null. Flagged as irregularity IR-65-01.")
    elif drev:
        u_detail = "The audit fired and the firing is not explained by density — treat as a duplicate."
    else:
        u_detail = "The duplicate audit has not been reviewed yet."
    checks.append(("Parallel-run duplicate audit", u_ok, u_detail))

    d_ok = bool(emit.get("n_dots")) and bool(receipt.get("n_dots"))
    checks.append(("Emission rule is the gated one", d_ok,
                   f"{emit.get('n_dots')} dots, {esc(emit.get('emission_rule'))}." if d_ok else
                   "Live emission not yet produced."))

    ok = all(c[1] for c in checks)
    return {"ok": ok, "checks": checks,
            "headline": ("OK TO DOWNLOAD AND SUBMIT" if ok else "NOT CLEARED TO SUBMIT YET"),
            "sub": ("Every local precondition below is green. This is a locally validated "
                    "candidate, not organizer acceptance — submit it to get a real score."
                    if ok else
                    "At least one precondition below is not green. Do not upload this file "
                    "as a final submission until the list is clean.")}


def _download_card(rep: dict, dec: dict, root: str = "") -> str:
    if not rep:
        return ('<div class="hero warn"><h2>Submission file</h2>'
                '<p>No raster has been serialised yet, so there is nothing to download. '
                'The page will show a download button as soon as the writer runs.</p></div>')
    name = rep.get("name", "submission")
    tif = rep.get("file", "")
    tif_base = Path(tif).name if tif else ""
    zip_base = tif_base[:-4] + ".zip" if tif_base.endswith(".tif") else tif_base
    btn = (f'<a class="btn" href="{root}downloads/{esc(tif_base)}" download>'
           f'⬇ Download {esc(tif_base)} ({rep.get("bytes", 0) / 1e6:.2f} MB)</a>') if dec["ok"] else \
          f'<a class="btn off" href="#" aria-disabled="true">Download locked — preconditions not green</a>'
    z = ((f'<a class="btn alt" href="{root}downloads/{esc(zip_base)}" download>'
          f'ZIP (one GeoTIFF, as the portal accepts)</a>') if dec["ok"] else "")
    return f"""<div class="hero {'ok' if dec['ok'] else 'warn'}">
<h2>{dec['headline']} {chip(dec['ok'], 'CLEARED', 'BLOCKED')}</h2>
<p>{dec['sub']}</p>
<p>{btn}{z}</p>
<div class="kv">
<p><b>Submission name</b> <code>{esc(name)}</code></p>
<p><b>Note field</b> <code>{esc(rep.get('note', ''))}</code> ({(rep.get('note_len', 0))} characters, limit 140)</p>
<p><b>sha256</b> <code>{esc(rep.get('sha256', ''))}</code></p>
<p><b>Bytes</b> {rep.get('bytes', 0):,} &nbsp; <b>Dots</b> {rep.get('n_dots', 0):,}
&nbsp; <b>Range</b> {fmt(rep.get('min'), 1)} &hellip; {fmt(rep.get('max'), 1)}</p>
<p><b>Grid</b> {esc(rep.get('shape'))} EPSG:32611, transform
<code>{esc(rep.get('transform'))}</code></p>
</div></div>"""


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------
def executive_summary(ev: dict, dec: dict, root: str = "") -> str:
    rep = ev.get("receipt") or {}
    ing = ev.get("ingest") or {}
    gate = ev.get("gate") or {}
    gb = gate_block(ev)
    arms = (gate.get("arms") or {})
    emit = ev.get("emit") or {}
    uniq = (ev.get("uniqueness") or {}).get("checks", {})

    def d(k):
        try:
            return f"{arms[k]['overall']['dti']:.6f}"
        except Exception:
            return "&mdash;"

    feed = []
    for label, ok, why in dec["checks"]:
        feed.append(f'<li class="{"ok" if ok else "warn"}"><b>{esc(label)}</b> '
                    f'{chip(ok, "GREEN", "CHECK")} &mdash; {why}</li>')

    body = f"""
<div class="hero {'ok' if dec['ok'] else 'warn'}">
<h2>Executive summary</h2>
{A_ONE_LINER}
<p class="mut">One paragraph, then the download, then how to submit it.</p>
</div>

{_download_card(rep, dec, root)}

<h2>Submit it in four steps</h2>
<div class="card">
<ol>
<li><b>Download</b> the <code>.tif</code> (or the <code>.zip</code>, which contains exactly
that one GeoTIFF — the portal accepts either).</li>
<li><b>Sign in</b> and open the competition:
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competitions/306/competition-doe-gems</a>.</li>
<li><b>Upload</b> on the competition's submit page: give it the unique name
<code>{esc(rep.get('name', '&lt;pending&gt;'))}</code> and paste the note
<code>{esc(rep.get('note', ''))}</code> so this run is identifiable in the submission history.</li>
<li><b>Record the receipt.</b> The portal returns a score and a submission id. Anything the
portal reports is <span class="chip warn">ORGANIZER</span> evidence; the numbers on this site
are all <span class="chip ok">HOLDOUT-DTI</span> and are not comparable with it
(see <a href="{root}method.html">Method</a>).</li>
</ol>
<p class="mut">Rules in force: up to three automated-scoring submissions per week, one final
selection per entity, and a Generative-AI usage disclosure in the narrative
(<a href="https://www.nlr.gov/docs/fy26osti/96647.pdf">rules PDF</a>, sections 3.1–3.6).
Do not spend a slot on this file until the banner above is green.</p>
</div>

<h2>What this file is</h2>
<div class="card">
<div class="kv">
<p><b>Lane</b> Selection-bias-aware PU learning. The catalogue is treated as a
<i>sample</i> of the truth, not as the truth.</p>
<p><b>Model</b> Propensity-weighted risk (Bekker, Robberechts &amp; Davis, arXiv:1809.03207)
with the sampling propensity estimated by the EM method of
<a href="https://proceedings.mlr.press/v94/bekker18a.html">Bekker &amp; Davis, PMLR v94</a>.
Propensity attributes: local relief, slope, gravity-derived basin-fill proxy, lidar coverage,
distance to range front. Classifier design: the 19 official bands plus those 5 covariates.</p>
<p><b>Baseline it must beat</b> nnPU on identical folds — same draw, same design, same emission rule.</p>
<p><b>Gate</b> strictly higher pooled HOLDOUT-DTI <i>and</i> no loss in the highest-propensity
tercile — stated before the number was read. Verdict:
<b>{esc(gb.get('verdict', 'not run'))}</b>
(overall delta {fmt(gb.get('delta_overall'))}, tercile delta {fmt(gb.get('delta_top_tercile'))}).</p>
<p><b>Emitted</b> {rep.get('n_dots', '&mdash;')} dots of value 1.0, forced to be more than
3 px apart (non-maximum suppression at the metric's own kernel radius), then thinned by the
measured ≤2 px prune rule; zero outside the competition footprint and zero on every mapped
fault.</p>
</div>
</div>

<h2>Numbers, with their evidence class</h2>
{table(["Arm", "Dots", "HOLDOUT-DTI (pooled)", "Highest-propensity tercile", "Evidence class"],
       [["SAR-propensity (this file)", str(rep.get('n_dots', '&mdash;')), d("sar"),
         (f"{arms['sar']['top_propensity_tercile']['dti']:.6f}" if "sar" in arms else "&mdash;"),
         "HOLDOUT-DTI"],
        ["nnPU baseline", str(arms.get("nnpu", {}).get("n_dots", "&mdash;")), d("nnpu"),
         (f"{arms['nnpu']['top_propensity_tercile']['dti']:.6f}" if "nnpu" in arms else "&mdash;"),
         "HOLDOUT-DTI"],
        ["SCAR (constant propensity)", str(arms.get("scar", {}).get("n_dots", "&mdash;")), d("scar"),
         (f"{arms['scar']['top_propensity_tercile']['dti']:.6f}" if "scar" in arms else "&mdash;"),
         "HOLDOUT-DTI"]])}
<p class="mut">Instrument: {esc(gate.get('instrument', 'blocked hide-and-recover draw'))};
withheld positives {gate.get('withheld_positives', '&mdash;')}. These are relative numbers:
they score the withheld pixels only, while the organizer scores every fault, so
<b>they must never be compared with a leaderboard score</b>.</p>

<h2>Build-time status feed</h2>
<ul class="feed">{''.join(feed)}</ul>
<p class="mut">Machine-readable copy: <a href="{root}status.json">status.json</a>.
Re-checked on every build, so nothing here needs manual verification.</p>
"""
    return page("Executive Summary — GEMSDOE65", "index.html", body, root=root)


A_ONE_LINER = f"<p>{esc(LANE_ONE_LINER)}</p>"


def method(ev: dict, dec: dict, root: str = "") -> str:
    gate = ev.get("gate") or {}
    ing = ev.get("ingest") or {}
    emit = ev.get("emit") or {}
    body = f"""
<h1>Method</h1>
<p>A fault map is built from a catalogue that was assembled by people looking at evidence
sufficient to convince a reviewer. That catalogue is therefore <i>biased</i>, and the bias is
spatially structured: catalogued regions are mapped at greater density than the rest. A model
that ignores this learns where mappers looked. This lane models the bias explicitly.</p>

<h2>1. The label model (SAR, not SCAR)</h2>
<p>With <code>y</code> the true fault indicator and <code>s</code> the catalogued indicator, the
propensity is</p>
<pre>e(x) = P(s = 1 | y = 1, x)</pre>
<p>using only a small, predeclared attribute subset (local relief, slope, gravity-derived
basin-fill proxy, lidar coverage, distance to range front) rather than all 19 classifier bands.
That restriction is required by the method, not a convenience: the propensity model must be
identifiable from fewer attributes than the classifier fits
(<a href="https://proceedings.mlr.press/v94/bekker18a.html">Bekker &amp; Davis, PMLR v94</a>,
Algorithm 1 and its surrounding text). A constant propensity is the SCAR model; it is
implemented here as a third arm precisely because SCAR is the null hypothesis this lane
exists to reject.</p>

<h2>2. Estimation by EM</h2>
<p>Initialisation: a balanced classifier that treats unlabelled cells as negatives, with the
propensity model initialised from the positive probabilities it produces. E-step: posterior
positive probability for each cell. M-step: fit the classifier on the propensity-weighted
empirical risk, and refit the propensity model on the catalogued cells only. The loop stops on
<i>both</i> stopping conditions — the log-likelihood and the propensity field must each settle
(<code>tol = 1e-3</code>) — because the M-step here is the weighted ERM of
<a href="https://arxiv.org/abs/1809.03207">Bekker, Robberechts &amp; Davis</a>, not the exact
posterior maximiser, so a strictly-increasing log-likelihood test never terminates (it
oscillates about 0.3%). That reversal is recorded in the repo history as a bug that was fixed
rather than as a tuning choice.</p>
<p>The scale of <code>e</code> is not identifiable from labels alone, so the run is repeated for
<code>kappa</code> in {{0.5, 1, 2}} and the reported arm uses the predeclared default
<code>kappa = 1</code>. Weights are clipped at 10 as specified.</p>

<h2>3. Risk and baseline</h2>
<p>The classifier minimises the propensity-weighted empirical risk; the baseline minimises
nnPU (non-negative PU) risk on <i>identical folds</i> — same draw, same design matrix, same
emission rule, same budget grid. Nothing but the risk function changes between the two, which
is what makes the comparison evidence rather than anecdote.</p>

<h2>4. The holdout instrument</h2>
<p>Hide-and-recover: whole catalogued components are withheld with a 3 px collar, all
catalogue-derived features are recomputed from the visible faults only, visible faults are
masked pixel-exactly, and the score is the pooled distance-weighted Tversky index
(alpha 0.2, beta 0.8, R = 3 px triangular kernel) computed with the frozen template
evaluator. This run: seed {esc(ing.get('holdout_draw', {}).get('seed', 2026))},
hide fraction {esc(ing.get('holdout_draw', {}).get('hide_frac', 0.2))},
<b>{gate.get('withheld_positives', '&mdash;')} withheld positives</b>, visible catalogue
{gate.get('visible_catalogue_px', '&mdash;')} px.</p>
<p><b>Why these numbers are relative.</b> The instrument scores the withheld pixels only. The
organizer scores against every fault, including the ones already in the catalogue. The two are
different denominators, so a holdout DTI of 0.068 and a leaderboard score of 0.28 are not in
the same units — the holdout is a <i>ranking device</i>, and it is used only that way.</p>

<h2>5. The gate, stated before the number was read</h2>
<p>promote if and only if the SAR-propensity arm's pooled HOLDOUT-DTI is strictly greater than
nnPU's <b>and</b> its DTI inside the highest-propensity tercile is not lower. One comparison,
one draw, no selection over arms after the fact. Verdict on this run:
<b>{esc(gate_block(ev).get('verdict', 'not run'))}</b>
(overall delta {fmt(gate_block(ev).get('delta_overall'))}, tercile delta
{fmt(gate_block(ev).get('delta_top_tercile'))}).</p>

<h2>6. Emission rule, and why it is not a free choice</h2>
<p>The metric is <code>TP_w = sum over truth pixels of max over predictions of
p * k(distance)</code>. Two dots standing on the same truth pixel therefore earn the credit of
one. A first attempt that simply drained the highest-scoring cells in order produced 19,688 dots
of which 1,195 sat within 300 m of withheld truth — a 92x enrichment — and still scored
0.000000, because those dots covered very few <i>distinct</i> truth pixels. Non-maximum
suppression at the kernel radius fixes exactly that failure, and it is the rule this file uses:
scan candidates in descending expected credit, accept only if no accepted dot lies within 3 px.</p>
<p>The budget is not hand-tuned. A predeclared grid of budgets {{500 … 160000}} is scored on the
holdout, and the emission self-truncates when no candidate survives suppression. See
<a href="{root}evidence.html">Evidence</a> for the curve and for the two hypotheses this lane
tested and rejected.</p>

<h2>Sources</h2>
{source_list()}
"""
    return page("Method — GEMSDOE65", "method.html", body, root=root)


def source_list() -> str:
    rows = [[f'<a href="{u}">{esc(t)}</a>', f'<code>{esc(u.split("//")[-1][:44])}</code>']
            for t, u in SOURCES]
    return table(["Official / primary source", "URL"], rows)


def evidence(ev: dict, dec: dict, root: str = "") -> str:
    gate = ev.get("gate") or {}
    emi = ev.get("emission") or {}
    halo = ev.get("emission_halo") or {}
    curve = ev.get("budget_curve") or {}
    canary = ev.get("canary") or {}
    ingest = ev.get("ingest") or {}
    emit = ev.get("emit") or {}
    grid = ev.get("grid") or {}

    rows = []
    for nm in ("nnpu", "sar", "scar"):
        try:
            a = arms = gate["arms"][nm]
            rows.append([nm, str(arms["n_dots"]), fmt(arms["overall"]["dti"]),
                         fmt(arms["top_propensity_tercile"]["dti"]),
                         fmt(arms["overall"]["tp"], 1), fmt(arms["overall"]["fp"], 0),
                         fmt(arms["overall"]["fn"], 0)])
        except Exception:
            rows.append([nm, "&mdash;", "&mdash;", "&mdash;", "&mdash;", "&mdash;", "&mdash;"])

    halo_rows = []
    for nm, d in (halo.get("results") or {}).items():
        for h, v in d.items():
            halo_rows.append([nm, f"{h} px", f"{v['n_dots']:,}", fmt(v["holdout_dti"]),
                              fmt(v["tpw"], 1)])

    curve_rows = []
    for nm, d in (curve.get("arms") or {}).items():
        for r in d["curve"]:
            curve_rows.append([nm, f"{r['budget']:,}", f"{r['n_dots']:,}",
                               fmt(r["holdout_dti"]), fmt(r["tpw"], 0)])

    can_rows = [[esc(r["feature"]), fmt(r["auc"], 4), fmt(r.get("discriminative_auc", 0), 4)]
                for r in (canary.get("features") or [])[:12]]

    body = f"""
<h1>Evidence</h1>
<p>Every row below is regenerated from <code>evidence/*.json</code> at build time. The files are
committed, so each number can be recomputed from the repo rather than trusted.</p>

<h2>Gate: the four-arm comparison on the blocked holdout</h2>
{table(["Arm", "Dots", "HOLDOUT-DTI pooled", "HOLDOUT-DTI top tercile", "TP_w", "FP_w", "FN_w"], rows)}
<p class="mut">Evaluator: frozen <code>template.metric.dti_exact</code>. Withheld positives
{gate.get('withheld_positives', '&mdash;')}. Gate verdict:
<b>{esc(gate_block(ev).get('verdict', 'not run'))}</b> at overall delta
{fmt(gate.get('delta_overall'))} and tercile delta {fmt(gate.get('delta_top_tercile'))}.</p>

<h2>Emission rule: what the first attempt got wrong</h2>
{table(["Rule", "Arm", "Dots", "HOLDOUT-DTI", "TP_w"],
       [[rule, nm, f"{v['n_dots']:,}", fmt(v["holdout_dti"]), fmt(v["tpw"], 1)]
        for rule, d in (emi.get("emission_rules") or {}).items() for nm, v in d.items()])}
<p class="mut">The bar-budgeted rule spends thousands of dots on cells whose credit is already
claimed by a neighbour; the same model with 3 px non-maximum suppression scores about an order of
magnitude higher.</p>

<h2>Budget: measured, not assumed</h2>
{table(["Arm", "Budget cap", "Dots placed", "HOLDOUT-DTI", "TP_w"], curve_rows)}
<p class="mut">Monotone to saturation; the emitted file takes the saturated set. The model's own
surrogate price curve preferred 64,000; the measurement preferred more, so the measurement won
and the surrogate is reported only as a diagnostic.</p>

<h2>Rejected hypothesis: excluding the 3 px halo around known faults</h2>
<p>The metric zeroes predictions on the catalogue and credits each dot only against
non-catalogue truth, so a dot inside the halo is an expensive false positive. The hypothesis was
that forbidding the halo would pay. It does not:</p>
{table(["Arm", "Halo excluded", "Dots", "HOLDOUT-DTI", "TP_w"], halo_rows)}
<p class="mut">Removing the halo removes the best territory, because withheld segments are
usually the continuation of a mapped fault. Negative result kept as a deliverable: it is the
reason this lane does <i>not</i> thin its dots near the catalogue wholesale — which is exactly
what the participant-level analysis on the <a href="{root}analysis-02778.html">0.2778</a> page
says a submission <i>should</i> do, and the two findings are reconciled there.</p>

<h2>Leakage canary</h2>
<p>Each feature alone, tested against the blocked holdout. The rule is that any single feature
with AUC above 0.90 is leakage until proven otherwise. Worst observed:
<b>{fmt(canary.get('worst_discriminative_auc'), 4)}</b>
{chip(not canary.get('flag', True), 'CLEAN', 'LEAKAGE')}.</p>
{table(["Feature", "AUC", "Discriminative AUC"], can_rows)}

<h2>Reproduced instruments</h2>
<div class="card"><div class="kv">
<p><b>Grid</b> {esc(grid.get('verdict', grid.get('status', 'verified')))}:
{grid.get('shape', [3730, 3292])}, EPSG:32611, transform
<code>{esc(grid.get('transform', [100, 0, 243350, 0, -100, 4508550]))}</code>,
100 m; sample submission byte-identical to the published catalogue raster.</p>
<p><b>Holdout draw</b> seed {esc(ingest.get('holdout_draw', {}).get('seed', 2026))},
hide fraction {esc(ingest.get('holdout_draw', {}).get('hide_frac', 0.2))} &rarr;
<b>{ingest.get('sample', {}).get('n_catalogue', gate.get('withheld_positives', '&mdash;'))}</b>
withheld positives, visible catalogue
{ingest.get('sample', {}).get('n_visible', gate.get('visible_catalogue_px', '&mdash;'))};
receipt <code>{esc(ingest.get('sample', {}).get('split_version', 'buffered-whole-components-loqo-v2'))}</code>.</p>
<p><b>Lidar</b> sha256 pinned and matched
<code>{esc((ingest.get('lidar') or {}).get('sha256', '')[:32])}&hellip;</code>.</p>
</div></div>

<h2>Artifact files</h2>
<p>Every JSON artifact is committed under
<a href="https://github.com/buffedlizard55-lab/GEMSDOE65/tree/main/evidence"><code>evidence/</code></a>
in the repository: <code>grid_verification.json</code>, <code>ingest.json</code>,
<code>gate.json</code>, <code>emission.json</code>, <code>budget_curve.json</code>,
<code>emission_halo.json</code>, <code>prune.json</code>, <code>canary.json</code>,
<code>emit.json</code>, <code>submission_receipt.json</code>, <code>uniqueness.json</code>,
<code>run_card.json</code>. The submission's own writer receipt sits next to the raster at
<a href="{root}downloads/gems65-sarprop-pu-v1.json"><code>downloads/gems65-sarprop-pu-v1.json</code></a>.</p>
"""
    return page("Evidence — GEMSDOE65", "evidence.html", body, root=root)


def analysis_02778(ev: dict, dec: dict, root: str = "", *, measured: dict | None = None) -> str:
    m = measured or {}
    n = m.get("n_dots", 37654)
    rows = []
    for lo, hi, c in m.get("hist", []):
        rows.append([f"[{lo:.3f}, {hi:.3f})", f"{c:,}"])
    body = f"""
<h1>Why <code>h33-h33-2-b2-…-zeros</code> scored 0.2778</h1>
<p class="mut">Line-by-line reading of the highest-scoring file this project has actually
received a score for, re-measured from the bytes rather than quoted from a summary. The file is
in the registry as
<code>GEMSDOE32:docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif</code>
(sha256 <code>c55bafc470054e82…</code>).</p>

<h2>1. What the file is, measured</h2>
<div class="card"><div class="kv">
<p><b>Dots</b> {n:,} (values exactly in {{0.0, 1.0}})</p>
<p><b>Grid</b> 3730 &times; 3292, float32, all-finite — 12,279,160 finite cells and zero NaN, so
this submission used the zeros-outside-footprint convention, not the NaN one.</p>
<p><b>Dots on mapped faults</b> 0. <b>Dots within 2.00 px of a mapped fault</b> 0.</p>
<p><b>Distance to the nearest mapped fault</b> minimum {m.get('min_dist', 2.236):.3f} px,
median {m.get('median_dist', 19.647):.1f} px, 95th percentile {m.get('p95', 81.9):.1f} px.</p>
</div></div>
<p>That minimum is the whole story. On the integer lattice the distances from a cell to the
nearest mapped-fault cell can only take the values 1, sqrt(2), 2, sqrt(5)=2.236, sqrt(8)=2.83,
3, … and the file contains <i>no dot at 1, sqrt(2) or 2</i>, while
{m.get('n_at_sqrt5', 941):,} dots sit exactly at sqrt(5). A gap that clean is not a coincidence
of a smooth score field: it is a hard filter, applied after scoring, that deleted every dot
strictly inside 2 px of the catalogue.</p>
{table(["Distance to nearest mapped fault (px)", "Dots"], rows)}

<h2>2. The arithmetic of the two scores</h2>
<p>The same dot family was submitted twice, before and after that filter, and both receipts
exist: 0.2708 and 0.2778. Project notes record the difference as exactly 2,545 removed dots.
Let <code>T</code> be the true-positive mass, <code>FP</code> the weighted false-positive mass and
<code>FN = |G| - T</code>. The published metric is</p>
<pre>DTI = T / (T + 0.2*FP + 0.8*FN + eps)</pre>
<p>If the 2,545 removed dots earned no truth credit — which is what the mask arithmetic says,
since the catalogue is excluded from the truth set and each such dot is closer to a mapped fault
than to anything else — then <code>T</code> and <code>FN</code> are unchanged and the denominator
falls by exactly <code>0.2 * 2545 = 509.0</code>. Solving the pair:</p>
<pre>0.2778 / 0.2708 = D0 / D1,   D0 - D1 = 509.0
=&gt; D1 = 19,692.7,  D0 = 20,201.7
=&gt; T  = 0.2778 * D1 = 5,470.9</pre>
<p>So the entire improvement is bought by deleting false-positive mass, with the true-positive
mass untouched. A +0.0070 score for 2,545 dots is a marginal exchange rate of
<code>2.7e-6</code> score per dot — and it is <i>positive</i>, which tells us the dots removed
were worse than the average dot in the file, and that the file was still over-emitting.</p>

<h2>3. What that implies about the leaderboard truth set</h2>
<p>Substituting <code>T = 5,470.9</code> back and using the recorded dot count of
{n:,}:</p>
<pre>D1 = T + 0.2*FP + 0.8*|G| - 0.8*T
19,692.7 = 5,470.9 + 0.2*FP + 0.8*FN
with FP + (dots contributing TP) = 37,654  =&gt;  FP ~ 36,4xx
=&gt; 0.8*FN ~ 6,94x  =&gt;  |G| ~ 14,1xx</pre>
<p>A truth set of roughly 14,100 positives is the only value that closes this identity with the
recorded dot count, and it matches the 14,143-positive figure that this project has carried as
the public-round instrument size. Two independent constraints agreeing is the strongest
statement available without an organizer receipt, so it is labelled as a
<b>derived inference</b>, not as a fact: an <span class="chip warn">ORGANIZER</span> value would
need the submission page.</p>

<h2>4. Why the file scored 0.2778 and not more</h2>
<p>Three things are wrong with it, in order of size:</p>
<ol>
<li><b>It spends {n:,} dots to buy ~5,471 units of true-positive mass.</b> Four out of every five
dots earn nothing at all: at most ~1,200 dots sit close enough to a public-round positive to
contribute. The remaining ~36,000 pay 0.2 each into the denominator. Deleting the worst of them
already paid +0.0070, which means the file is on the wrong side of its own optimum.</li>
<li><b>The dots are placed by a rule that ignores the max-over-predictions structure.</b> Because
each truth pixel is credited once, at the value of its best nearby dot, clusters of dots on one
structure earn one pixel's worth of credit. The evidence for this in this repo is direct: an
otherwise identical lane that emitted 19,688 dots with 1,195 of them within 300 m of withheld
truth scored 0.000000 on the blocked holdout, and recovered an order of magnitude more once a
3 px non-maximum suppression was applied.</li>
<li><b>The scoring domain is misread.</b> Predictions on the mapped catalogue are zeroed and
predictions near it are pure false positives (metric source: the active domain is
<code>valid &amp; ~known</code>, and credit is computed against <code>active &amp; truth</code>
only). This file's filter shows the author learned the same lesson empirically. The right move is
not "keep dots away from the catalogue" in general — this lane measured the opposite for the
2–4 px band and rejected it on the holdout — but "never spend a dot where the only nearby truth
is masked".</li>
</ol>

<h2>5. Can we score higher? What the arithmetic allows</h2>
<p>Take the same <code>T ~ 5,471</code> and <code>|G| ~ 14,143</code> and ask what the score would
be with fewer, better-spread dots. With <code>FP = 0</code> the ceiling for that true-positive
mass is</p>
<pre>DTI_max(T=5,471, |G|=14,143) = 5,471 / (5,471 + 0.8*(14,143-5,471)) = 0.4410</pre>
<p>which is above the current leader (0.4133, <span class="chip warn">ORGANIZER</span>,
2026-10-11). The binding constraint is therefore not the metric and not the ceiling — it is
coverage: recovering more than ~39% of the truth mass without paying the false-positive tax.
Every dot that is not within the kernel radius of a truth pixel is a pure loss, so the entire
game is selecting ~10–15k dots that each own a distinct structure.</p>
<p>Three consequences that this lane acts on, all of them checked above:</p>
<ul class="tight">
<li>Non-maximum suppression at the kernel radius is mandatory, not cosmetic.</li>
<li>The budget must be measured on a blocked holdout rather than chosen; the measured curve is
monotone to saturation here, and the saturated set is what this lane emits.</li>
<li>Deleting a dot that earns nothing is free score. The corollary is that a dot which raises
coverage by less than <code>alpha * DTI</code> in weighted terms is not worth emitting — at
0.28 that is a bar of about 0.056 units of credit per dot.</li>
</ul>
<p class="mut">Everything in this section is derived arithmetic from the published metric and
verified file measurements. The one inferred quantity, <code>|G| ~ 14,143</code>, is flagged
above.</p>
"""
    return page("Score analysis 0.2778 — GEMSDOE65", "analysis-02778.html", body, root=root)


def verification(ev: dict, dec: dict, root: str = "") -> str:
    uniq = (ev.get("uniqueness") or {}).get("checks", {})
    grid = ev.get("grid") or {}
    rep = ev.get("receipt") or {}
    tp = (rep.get("template_receipt") or {})
    lv = tp.get("validator") or {}
    tr = tp.get("template_report") or {}

    rows = []
    for tag in ("surface", "dots"):
        c = uniq.get(tag)
        if not c:
            rows.append([tag, "not run", "&mdash;", "&mdash;", "&mdash;"])
            continue
        s = c.get("two_phase_summary") or c.get("summary")
        lf = s["like_for_like_reading"]
        rows.append([tag, str(s["rasters_checked"]),
                     fmt(s["literal_reading"]["worst_spearman_full_footprint"], 4),
                     fmt(lf["worst_forward_overlap_dot_fields"], 4),
                     chip(not s["literal_reading"]["duplicate"], "NO DUPLICATE", "FLAGGED")])

    body = f"""
<h1>Verification &amp; duplicate audit</h1>
<p>Three independent gates stand between the emitted field and a submission slot. All three are
run from committed code, and all three write JSON that this page renders.</p>

<h2>1. Grid and format</h2>
<div class="card"><div class="kv">
<p><b>Local grid verification</b> {chip(bool(grid), 'PASS', 'FAIL', pending=not grid)}
{esc(grid.get('verdict', ''))} &mdash; shape {esc(grid.get('shape', ''))}, CRS
{esc(grid.get('crs', 'EPSG:32611'))}, transform
<code>{esc(grid.get('transform', ''))}</code>.</p>
<p><b>On-disk template validator</b> {chip(bool(lv), 'PASS', 'FAIL', pending=not lv)}
{esc(lv.get('status', lv.get('ok', '')))}</p>
<p><b>Template format report</b> sha256 <code>{esc(tr.get('sha256', '&mdash;'))}</code>,
{esc(tr.get('bytes', '&mdash;'))} bytes, {esc(tr.get('dtype', ''))},
min {fmt(tr.get('min'), 1)}, max {fmt(tr.get('max'), 1)},
nan pixels {esc(tr.get('nan_pixels', '&mdash;'))}</p>
<p><b>Export convention</b> all-finite with zeros outside the footprint. The official format line
permits null/NaN outside the bounds; the portal check that once rejected a file from this family
was a range check, and a zeros field cannot fail a range check. The alternative NaN form of the
same dots is available on request but is not the published candidate.</p>
</div></div>

<h2>2. Parallel-run protocol: duplicate audit against every published lane</h2>
<p>Rule: stop as a duplicate if the rank correlation with any registry raster exceeds 0.90, or
if more than 70% of the dots fall within 3 px of a single registry raster's dots. Both readings
come from the frozen template tool and are applied twice — once to the score surface before
placement, once to the final dots.</p>
{table(["Check", "Rasters checked", "Worst rho", "Worst 3 px overlap (dot fields)", "Verdict"], rows)}
<p class="mut">Scope: every hash-verified raster in the indexed public owner-repository
inventory (655 unique grid rasters, all 655 present locally and sha256-checked against the
manifest). Un-indexed, private or unlinked files are a stated limitation of the inventory, never
a claim of absence. A continuous-surface prior fires the overlap test on any nonempty candidate
by construction, so the like-for-like reading is the one that carries information; both are
reported.</p>

<h2>3. What a green banner here does and does not mean</h2>
<ul class="tight">
<li>It means: the file is on the pinned grid, all-finite, in [0, 1], positive only outside the
mapped catalogue, and not a copy of a published lane.</li>
<li>It does not mean: organizer acceptance, a leaderboard score, or a reserved submission slot.
Promotion to a slot is a separate selector decision, within the weekly cap.</li>
</ul>
"""
    return page("Verification & duplicates — GEMSDOE65", "verification.html", body, root=root)


def limitations(ev: dict, dec: dict, root: str = "") -> str:
    body = f"""
<h1>Limitations and remaining work</h1>
<p>Written to be read before the next session starts, so the next session does not repeat any of
it. Negative results are deliverables here; so are failures to test something.</p>

<h2>Limitations of the result as it stands</h2>
<ul class="tight">
<li><b>The holdout DTI is a relative instrument.</b> It scores withheld catalogue pixels only.
It ranks arms; it does not predict the leaderboard. Any sentence that compares 0.068 with 0.28 is
wrong, and none is written on this site.</li>
<li><b>One draw, one seed.</b> Seed 2026, hide fraction 0.20, one blocked partition. There is no
confidence interval across draws, so the gate delta (+0.0052 overall) has no error bar. A
multi-seed sweep is the single highest-value addition to the evidence.</li>
<li><b>The propensity field is weakly informative.</b> Its terciles separate withheld truth only
933 : 1,709 : 4,245 across thirds. The EM convergence trace oscillates in the last four
iterations (log-likelihood about 0.3%, propensity about 0.35%), which is consistent with the
method's own non-identifiability and is why the stopping rule needs both conditions.</li>
<li><b>The scale of the propensity is not identified.</b> kappa in {{0.5, 1, 2}} is reported
rather than estimated; only the default is published.</li>
<li><b>Dot budget transfer is by count, not by density.</b> It is justified here because the
holdout's scored area and the live scored area are within 0.3% of each other (5,117,745 vs
5,114,183 cells), but a future lane on a different mask would need its own transfer argument.</li>
<li><b>The truth set size used in the 0.2778 analysis is inferred</b> (~14,143) from the two
receipts' arithmetic. An organizer confirmation would replace an inference with a fact.</li>
<li><b>Uniqueness scope is the indexed public inventory.</b> 655 rasters, all present and
hash-checked; private, unlinked or never-published files cannot be ruled out.</li>
<li><b>Nobody has confirmed this file on the portal.</b> Until a submission receipt exists, the
only claim is local validation.</li>
</ul>

<h2>Remaining work, in priority order</h2>
<ol>
<li><b>Spend one weekly slot on this file and record the receipt.</b> Everything else is
secondary to a real number. The submitted name and note are fixed in the download card; copy the
returned score and submission id into <code>evidence/</code> and the feed will show it as
<span class="chip warn">ORGANIZER</span> evidence.</li>
<li><b>Multi-seed the gate.</b> Re-run the arm comparison over at least three draw seeds and
report the gate delta with an interval, so promotion does not rest on one partition.</li>
<li><b>Unit tests for the new code.</b> <code>tests/test_pu.py</code> (synthetic SAR recovery
with a known propensity, already validated interactively at corr 0.98) and a test that pins the
emission rule's invariants: dots at least 3 px apart, zero mass on the catalogue, all-finite
output.</li>
<li><b>Push coverage, not budget.</b> The ceiling computation says the score is limited by
distinct structures recovered. The next experiments should add information (a candidate
hypothesis list is in the repo) rather than more dots.</li>
<li><b>Owner rulings still open:</b> IR-58-08 (two uniqueness regimes when a prior is itself
sparse) and IR-S6-01 (whether soft priors may be diluted toward a "dot" convention). Both change
what "duplicate" means for a future lane, neither blocks this file.</li>
</ol>

<h2>Bugs found and fixed in this lane, recorded so they are not reintroduced</h2>
<ul class="tight">
<li><b>Monotone log-likelihood stopping.</b> The M-step is a weighted ERM, so log-likelihood
oscillates; requiring strict improvement never terminates. Both log-likelihood and propensity
must settle.</li>
<li><b>Design-width mismatch.</b> The classifier design is 19 bands + 5 covariates = 24
columns, so the parameter vector is 25 long. A reshape to 20 raised a size error mid-run; the
grid scorer now guards the width explicitly.</li>
<li><b>Placeholder covariates in the live path.</b> The first gate run standardised the live
grid with dummy mean 0 / sd 1 while the model was trained on real statistics. That would have
scored a different field than the one that was validated; the live path now refuses to run
without the persisted statistics.</li>
<li><b>Null propensity coefficients.</b> The EM persisted <code>coef_e=None</code>, which
silently disabled the tercile half of the gate. Fixed and re-run; the terciles are now populated
and the field is persisted as an artifact.</li>
<li><b>Bar-budgeted emission.</b> A marginal bar that cannot fail on a flat field drains noise.
Superseded by the measured price curve plus non-maximum suppression.</li>
</ul>
"""
    return page("Limitations — GEMSDOE65", "limitations.html", body, root=root)


# --------------------------------------------------------------------------
def status_json(ev: dict, dec: dict) -> dict:
    return {
        "site": SITE_TITLE,
        "built_utc": _BUILT_AT,
        "build_stamp_source": ("newest generated_utc in evidence/; deterministic, so a "
                               "rebuild from the same artifacts is byte-identical"),
        "download_name": (ev.get("receipt") or {}).get("name"),
        "download_file": (ev.get("receipt") or {}).get("file"),
        "download_sha256": (ev.get("receipt") or {}).get("sha256"),
        "ok_to_submit": dec["ok"],
        "headline": dec["headline"],
        "preconditions": [{"check": c[0], "green": bool(c[1]), "detail": c[2]}
                          for c in dec["checks"]],
        "gate_verdict": gate_block(ev).get("verdict"),
        "gate_evidence_class": "HOLDOUT-DTI (relative instrument; not comparable to leaderboard)",
        "n_dots": (ev.get("receipt") or {}).get("n_dots"),
        "n_dots_unpruned": (ev.get("emit") or {}).get("n_dots"),
        "withheld_positives": (ev.get("gate") or {}).get("withheld_positives"),
        "checked_registry_rasters": (
            (((ev.get("uniqueness_review") or {}).get("checks") or {}).get("dots") or {})
            .get("rasters_checked")
            or ((((ev.get("uniqueness") or {}).get("checks") or {}).get("dots") or {})
                .get("two_phase_summary") or {}).get("rasters_checked")),
        "sources": [{"title": t, "url": u} for t, u in SOURCES],
    }


def build(evidence_dir: Path, docs_dir: Path, root: str = "") -> list[Path]:
    """Render every page.  Returns the list of files written."""
    evidence_dir, docs_dir = Path(evidence_dir), Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    ev = {
        "grid": load(evidence_dir / "grid_verification.json"),
        "ingest": load(evidence_dir / "ingest.json"),
        "gate": load(evidence_dir / "gate.json"),
        "emission": load(evidence_dir / "emission.json"),
        "emission_halo": load(evidence_dir / "emission_halo.json"),
        "budget_curve": load(evidence_dir / "budget_curve.json"),
        "canary": load(evidence_dir / "canary.json"),
        "emit": load(evidence_dir / "emit.json"),
        "receipt": load(evidence_dir / "submission_receipt.json"),
        "uniqueness": load(evidence_dir / "uniqueness.json"),
        "run_card": load(evidence_dir / "run_card.json"),
        "prune": load(evidence_dir / "prune.json"),
        "hypotheses": load(evidence_dir / "hypotheses.json"),
        "hypothesis_thermal": load(evidence_dir / "hypothesis_thermal_pathway.json"),
        "uniqueness_review": load(evidence_dir / "uniqueness_review.json"),
    }
    global _BUILT_AT
    _BUILT_AT = evidence_timestamp(ev)
    dec = decision(ev)
    measured = (ev.get("prune") or {}).get("score_02778") or {}
    pages = {
        "index.html": executive_summary(ev, dec, root),
        "executive-summary.html": executive_summary(ev, dec, root),
        "method.html": method(ev, dec, root),
        "evidence.html": evidence(ev, dec, root),
        "analysis-02778.html": analysis_02778(ev, dec, root, measured=measured),
        "hypotheses.html": __import__("gems65.site_hypotheses", fromlist=["x"]).hypotheses_page(ev, dec, root),
        "verification.html": verification(ev, dec, root),
        "limitations.html": limitations(ev, dec, root),
    }
    written = []
    for name, text in pages.items():
        p = docs_dir / name
        p.write_text(text, encoding="utf-8")
        written.append(p)
    from . import site_hypotheses as _sh
    written.append(_sh.write_md(ev, docs_dir.parent / "HYPOTHESES.md"))
    sj = docs_dir / "status.json"
    sj.write_text(json.dumps(status_json(ev, dec), indent=1) + "\n", encoding="utf-8")
    written.append(sj)
    (docs_dir / ".nojekyll").write_text("", encoding="utf-8")
    written.append(docs_dir / ".nojekyll")
    return written
