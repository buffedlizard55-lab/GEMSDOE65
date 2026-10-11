#!/usr/bin/env python3
"""Index the staged prior-raster registry that the uniqueness gate reads.

The shared template's :func:`gems57.uniqueness.compare_array_to_registry` consumes
an *index* (a JSON inventory), never a raw directory.  This script fingerprints
every raster staged under ``data/registry/rasters/`` and writes
``data/registry/registry_index.json`` in exactly the schema
:func:`gems57.uniqueness.records_from_index` documents::

    {"rasters": [{"repo_first", "sources", "cache_file", "sha256"}, ...],
     "complete_accessible_scan": bool,
     "errors": [...]}

``complete_accessible_scan`` is written **false** and an explanatory entry is put
in ``errors``: the staged set is the complete contents of this repository's
registry directory, but no scan performed from this repository can certify that
it is the complete inventory of every sibling lane, so the duplicate test is
reported as fail-closed rather than as a complete-inventory certificate.

Usage::

    python3 scripts/build_registry_index.py [--check]

``--check`` re-fingerprints and exits non-zero if the index is stale.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = REPO_ROOT / "data" / "registry"
RASTER_DIR = REGISTRY_DIR / "rasters"
INDEX = REGISTRY_DIR / "registry_index.json"

NOT_COMPLETE_NOTE = (
    "The staged set is the complete contents of data/registry/rasters as cloned "
    "and hash-verified from the public owner-repository mirrors; a scan from this "
    "repository cannot certify that it is the complete inventory of every sibling "
    "lane, so the duplicate verdict is fail-closed (no certificate)."
)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def repo_of(name: str) -> str:
    """Derive the origin repository from the staged file name."""
    head = name.split("__", 1)[0]
    if head.endswith("GEMSDOE") or head.endswith("GEMSDOWN"):
        return head
    return head or "UNKNOWN"


def entry_of(path: Path) -> dict:
    with rasterio.open(path) as src:
        shape = [src.height, src.width]
        crs = None if src.crs is None else src.crs.to_string()
        count = src.count
        dtype = src.dtypes[0]
    return {
        "repo_first": repo_of(path.name),
        "sources": [f"{repo_of(path.name)}/data/registry/rasters/{path.name}"],
        "cache_file": str(path.relative_to(REPO_ROOT)),
        "sha256": sha256_of(path),
        "shape": shape,
        "crs": crs,
        "bands": count,
        "dtype": dtype,
        "bytes": path.stat().st_size,
    }


def build() -> dict:
    files = sorted(p for p in RASTER_DIR.glob("*.tif"))
    if not files:
        raise SystemExit(f"no rasters staged under {RASTER_DIR}")
    entries = [entry_of(p) for p in files]
    grids = {tuple(e["shape"]) for e in entries}
    return {
        "schema": 1,
        "generated_utc": None,
        "scope": ("Privately staged, publicly published prior rasters from the owner's "
                  "sibling lane repositories; comparison is exact Spearman on the shared "
                  "footprint plus 3 px dot overlap and Jaccard."),
        "rasters": entries,
        "complete_accessible_scan": False,
        "errors": [NOT_COMPLETE_NOTE],
        "grid_shapes": sorted(grids),
        "sha256_of_file_names": hashlib.sha256(
            "\n".join(e["cache_file"] for e in entries).encode()).hexdigest(),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="verify the on-disk index matches a fresh fingerprint")
    args = ap.parse_args(argv)
    fresh = build()
    fresh["generated_utc"] = None if args.check else __import__("time").strftime(
        "%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())
    if args.check:
        if not INDEX.is_file():
            print(f"MISSING {INDEX}")
            return 2
        on_disk = json.loads(INDEX.read_text())
        for key in ("rasters", "complete_accessible_scan", "sha256_of_file_names"):
            if on_disk.get(key) != fresh.get(key):
                print(f"STALE {key}")
                return 2
        print(f"registry index OK ({len(fresh['rasters'])} rasters)")
        return 0
    INDEX.write_text(json.dumps(fresh, indent=2) + "\n")
    print(f"wrote {INDEX.relative_to(REPO_ROOT)} with {len(fresh['rasters'])} rasters")
    shapes = {tuple(e["shape"]) for e in fresh["rasters"]}
    print(f"grid shapes: {sorted(shapes)}  bands: "
          f"{sorted({e['bands'] for e in fresh['rasters']})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
