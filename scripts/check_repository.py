"""Fail CI if a negative research TIFF, raw array, or large blob entered Git."""
from pathlib import Path
import subprocess
import json
ROOT=Path(__file__).resolve().parents[1]


# --- LANE 65 ALLOWLIST (IR-65-009, session 2026-10-11) -----------------------------------------
# The standing user requirement is a click-to-download TIF whose submit/do-not-submit status is
# obvious.  The six built rasters are therefore published under docs/downloads/ as EVIDENCE
# ARTIFACTS with a loud DO-NOT-SUBMIT banner.  The allowlist below keeps the fail-closed intent:
#   * a raster is tolerated only while NO arm is cleared for submission, and
#   * only if its sha256 appears in evidence/submission_build.json (no stray binary can be added), and
#   * only up to 2 MB.
# If any arm is ever cleared, publication requires an organizer-confirmed receipt record and this
# allowlist must be removed.  Reverse the whole change by deleting this block and its two call sites.
import hashlib as _hashlib

RASTER_ALLOW_DIR = 'docs/downloads'
RASTER_ALLOW_MAX_BYTES = 2 * 1024 * 1024


def raster_allowlist(root):
    """Return (allowed_rel_paths, reasons_why_not_allowed)."""
    card = json.loads((root / 'RUN_CARD.json').read_text()) if (root / 'RUN_CARD.json').exists() else {}
    build = json.loads((root / 'evidence' / 'submission_build.json').read_text()) \
        if (root / 'evidence' / 'submission_build.json').exists() else {}
    arms = build.get('arms', {})
    cleared = [k for k, a in arms.items() if a.get('OK_TO_DOWNLOAD_AND_SUBMIT')]
    problems = []
    if cleared:
        problems.append(f'Cleared arm(s) {cleared} but no organizer-confirmed receipt on file; '
                        'publishing a submittable raster is refused')
    if card.get('verdict') not in (None, 'NEGATIVE'):
        problems.append(f'RUN_CARD.json verdict is {card.get("verdict")!r}; the raster allowlist is '
                        'for a NEGATIVE run only')
    known = {}
    for a in arms.values():
        for mode in ('nan', 'zeros'):
            v = (a.get('validator', {}) or {}).get(mode, {}) or {}
            if v.get('sha256'):
                known[v['sha256']] = v.get('file')
    allowed, unknown = set(), []
    d = root / RASTER_ALLOW_DIR
    if d.is_dir():
        for f in sorted(d.glob('*.tif')):
            rel = f.relative_to(root).as_posix()
            h = _hashlib.sha256(f.read_bytes()).hexdigest()
            if f.stat().st_size > RASTER_ALLOW_MAX_BYTES:
                unknown.append(f'{rel}: {f.stat().st_size} bytes exceeds the 2 MB allowlist cap')
            elif h not in known:
                unknown.append(f'{rel}: sha256 {h[:16]}... is not recorded in evidence/submission_build.json')
            else:
                allowed.add(rel)
    return allowed, problems + unknown
# --- END LANE 65 ALLOWLIST -----------------------------------------------------------------------


def main():
    proc=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,check=True)
    files=[Path(s.decode()) for s in proc.stdout.split(b'\0') if s]
    allowed_rasters, raster_problems = raster_allowlist(ROOT)
    problems=list(raster_problems)
    for rel in files:
        p=ROOT/rel
        if not p.exists():continue
        if p.is_file() and p.stat().st_size>10*1024*1024:problems.append(f'Unexpected large Git blob: {rel}')
        if rel.suffix.lower() in {'.tif','.tiff','.zip','.npy','.npz','.pyc'}:
            if rel.as_posix() in allowed_rasters: continue   # LANE 65 allowlist (IR-65-009)
            problems.append(f'Forbidden tracked model/data artifact: {rel}')
        if any(x in rel.parts for x in ('.venv','.cache','node_modules','__pycache__')):problems.append(f'Cache tracked: {rel}')
    card=json.loads((ROOT/'evidence/run_card.json').read_text())
    if card['verdict']!='negative' or card['eligible_for_download'] is not False:
        problems.append('Repository publication guard is for the negative run only; no release clearance exists')
    print(json.dumps({'ok':not problems,'tracked_files':len(files),'problems':problems},indent=2))
    raise SystemExit(1 if problems else 0)

if __name__=='__main__':main()
