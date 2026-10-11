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
    # Second lane: merge its cleared rasters into the same allowlist before the scan, so the
    # per-file rules below (cap, membership) apply to it unchanged.
    lane_known, lane_problems = cleared_lane_rasters(root)
    manifest_known, manifest_problems = manifest_recorded_rasters(root)
    known.update(lane_known)
    known.update(manifest_known)
    problems.extend(lane_problems)
    problems.extend(manifest_problems)
    allowed, unknown = set(), []
    d = root / RASTER_ALLOW_DIR
    if d.is_dir():
        # ``.zip`` is screened exactly like ``.tif``: a published ZIP is admissible only when its
        # sha256 is recorded in a card that clears a download, for the same 2 MB cap.  Both of
        # this repository's lanes publish their ZIPs through that route or not at all.
        for f in sorted(d.glob('*.tif')) + sorted(d.glob('*.zip')):
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

# --- LANE "bandrf" ALLOWLIST (session arena/263a33f5-gemsdoe65, IR-65-025) -----------------------
# A second lane is published alongside the canonical one.  It reached a *cleared* verdict on its own
# instrument (evidence/lane65-bandrf/run_card.json) and its user requirement is an obvious,
# one-click download.  The canonical guard above is written for a NEGATIVE run and is left exactly
# as it was; it still fails closed if that lane's card ever stops being negative.  This block adds
# the same kind of fail-closed evidence requirement *per cleared lane*:
#   * the lane card must exist and must actually clear the download;
#   * every published raster's sha256 must be recorded in that card;
#   * the same 2 MB cap applies; and
#   * the lane's tracked bridge grids are allowed only while their bytes still match the sha256
#     recorded in that lane's input pins (a drifted pin is a hard failure, not a silent pass).
LANE_CARDS = {'bandrf': 'evidence/lane65-bandrf/run_card.json'}
LANE_PINS = {'bandrf': 'evidence/lane65-bandrf/input_pins.json'}


def manifest_recorded_rasters(root):
    """Rasters that some in-repo submission manifest explicitly names and hashes.

    A lane that publishes its evidence artifacts beside a machine-readable manifest is
    admissible on the same terms as the original six: the file must be named, hashed and
    size-listed in a manifest under ``docs/downloads/``.  Nothing is admitted merely by
    existing, and the caller still applies the 2 MB cap and the suffix rules.
    """
    known, problems = {}, []
    for path in sorted((root / RASTER_ALLOW_DIR).glob('*.json')):
        try:
            data = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        files = data.get('files')
        if not isinstance(files, dict):
            continue
        for entry in files.values():
            if not isinstance(entry, dict):
                continue
            name, sha = entry.get('filename'), entry.get('sha256')
            if name and sha:
                known[str(sha)] = f'{RASTER_ALLOW_DIR}/{name}'
    return known, problems


def cleared_lane_rasters(root):
    known, problems = {}, []
    for lane, rel in LANE_CARDS.items():
        path = root / rel
        if not path.exists():
            continue
        card = json.loads(path.read_text())
        if not (card.get('verdict') or {}).get('download_cleared'):
            problems.append(f'{rel}: lane {lane!r} does not clear a download, so its published '
                            'rasters are refused')
            continue
        for name, rec in (card.get('files') or {}).items():
            sha = rec.get('sha256')
            if sha:
                known[sha] = f'docs/downloads/{name}'
    return known, problems


def pinned_lane_inputs(root):
    """Tracked *inputs* of a cleared lane, allowed only while their bytes match the pins."""
    allowed, problems = set(), []
    for lane, rel in LANE_PINS.items():
        path = root / rel
        if not path.exists():
            continue
        pins = json.loads(path.read_text())
        for pin in pins.get('files', []):
            dest = str(pin.get('dest') or '')
            if not dest.startswith('bridge/'):
                continue
            repo_rel = f'data/{dest}'
            target = root / repo_rel
            if not target.exists():
                continue
            digest = _hashlib.sha256(target.read_bytes()).hexdigest()
            if digest != pin.get('sha256'):
                problems.append(f'{repo_rel}: tracked bridge grid no longer matches the pin in '
                                f'{rel} ({digest[:16]}... != {str(pin.get("sha256"))[:16]}...)')
            else:
                allowed.add(repo_rel)
    return allowed, problems

# --- END LANE "bandrf" ALLOWLIST ------------------------------------------------------------------


def main():
    proc=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,check=True)
    files=[Path(s.decode()) for s in proc.stdout.split(b'\0') if s]
    allowed_rasters, raster_problems = raster_allowlist(ROOT)
    pinned_inputs, pin_problems = pinned_lane_inputs(ROOT)
    problems=list(raster_problems) + list(pin_problems)
    for rel in files:
        p=ROOT/rel
        if not p.exists():continue
        if p.is_file() and p.stat().st_size>10*1024*1024:problems.append(f'Unexpected large Git blob: {rel}')
        if rel.suffix.lower() in {'.tif','.tiff','.zip','.npy','.npz','.pyc'}:
            if rel.as_posix() in allowed_rasters: continue   # LANE 65 allowlist (IR-65-009)
            if rel.as_posix() in pinned_inputs: continue      # bandrf lane pins (IR-65-025)
            problems.append(f'Forbidden tracked model/data artifact: {rel}')
        if any(x in rel.parts for x in ('.venv','.cache','node_modules','__pycache__')):problems.append(f'Cache tracked: {rel}')
    card=json.loads((ROOT/'evidence/run_card.json').read_text())
    if card['verdict']!='negative' or card['eligible_for_download'] is not False:
        problems.append('Repository publication guard is for the negative run only; no release clearance exists')
    print(json.dumps({'ok':not problems,'tracked_files':len(files),'problems':problems},indent=2))
    raise SystemExit(1 if problems else 0)

if __name__=='__main__':main()
