"""Offline link/fragment, evidence-identity and negative-publication validation."""
import _path  # noqa: F401
from gems65.common import ROOT, sha256
from html.parser import HTMLParser
from urllib.parse import urlparse,unquote
import json

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.ids=set();self.h1=0;self.lang=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='html':self.lang=a.get('lang')
        if tag=='h1':self.h1+=1
        if a.get('id'):self.ids.add(a['id'])
        for k in ('href','src'):
            if a.get(k):self.links.append(a[k])


def check_site(root=None):
    root=root or ROOT
    docs=root/'docs';errors=[];pages={}
    # LANE 65 allowlist (IR-65-009): the six evidence rasters are published under docs/downloads
    # with a DO-NOT-SUBMIT banner; see scripts/check_repository.py::raster_allowlist for the guard.
    import check_repository as _cr
    allowed_rasters, raster_problems = _cr.raster_allowlist(root)
    errors.extend(raster_problems)
    for p in docs.rglob('*'):
        if p.is_symlink():errors.append(f'Public symlink: {p}')
        if p.is_file() and p.suffix.lower() in {'.tif','.tiff','.zip','.npy','.npz'}:
            if p.relative_to(root).as_posix() in allowed_rasters: continue
            errors.append(f'Negative run has public artifact: {p}')
    # Pages under docs/lane65-bandrf/ belong to the *second* lane, whose own run card clears a
    # download.  Its pages must carry the matching banner, verified against that card: a page may
    # not claim CLEARED unless the card on disk clears it, and it may not stay silent either.
    import json as _json
    lane_card_path = root / 'evidence' / 'lane65-bandrf' / 'run_card.json'
    lane_cleared = False
    if lane_card_path.exists():
        lane_cleared = bool((_json.loads(lane_card_path.read_text()).get('verdict') or {})
                            .get('download_cleared'))
    lane_dir = docs / 'lane65-bandrf'
    if lane_dir.is_dir() and not lane_cleared:
        errors.append('lane65-bandrf pages exist while that lane does not clear a download')
    for p in list(docs.glob('*.html')) + list((docs / 'lane65-bandrf').glob('*.html')):
        parser=Page();parser.feed(p.read_text());pages[p.resolve()]=parser
        if parser.lang!='en':errors.append(f'Missing document language: {p.name}')
        if parser.h1!=1:errors.append(f'Expected one h1: {p.name} has {parser.h1}')
        text=p.read_text()
        if p.parent==docs:
            if 'NOT CLEARED FOR SUBMISSION' not in text:errors.append(f'Missing fail-closed banner: {p.name}')
        elif lane_dir in p.parents:
            if 'CLEARED FOR SUBMISSION' not in text:
                errors.append(f'Missing lane-cleared banner: {p.relative_to(docs).as_posix()}')
        elif 'NOT CLEARED FOR SUBMISSION' not in text:
            errors.append(f'Missing fail-closed banner: {p.relative_to(docs).as_posix()}')
    for path,parsed in pages.items():
        for link in parsed.links:
            u=urlparse(link)
            if u.scheme or u.netloc:continue
            target=(path.parent/unquote(u.path)).resolve() if u.path else path
            if not target.is_relative_to(docs.resolve()):
                errors.append(f'Link escapes public site: {link}');continue
            if not target.exists():errors.append(f'Missing target from {path.name}: {link}')
            if u.fragment and target in pages and unquote(u.fragment) not in pages[target].ids:
                errors.append(f'Missing fragment from {path.name}: {link}')
            if target.suffix.lower() in {'.tif','.tiff','.zip','.npy','.npz'}:
                if target.relative_to(root).as_posix() in allowed_rasters: continue
                errors.append(f'Negative artifact link: {link}')
    for p in (docs/'data').glob('*.json'):
        try:json.loads(p.read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
        except (ValueError,json.JSONDecodeError):errors.append(f'Nonstandard/invalid JSON: {p.name}')
        source=root/'evidence'/p.name
        if source.exists() and sha256(source)!=sha256(p):errors.append(f'Stale public evidence: {p.name}')
    card=json.loads((docs/'data/run_card.json').read_text())
    if card['verdict']!='negative' or card['eligible_for_download'] is not False:
        errors.append('Negative-only site has inconsistent release state')
    for expected in ['index.html','executive-summary.html','research.html','sources.html','audit.html']:
        if not (docs/expected).exists():errors.append('Required page missing: '+expected)
    return dict(ok=not errors,pages_checked=len(pages),errors=errors,negative_raster_exposure=False if not errors else None)

if __name__=='__main__':
    report=check_site();print(json.dumps(report,indent=2));raise SystemExit(0 if report['ok'] else 1)
