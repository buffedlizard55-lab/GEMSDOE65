"""Evidence-driven static Pages site. A negative run can never publish a raster."""
import _path  # noqa: F401
from gems65.common import ROOT, write_json
from html import escape as esc
from pathlib import Path
import json
import shutil
import re
import markdown2

DOCS = ROOT/'docs'
DATA = DOCS/'data'
REPO = 'https://github.com/buffedlizard55-lab/GEMSDOE65'


def load(path):
    return json.loads((ROOT/path).read_text())


def badge(text,kind='neutral'):
    return f'<span class="badge {kind}">{esc(text)}</span>'


def layout(title,active,body):
    nav=[('index.html','Overview'),('executive-summary.html','Submission guide'),('research.html','Research'),('sources.html','Sources'),('audit.html','Audit')]
    links=''.join(f'<a href="{p}"'+(' aria-current="page"' if p==active else '')+f'>{label}</a>' for p,label in nav)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · GEMSDOE65</title><meta name="description" content="Selection-bias-aware fault mapping research. Three sensitivity experiments, verified artifacts, and a fail-closed submission gate.">
<link rel="stylesheet" href="assets/site.css"><link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
<script src="assets/site.js" defer></script></head><body>
<a class="skip" href="#main">Skip to content</a>
<header class="topbar"><div class="nav"><a class="brand" href="index.html"><span class="mark" aria-hidden="true">G</span><span><strong>GEMSDOE<span style="color:#d9ad77">65</span></strong><small>Fault discovery lab</small></span></a><nav class="navlinks" aria-label="Main navigation">{links}</nav><a class="repo-link" href="{REPO}">Repository ↗</a></div></header>
<div class="status-strip"><div class="status-inner"><span><span class="status-dot" aria-hidden="true"></span><strong>NOT CLEARED FOR SUBMISSION</strong> · Negative research result</span><span>No weekly slot used · <a href="executive-summary.html">Read the submission gate →</a></span></div></div>
<main class="container" id="main">{body}</main>
<footer class="footer"><div><strong>GEMSDOE65</strong> · Selection-bias-aware PU lane<br>Evidence before optimism. Negative results are deliverables.</div><div class="footer-nav"><a href="data/run_card.json" download>Run card JSON</a><a href="{REPO}/blob/main/README.md">Original brief</a><a href="{REPO}">Source code ↗</a><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Official leaderboard ↗</a><a href="https://www.drivendata.org/termsofuse/">Access terms ↗</a></div></footer>
</body></html>'''


def stat(s):
    return f"{s['dti']:.6f}<small>95% CI [{s['ci95'][0]:.6f}, {s['ci95'][1]:.6f}]</small>"


def results_table(experiments,stratum='overall'):
    rows=[]
    for x in experiments['scenarios']:
        r=x[stratum];d=r['paired_differences']['nnpu'];n=r['scores']['sar']['withheld_positive_pixels']
        rows.append(f'''<tr class="{'row-primary' if x['primary'] else ''}"><td><strong>e(z=0) = {x['reference_propensity']:.2f}</strong><small>{'Preregistered primary' if x['primary'] else 'Sensitivity only'} · assumption, not an estimate</small></td><td class="num">{stat(r['scores']['sar'])}</td><td class="num">{stat(r['scores']['nnpu'])}</td><td class="num bad">{d['delta']:+.6f}<small>95% CI [{d['ci95'][0]:.6f}, {d['ci95'][1]:.6f}]</small></td><td class="num">{n:,}</td></tr>''')
    return '<div class="table-wrap"><table><caption>HOLDOUT-DTI · evaluator gems57-pooled-hide-v2 · pooled terms · conditional 95% CI from 1,000 paired 20 km spatial-block bootstrap draws. Finite-iteration models; not organizer scores.</caption><thead><tr><th scope="col">Propensity scale</th><th scope="col">SAR-PU</th><th scope="col">nnPU</th><th scope="col">Paired difference</th><th scope="col">Withheld positives</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'


def overview(card,experiments,forensics):
    h=card['holdout'];s=h['sar'];n=h['nnpu'];ci=s['ci95'];ni=n['ci95']
    body=f'''<section class="hero"><div><p class="eyebrow">GEMS prize research / SAR-PU lane</p><h1>A new model.<br><em>An honest result.</em></h1><p class="lead">Can correcting mapping bias help uncover faults hidden beneath low-relief terrain? We tested the idea. This run did not beat its baseline.</p><div class="button-row"><a class="button" href="#evidence">Explore the evidence <span aria-hidden="true">↓</span></a><a class="button secondary" href="research.html">Read the methodology ↗</a></div></div>
<aside class="decision" aria-labelledby="decision-heading">{badge('Negative · do not submit','fail')}<h2 id="decision-heading">No submission download.</h2><p>A new research TIFF was generated and passed format validation. It failed the holdout and literal uniqueness gates, so it remains quarantined.</p><button class="button" disabled aria-describedby="download-reason">Submission TIFF not released</button><p id="download-reason" class="tiny">Format-valid does not mean scientifically qualified. No old submission was copied.</p><a href="executive-summary.html">What must pass before submission? →</a></aside></section>
<section class="metrics" aria-label="Run summary"><div class="metric"><div class="label">SAR-PU · HOLDOUT-DTI</div><div class="value">{s['dti']:.5f}</div><div class="sub">95% CI {ci[0]:.5f}–{ci[1]:.5f}</div></div><div class="metric"><div class="label">nnPU · HOLDOUT-DTI</div><div class="value">{n['dti']:.5f}</div><div class="sub">95% CI {ni[0]:.5f}–{ni[1]:.5f}</div></div><div class="metric"><div class="label">Local GeoTIFF validator</div><div class="value good">PASS</div><div class="sub">Finite [0,1] inside footprint</div></div><div class="metric"><div class="label">Experiment budget</div><div class="value">3 / 3</div><div class="sub">Complete · no slot used</div></div></section>
<p class="compact">Both primary HOLDOUT-DTI values: <code>gems57-pooled-hide-v2</code>, {s['withheld_positive_pixels']:,} withheld positive pixels. Conditional confidence intervals. No ORGANIZER-CONFIRMED result is available.</p>
<section class="section" id="evidence"><div class="section-head"><div><p class="eyebrow">01 / The decision</p><h2>Every gate is visible.</h2><p>Promote only when the evidence supports it. Never substitute a filename for novelty.</p></div><span class="section-tag">FAIL-CLOSED BY DESIGN</span></div><div class="grid-2"><div class="panel"><h3>Scientific qualification</h3><ul class="gate-list"><li><span><span class="gate-icon bad">×</span>Higher pooled holdout DTI</span>{badge('Failed','fail')}</li><li><span><span class="gate-icon bad">×</span>No loss in the highest-propensity tercile</span>{badge('Failed','fail')}</li><li><span><span class="gate-icon good">✓</span>Single-feature leakage canaries</span>{badge('Passed','pass')}</li><li><span><span class="gate-icon bad">×</span>EM convergence</span>{badge('Cap reached','fail')}</li><li><span><span class="gate-icon bad">×</span>Comparable incumbent holdout</span>{badge('Unavailable','fail')}</li></ul></div><div class="panel"><h3>Artifact qualification</h3><ul class="gate-list"><li><span><span class="gate-icon good">✓</span>Range, CRS, shape and transform</span>{badge('Passed','pass')}</li><li><span><span class="gate-icon good">✓</span>New model output; not a copied raster</span>{badge('Generated','pass')}</li><li><span><span class="gate-icon bad">×</span>Literal overlap against registry</span>{badge('Blocked','fail')}</li><li><span><span class="gate-icon bad">×</span>All-prior clearance / final-dot audit</span>{badge('Stopped','fail')}</li><li><span><span class="gate-icon">—</span>Selector approval / organizer acceptance</span>{badge('Not obtained')}</li></ul></div></div><div class="callout"><strong>A rule-level blocker, not proof of copied geology.</strong> A registered continuous raster is positive throughout the footprint. Under the inherited positive-pixel definition, every nonempty dot set overlaps it. We verified this witness and honored the stop; we did not silently change the rule.</div><div class="evidence-links"><a href="data/run_card.json" download>Download run card JSON ↓</a><a href="data/validator_output.json">Validator receipt</a><a href="data/uniqueness.json">Uniqueness audit</a></div></section>
<section class="section"><div class="section-head"><div><p class="eyebrow">02 / Matched comparisons</p><h2>Three assumptions. The same negative result.</h2><p>Propensity is not identified from these data alone. Scale scenarios are disclosed, not optimized after seeing the holdout.</p></div></div>{results_table(experiments)}<p class="compact" style="margin-top:14px">All EM fits reached the iteration cap. These results reject this finite-iteration candidate for promotion; they do not prove SAR learning cannot work.</p></section>
<section class="section grid-2"><figure class="panel figure"><img src="assets/research-surface.png" alt="Diagnostic map of the newly fitted out-of-fold research surface; no accepted fault or geothermal discovery is indicated." width="600" height="580" loading="lazy"><figcaption><strong>New research surface · not a submission.</strong><br>OOF predictions with mapped faults masked. Display stretch only; not calibrated fault probabilities. The validated TIFF remains quarantined.</figcaption></figure><div class="panel"><p class="eyebrow">03 / What the cited raster actually did</p><h2>Pruning, not a new discovery surface.</h2><p>The cited GEMSDOE32 raster is a strict subset of its predecessor. Our byte-and-pixel audit found <strong>{forensics['removed']:,} removed dots</strong> near mapped faults, leaving <strong>{forensics['candidate_positive_pixels']:,}</strong>.</p><p class="compact">RASTER-FORENSICS measurements, not scores. Reducing redundant false-positive mass can improve a Tversky ratio. That is a plausible mechanism—not proof of the hidden-label cause.</p><p class="compact">The prompt’s reported leaderboard result is unverified. No receipt was available, and we make no promise to surpass it.</p><a href="research.html#why-did-the-cited-gemsdoe32-artifact-do-well">Read the forensic analysis →</a></div></section>
<section class="section"><p class="eyebrow">04 / The reproducible path</p><h2>From cached data to a decision.</h2><div class="method-flow"><div class="flow-step"><span class="index">01 — RESTORE</span><h3>Check the input bytes</h3><p>Pinned feature stack, topo and lidar derivatives. Owner mirror, not official authentication.</p></div><div class="flow-step"><span class="index">02 — LEARN</span><h3>Separate fault and selection</h3><p>Five propensity covariates, SAR-EM, clipped risk and a matched nnPU baseline.</p></div><div class="flow-step"><span class="index">03 — CHALLENGE</span><h3>Hide whole components</h3><p>Spatial buffer, canaries, pooled DTI, confidence intervals and high-propensity checks.</p></div><div class="flow-step"><span class="index">04 — RELEASE OR STOP</span><h3>Protect the weekly slots</h3><p>Validate and compare actual pixels. A failed gate means no public raster.</p></div></div></section>
<section class="section panel"><div class="section-head"><div><p class="eyebrow">Next session</p><h2>Resolve the blockers before another fit.</h2></div><a href="audit.html">All irregularities →</a></div><div class="grid-3"><div><h3>01. Make the registry rule usable</h3><p class="compact">The selector must explicitly address mixed dense and dotted priors. No self-granted exemptions.</p></div><div><h3>02. Establish identification evidence</h3><p class="compact">Obtain complete-mapping evidence, official data provenance, comparable holdout results and real receipts.</p></div><div><h3>03. Preregister a fresh experiment</h3><p class="compact">Set a convergence budget before a new locked holdout. Do not retune the consumed three-scenario run.</p></div></div></section>'''
    return layout('Overview','index.html',body)


def guide(card):
    body=f'''<div class="page-intro"><p class="eyebrow">Executive summary / submission guide</p><h1>Know exactly when it is safe<br>to download and submit.</h1><p class="lead">This run is <strong>not cleared</strong>. A format-valid TIFF exists for audit, but its scientific and uniqueness gates failed. There is no competition-ready download.</p></div><div class="callout"><p id="guide-download-reason"><strong>Do not submit this run.</strong> Do not substitute a historical raster, rename the quarantine file, or upload the JSON evidence as a prediction. No slot has been spent.</p><button class="button" disabled aria-describedby="guide-download-reason">Submission TIFF not released</button></div>
<div class="grid-2"><section class="panel"><h2>Two separate decisions</h2><div class="path-row"><span class="path-index">A</span><div><h3>Research promotion</h3><p>Requires a matched holdout win, no high-propensity loss, converged/valid fitting, leakage clearance, complete registry checks and format validation.</p></div></div><div class="path-row"><span class="path-index">B</span><div><h3>Real-slot selection</h3><p>A separate selector checks the current submission-page cap, rules and receipt-backed incumbent. Research promotion alone never authorizes an upload.</p></div></div><a href="data/run_card.json" download>Download the negative run card ↓</a></section><section class="panel"><h2>Required TIFF contract</h2><ul><li>One band, <code>float32</code>, <code>EPSG:32611</code>.</li><li>Shape <code>3730 × 3292</code>, 100 m cells.</li><li>Transform <code>(100, 0, 243350, 0, -100, 4508550)</code>.</li><li>Finite values in <code>[0,1]</code> inside the sample footprint.</li><li>NaN only outside the footprint; no negative sentinel inside.</li><li>If zipped, the archive contains exactly one TIFF.</li></ul><p class="compact">Verified against the hash-pinned owner-mirrored sample. Direct official provenance/acceptance is not established.</p><a href="data/validator_output.json">Inspect the on-disk validation receipt →</a></section></div>
<section class="section panel"><p class="eyebrow">Future passing runs only</p><h2>The submission checklist</h2><div class="path-row"><span class="path-index">01</span><div><h3>Confirm a released candidate exists</h3><p>The top of this site must explicitly show research promotion and a TIFF download linked to a matching SHA256. This run does not. A static website cannot train or safely invent a prediction file in your browser.</p></div></div><div class="path-row"><span class="path-index">02</span><div><h3>Obtain separate selector clearance</h3><p>Read the live <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition rules</a> and submission page. Verify the remaining weekly allowance there; it is unknown here. Log the selector’s decision.</p></div></div><div class="path-row"><span class="path-index">03</span><div><h3>Download only the approved TIFF or one-TIFF ZIP</h3><p>Do not upload this website, a JSON run card, an HTML report, the example raster, or an old submission. Preserve the unique filename and compare its SHA256 to the release receipt.</p></div></div><div class="path-row"><span class="path-index">04</span><div><h3>Run the local validator against the exact file</h3><p>Use <code>python scripts/validate_submission.py path/to/approved.tif</code>. A pass checks representation, not hidden-label performance or organizer acceptance. Any failure blocks upload.</p></div></div><div class="path-row"><span class="path-index">05</span><div><h3>Enter the competition’s “New submission” form</h3><p>After selector clearance, choose the approved TIFF (or single-TIFF ZIP) under “File to submit.” Use the release’s unique name and note of at most 140 characters. Review the current form; it was not accessed in this session.</p></div></div><div class="path-row"><span class="path-index">06</span><div><h3>Keep the actual organizer receipt</h3><p>Only the submission-page receipt can establish acceptance and an ORGANIZER-CONFIRMED score. Record receipt URL, name, file hash, note, date and displayed result. Never replace it with a local projection.</p></div></div></section>
<section class="section grid-2"><div class="panel"><h2>About the range error</h2><p><code>Predicted values must be in range [0, 1]</code></p><p>The rejected file was not supplied, so its exact cause is unknown. Common causes include raw logits, unbounded rescaling and finite negative nodata sentinels.</p><p>Our pipeline uses sigmoid scores and explicit footprint handling. The writer rejects invalid values instead of silently clipping them. Tests exercise the failure cases.</p></div><div class="panel"><h2>Research identifier, not an upload recommendation</h2><p class="hash">{esc(card['submission_name'])}</p><p><strong>Recorded note:</strong></p><p class="compact">{esc(card['note'])}</p><p class="tiny">{card['note_characters']} characters. This identifier belongs to the quarantined negative artifact.</p><p><strong>SHA256:</strong></p><p class="hash">{esc(card['raster_sha256'])}</p></div></section>'''
    return layout('Submission guide','executive-summary.html',body)


def md(text):
    text=markdown2.markdown(text,extras=['tables','fenced-code-blocks','header-ids'],safe_mode='escape')
    text=re.sub(r'<(/?)h([1-5])(\b[^>]*)>', lambda m: '<'+m[1]+'h'+str(int(m[2])+1)+m[3]+'>', text)
    return text.replace('<table>','<div class="table-wrap"><table>').replace('</table>','</table></div>')


def research(experiments):
    body='''<div class="page-intro"><p class="eyebrow">Research / a falsifiable geological hypothesis</p><h1>Account for what was mapped.<br>Not just what is there.</h1><p class="lead">Model fault occurrence and mapping selection separately. Keep the assumptions, non-fault mimics and failed tests in the record.</p></div><div class="callout green"><strong>Scope:</strong> fault detection in the competition footprint, not confirmed geothermal vents. Thermal resources require evidence beyond a fault-prediction raster.</div>'''
    body+='<section class="section"><h2>Highest-propensity-tercile check</h2><p class="compact">HOLDOUT-DTI on identical restricted domains; the training-population propensity quantile defines each stratum. Counts vary by sensitivity.</p>'+results_table(experiments,'high_tercile')+'</section>'
    body+='<article class="prose">'+md((ROOT/'research/preregistration.md').read_text())+md((ROOT/'research/review.md').read_text())+md((ROOT/'research/implementation_details.md').read_text())+'</article>'
    return layout('Research','research.html',body)


def sources_page(sources,sites):
    cards=[]
    for s in sources['sources']:
        verified=s['status'].startswith('Verified')
        cards.append(f'''<article class="source"><div class="tag">{esc(s['id'])} / {esc(s['kind'])}</div><h3>{esc(s['title'])}</h3>{badge(s['status'],'pass' if verified else 'neutral')}<p>{esc(s['claims'])}</p><a href="{esc(s.get('review_url',s['url']),quote=True)}">Open verification source ↗</a>{(' · <a href="'+esc(s['url'],quote=True)+'">Publication page ↗</a>') if 'review_url' in s else ''}</article>''')
    rows=[]
    for r in sites['repositories']:
        name=r['repo'];status=r['status'].replace('_',' ')
        rows.append(f'''<tr data-search="{esc(name+' '+status,quote=True)}"><td><strong>{esc(name)}</strong></td><td>{esc(status)}<small>Live page / organizer receipt not verified</small></td><td><a href="{esc(r.get('review_url',REPO),quote=True)}">Pinned source ↗</a></td><td><a href="https://buffedlizard55-lab.github.io/{esc(name)}/">Owner site ↗</a></td></tr>''')
    body=f'''<div class="page-intro"><p class="eyebrow">Sources / evidence with boundaries</p><h1>Verified code.<br>Disclosed provenance.</h1><p class="lead">Primary publications, official reference code and owner mirrors are different evidence classes. A working link is not a verified scientific claim.</p></div><div class="feed-status" data-feed-status>Source snapshot: {esc(sites['checked_at'])}. Live score and weekly cap not verified.</div><section class="source-list">{''.join(cards)}</section>
<section class="section"><div class="section-head"><div><p class="eyebrow">Public repository survey</p><h2>{len(sites['repositories'])} source sites, one auditable index.</h2><p>Read the repository-hosted page source; do not imply access to live Pages or organizer accounts.</p></div></div><label class="filter-label" for="repo-filter">Find a repository</label><input class="filter" id="repo-filter" type="search" placeholder="For example, GEMSDOE32" data-filter><p class="tiny" data-result-count aria-live="polite">{len(rows)} of {len(rows)} sources shown</p><div class="table-wrap"><table><thead><tr><th scope="col">Repository</th><th scope="col">Review status</th><th scope="col">Audit source</th><th scope="col">Manual review</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><div class="evidence-links"><a href="data/site_review.json" download>Complete source review JSON ↓</a><a href="data/sources.json" download>Source ledger JSON ↓</a><a href="data/feed.json">Metadata feed</a></div></section><div class="callout"><strong>Not a live leaderboard.</strong> The automated feed checks GitHub commit metadata only. It does not refresh holdout experiments, validate newly published rasters, authenticate data origins or confirm a competition score.</div>'''
    return layout('Sources','sources.html',body)


def audit_page(card,issues,validator):
    rows=''.join(f'<tr><td>{esc(k.replace("_"," "))}</td><td>{badge("PASS" if v else "FAIL","pass" if v else "fail")}</td></tr>' for k,v in validator['local']['checks'].items())
    items=''.join(f'<article class="issue"><h3>{badge(x["id"]+" · "+x["severity"],"fail" if x["severity"] in {"critical","high"} else "neutral")} {esc(x["title"])}</h3><p>{esc(x["finding"])}</p><p class="disposition">{esc(x["disposition"])}</p></article>' for x in issues['items'])
    body=f'''<div class="page-intro"><p class="eyebrow">Audit / own the outcome</p><h1>What passed.<br>What did not.</h1><p class="lead">A valid file is only one part of a valid submission. Every unresolved requirement stays visible.</p></div><div class="grid-2"><section class="panel"><h2>Actual on-disk validation</h2><p class="compact">FORMAT-MEASUREMENT · new quarantined research raster · not organizer acceptance.</p><table><tbody>{rows}</tbody></table><p class="hash" style="margin-top:15px">SHA256 {esc(card['raster_sha256'])}</p></section><section class="panel"><h2>Evidence files</h2><ul><li><a href="data/run_card.json" download>Final JSON run card</a></li><li><a href="data/experiments.json">All three sensitivity experiments</a></li><li><a href="data/validator_output.json">Full validator output</a></li><li><a href="data/uniqueness.json">Pre-placement hash / pixel / overlap checks</a></li><li><a href="data/h33_forensics.json">GEMSDOE32 forensic result</a></li><li><a href="data/feature_cache.json">Feature provenance and missingness</a></li><li><a href="data/expanded_canaries.json">Expanded-basis canary audit</a></li><li><a href="data/browser_checks.json">Desktop / mobile browser checks</a></li><li><a href="data/shared_template_pin.json">Unmodified shared-tool pins</a></li><li><a href="data/verification_passes.json">Three-pass verification record</a></li></ul><h3>What is deliberately absent</h3><p>No submission TIFF link. No final dots. No all-prior clearance. No organizer receipt. No assumed weekly limit. No claim of a geothermal discovery.</p><a href="{REPO}/actions">Inspect CI checks ↗</a></section></div><section class="section"><p class="eyebrow">Irregularity register</p><h2>Blockers are part of the deliverable.</h2>{items}</section>'''
    return layout('Audit','audit.html',body)


def assert_no_public_rasters():
    bad=[p for p in DOCS.rglob('*') if p.is_symlink() or (p.is_file() and p.suffix.lower() in {'.tif','.tiff','.zip','.npy','.npz'})]
    if bad:
        raise ValueError(f'Negative run must not publish model artifacts, even unlinked: {bad}')


def main():
    card=load('evidence/run_card.json');experiments=load('evidence/experiments.json')
    if card['eligible_for_download'] or card['verdict']!='negative':
        raise ValueError('Current site is a negative-result build. A release requires a separate verified selector pipeline.')
    assert_no_public_rasters()
    DATA.mkdir(parents=True,exist_ok=True)
    files=['run_card.json','experiments.json','validator_output.json','uniqueness.json','h33_forensics.json',
           'feature_cache.json','shared_template_pin.json','site_review.json','irregularities.json','verification_passes.json',
           'expanded_canaries.json','execution_provenance.json','browser_checks.json','browser_transport.json','visualization.json']
    for name in files:
        source=ROOT/'evidence'/name
        if not source.exists():
            raise FileNotFoundError(f'Required evidence missing: {name}')
        shutil.copyfile(source,DATA/name)
    shutil.copyfile(ROOT/'registry/sources.json',DATA/'sources.json')
    pages={'index.html':overview(card,experiments,load('evidence/h33_forensics.json')),
           'executive-summary.html':guide(card),'research.html':research(experiments),
           'sources.html':sources_page(load('registry/sources.json'),load('evidence/site_review.json')),
           'audit.html':audit_page(card,load('evidence/irregularities.json'),load('evidence/validator_output.json'))}
    for name,text in pages.items():(DOCS/name).write_text(text)
    # Stable legacy URLs now point at the completed run, not the earlier no-data briefing.
    for name,target in {'hypotheses.html':'research.html','irregularities.html':'audit.html',
                        'competitive-context.html':'research.html#why-did-the-cited-gemsdoe32-artifact-do-well'}.items():
        content=layout('Updated report',name,'<section class="page-intro"><h1>The research report has moved.</h1><p>This earlier briefing is superseded by the completed negative experiment.</p><a href="'+target+'">Open the current evidence →</a></section>')
        content=content.replace('<head>','<head><meta http-equiv="refresh" content="0;url='+target+'">',1)
        (DOCS/name).write_text(content)
    # Keep the preflight card URL, but never serve contradictory current states.
    shutil.copyfile(DOCS/'data/run_card.json',DOCS/'data/run-card.json')
    (DOCS/'.nojekyll').write_text('')
    (ROOT/'.nojekyll').write_text('')
    (ROOT/'index.html').write_text('''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0;url=docs/index.html"><title>GEMSDOE65 · Research status</title></head><body><h1>GEMSDOE65: not cleared for submission</h1><p>Negative research result. No submission download is offered.</p><p><a href="docs/index.html">Open the research site →</a></p></body></html>''')
    assert_no_public_rasters()
    print('Built five evidence-driven pages and three legacy redirects. No TIFF, ZIP or model array in public docs.')

if __name__=='__main__':main()
