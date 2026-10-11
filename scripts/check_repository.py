"""Fail CI if a negative research TIFF, raw array, or large blob entered Git."""
from pathlib import Path
import subprocess
import json
ROOT=Path(__file__).resolve().parents[1]


def main():
    proc=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,check=True)
    files=[Path(s.decode()) for s in proc.stdout.split(b'\0') if s]
    problems=[]
    for rel in files:
        p=ROOT/rel
        if not p.exists():continue
        if p.is_file() and p.stat().st_size>10*1024*1024:problems.append(f'Unexpected large Git blob: {rel}')
        if rel.suffix.lower() in {'.tif','.tiff','.zip','.npy','.npz','.pyc'}:problems.append(f'Forbidden tracked model/data artifact: {rel}')
        if any(x in rel.parts for x in ('.venv','.cache','node_modules','__pycache__')):problems.append(f'Cache tracked: {rel}')
    card=json.loads((ROOT/'evidence/run_card.json').read_text())
    if card['verdict']!='negative' or card['eligible_for_download'] is not False:
        problems.append('Repository publication guard is for the negative run only; no release clearance exists')
    print(json.dumps({'ok':not problems,'tracked_files':len(files),'problems':problems},indent=2))
    raise SystemExit(1 if problems else 0)

if __name__=='__main__':main()
