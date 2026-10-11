#!/usr/bin/env python3
"""Stage 00 -- restore the hash-pinned competition data WITHOUT a DrivenData login.

The competition data is login-walled at
https://www.drivendata.org/competitions/306/competition-doe-gems/data/ and this sandbox has no
DrivenData credentials, so the bytes are restored from the owner-supplied GitHub mirror and then
verified against sha256 pins before anything is allowed to train on them.

PROVENANCE, stated plainly: the mirror is owner-supplied and integrity-pinned. It is NOT
organizer-authenticated. Every hash below was first recorded by the sibling template
``buffedlizard55-lab/GEMSDOE32`` (``data/prepared_manifest.json``, ``data/restore_receipt.json``)
and is re-verified byte-for-byte here.

Run:  python scripts/00_restore_data.py [--force]
Out:  /home/user/.cache/gems_data/data/{training_features.tif,labels.tif,sample_submission.tif,
      external/lidar_scarp_features_u8.tif, external/dem_links.json, external/derived_sgmc_faults_100m_u8.tif}
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems65 import grid as G  # noqa: E402

FEATURES_REPO = "buffedlizard55-lab/GEMSDOE"
FEATURES_REF = "c0c06ac82178f26b94fce3397036ef8f12a2f3a0"
AUX_REPO = "buffedlizard55-lab/GEMSDOE24"
AUX_REF = "07345ea0604953d7efb858d9cfbc21e20c7aca0b"

# git blob shas, read from the GitHub contents API on 2026-10-11 and pinned here.
FEATURE_PARTS = [
    ("data/bridge/gems-geodawn-numerical-features.tif.part-000", "f34e5143d5e7c10014b5cfe01c85d01bcede4c0a", 94371840),
    ("data/bridge/gems-geodawn-numerical-features.tif.part-001", "4bd98099ae505f63cc6c3733954f259974efd290", 94371840),
    ("data/bridge/gems-geodawn-numerical-features.tif.part-002", "d6f883ba8822207ac2765445737ecd2ecdfd2914", 94371840),
    ("data/bridge/gems-geodawn-numerical-features.tif.part-003", "976977b4ac84c4c9b6fec72495c4e512341de872", 94371840),
    ("data/bridge/gems-geodawn-numerical-features.tif.part-004", "41a7bb7b7603c1e7669d8cc8405cfeb5efb5cf0c", 41425484),
]
AUX_FILES = [
    ("data/bridge/existing_faults.tif", "4ad3c1f3f19823e40924589bee7e51e44ae3a2e7", "labels.tif",
     "byte-identical to labels.tif in every mirror inspected; sha256 pin is the labels pin"),
    ("data/bridge/example_submission.tif", "7d865a9921a40ed2ea4c742a6a25b1fa2f357c5a", "sample_submission.tif", None),
    ("data/external/lidar_scarp_features_u8.tif", "da733b53147efad5c141ffdb96e469ec5b4da8b8",
     "external/lidar_scarp_features_u8.tif", None),
    ("data/external/derived_sgmc_faults_100m_u8.tif", "c794f6ee8dd278f9d836576dcb5d02239da1c4f7",
     "external/derived_sgmc_faults_100m_u8.tif", None),
    ("data/external/gdr_qfaults_traces.csv", "b2e66237d5e3111c113834ead0d209adbae8443e",
     "external/gdr_qfaults_traces.csv", None),
]
DEM_LINKS = ("data/dem_links.json", "external/dem_links.json")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_blob(repo: str, ref_or_sha: str, dest: Path, by_sha: bool) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = (f"repos/{repo}/git/blobs/{ref_or_sha}" if by_sha
           else f"repos/{repo}/contents/{ref_or_sha[0]}?ref={ref_or_sha[1]}")
    with dest.open("wb") as fh:
        p = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw", url],
                           stdout=fh, stderr=subprocess.PIPE)
    return p.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    d = G.data_dir()
    d.mkdir(parents=True, exist_ok=True)
    ok = True

    # ---- training features (5 parts, concatenated, then hashed)
    target = d / "training_features.tif"
    expect = G.EXPECTED_SHA256["training_features.tif"]
    if target.exists() and sha256(target) == expect and not args.force:
        print(f"[cached ] training_features.tif  sha256 MATCH")
    else:
        parts = []
        for path, blob, size in FEATURE_PARTS:
            p = d / "bridge" / Path(path).name
            if not (p.exists() and p.stat().st_size == size) or args.force:
                print(f"[fetch  ] {path} ({size:,} bytes)")
                if not fetch_blob(FEATURES_REPO, blob, p, by_sha=True):
                    print(f"FAILED to fetch {path}", file=sys.stderr)
                    return 2
            parts.append(p)
        with target.open("wb") as out:
            for p in parts:
                with p.open("rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 22), b""):
                        out.write(chunk)
        got = sha256(target)
        print(f"[verify ] training_features.tif  {'MATCH' if got == expect else 'MISMATCH ' + got}")
        ok &= got == expect

    # ---- auxiliary files
    for path, blob, dest_rel, note in AUX_FILES:
        dest = d / dest_rel
        expect_sha = (G.EXPECTED_SHA256.get(dest_rel)
                      or G.EXPECTED_SHA256.get("labels.tif") if dest_rel == "labels.tif" else None)
        if dest.exists() and not args.force:
            got = sha256(dest)
            if expect_sha is None or got == expect_sha:
                print(f"[cached ] {dest_rel:42s} sha256 {got[:16]}…")
                continue
        print(f"[fetch  ] {path}")
        if not fetch_blob(AUX_REPO, blob, dest, by_sha=True):
            print(f"FAILED to fetch {path}", file=sys.stderr)
            ok = False
            continue
        got = sha256(dest)
        if expect_sha:
            print(f"[verify ] {dest_rel:42s} {'MATCH' if got == expect_sha else 'MISMATCH ' + got}")
            ok &= got == expect_sha
        else:
            print(f"[hash   ] {dest_rel:42s} sha256 {got}  (no pin recorded; {note or 'recorded for audit'})")

    # ---- dem links (lidar coverage provenance, no pin)
    dest = d / DEM_LINKS[1]
    if not dest.exists() or args.force:
        fetch_blob(FEATURES_REPO, (DEM_LINKS[0], FEATURES_REF), dest, by_sha=False)
    print(f"[{'cached ' if dest.exists() else 'MISSING'}] {DEM_LINKS[1]:42s} {dest.stat().st_size if dest.exists() else 0:,} bytes")

    print("\nRESTORE OK" if ok else "\nRESTORE INCOMPLETE -- see failures above")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
