from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / 'vendor' / 'template58'
if str(TEMPLATE) not in sys.path:
    sys.path.insert(0, str(TEMPLATE))


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    tmp.replace(p)


def verify_template():
    pin = json.loads((ROOT / 'evidence/shared_template_pin.json').read_text())
    for entry in pin['files']:
        if sha256(ROOT / entry['path']) != entry['sha256']:
            raise ValueError(f"Shared template modified: {entry['path']}")
    return pin
