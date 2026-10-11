"""Hash-checked public input bridge. Its main restores no prior predictions; the generic fetch helper is also reused by the separate audit-only restore."""
import _path  # noqa: F401
from gems65.common import ROOT, sha256, write_json
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

PART_BLOBS = ['f34e5143d5e7c10014b5cfe01c85d01bcede4c0a',
              '4bd98099ae505f63cc6c3733954f259974efd290',
              'd6f883ba8822207ac2765445737ecd2ecdfd2914',
              '976977b4ac84c4c9b6fec72495c4e512341de872',
              '41a7bb7b7603c1e7669d8cc8405cfeb5efb5cf0c']


def fetch(repo, blob, dest, expected, size=None):
    dest = ROOT / dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or sha256(dest) != expected:
        tmp = dest.with_suffix(dest.suffix + '.partial')
        try:
            with tmp.open('wb') as f:
                subprocess.run(['gh', 'api', f'repos/{repo}/git/blobs/{blob}',
                                '-H', 'Accept: application/vnd.github.raw+json'], stdout=f, check=True)
            if sha256(tmp) != expected or (size is not None and tmp.stat().st_size != size):
                raise ValueError(f'Bridge integrity mismatch: {dest.name}')
            tmp.replace(dest)
        finally:
            tmp.unlink(missing_ok=True)
    if size is not None and dest.stat().st_size != size:
        raise ValueError('Cached byte length mismatch')
    return dict(path=str(dest.relative_to(ROOT)), sha256=sha256(dest), bytes=dest.stat().st_size,
                source=f'https://github.com/{repo}', git_blob_sha=blob, integrity_verified=True,
                organizer_authenticated=False)


def main():
    pins = json.loads((ROOT / 'registry/feature_stack_pins.json').read_text())
    records = []
    for b, p in zip(PART_BLOBS, pins['parts'], strict=True):
        records.append(fetch('buffedlizard55-lab/GEMSDOE', b, 'data/raw/' + p['name'], p['sha256'], p['bytes']))
    whole = ROOT / 'data/raw/training_features.tif'
    if not whole.exists() or sha256(whole) != pins['whole_file']['sha256']:
        tmp = whole.with_suffix('.partial')
        with tmp.open('wb') as out:
            for p in pins['parts']:
                with (ROOT / 'data/raw' / p['name']).open('rb') as src:
                    for block in iter(lambda: src.read(1 << 20), b''):
                        out.write(block)
        if sha256(tmp) != pins['whole_file']['sha256']:
            tmp.unlink()
            raise ValueError('Reassembled stack hash mismatch')
        tmp.replace(whole)
    inputs = [
        ('57GEMSDOE', 'data/bridge/existing_faults.tif', 'data/raw/existing_faults.tif', '7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093'),
        ('57GEMSDOE', 'data/bridge/sample_submission.tif', 'data/raw/sample_submission.tif', '2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc'),
        ('60GEMSDOE', 'data/external/topo_10m_derived_100m_u8.tif', 'data/external/topo_10m_derived_100m_u8.tif', 'a6398d9950965dec6aae6ccecdaa6ced48645d133eab222cbdd11def9bdabfa4'),
        ('60GEMSDOE', 'data/external/lidar_scarp_features_u8.tif', 'data/external/lidar_scarp_features_u8.tif', 'd580bb8bdcdb941e32fefb8b38044bc5bf04e199bf2e83498c3576e6fc465568'),
    ]
    inventory = json.loads((ROOT / 'evidence/repository_inventory.json').read_text())
    for repo, path, dest, digest in inputs:
        r = next(x for x in inventory['repositories'] if x['repo'] == repo)
        a = next(x for x in r['rasters'] if x['path'] == path)
        records.append(fetch('buffedlizard55-lab/' + repo, a['git_blob_sha'], dest, digest, a['size']))
    records.append(dict(path='data/raw/training_features.tif', sha256=sha256(whole),
                        bytes=whole.stat().st_size, integrity_verified=True, organizer_authenticated=False))
    write_json(ROOT / 'evidence/data_integrity.json', dict(checked_at=datetime.now(timezone.utc).isoformat(),
        source_class='Hash-pinned owner mirrors, NOT independently authenticated official downloads', files=records))
    print('Verified cached stack and four supporting rasters; no prior predictions loaded.')

if __name__ == '__main__':
    main()
