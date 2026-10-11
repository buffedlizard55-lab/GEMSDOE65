#!/usr/bin/env python3
"""Standalone submission validator -- the gate between "built" and "downloadable".

Run:
    python scripts/validate_submission.py docs/downloads/<file>.tif
    python scripts/validate_submission.py --all          # every tif in docs/downloads

Checks (all must pass; exit code 0 only if they do):
  geometry  single band, float32, 3730 x 3292, EPSG:32611,
            transform exactly (100, 0, 243350, 0, -100, 4508550)
  domain    all 5,167,373 footprint pixels finite (0 NaN, 0 inf, 0 float32 sentinels)
  range     every footprint value in [0, 1]; the NAIVE whole-array check also passes
  outside   every non-footprint pixel is NaN (or 0.0 for the -zeros variant)
  budget    no prediction mass on catalogue pixels (they are masked from scoring, thread 11516)

The footprint is read from the pinned ``sample_submission.tif`` (sha256 2176d08e...), never from a
feature band -- using a feature band strands 3,061 SCORED pixels as NaN and is mechanism M2 of the
portal error "Predicted values must be in range [0, 1]".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems65 import grid as G
from gems65 import submission as SUB


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tif", nargs="*", help="GeoTIFF(s) to validate")
    ap.add_argument("--all", action="store_true", help="validate every .tif in docs/downloads")
    ap.add_argument("--json", action="store_true", help="print the full audit as JSON")
    args = ap.parse_args()

    ddir = G.data_dir()
    sample = ddir / "sample_submission.tif"
    if not sample.exists():
        print(f"FATAL: pinned template missing: {sample}\n"
              f"       restore it with: python scripts/00_restore_data.py", file=sys.stderr)
        return 3
    foot = G.read_footprint(ddir)
    labels = G.read_labels(ddir)
    if int(foot.sum()) != G.FOOTPRINT_PIXELS:
        print(f"FATAL: footprint is {int(foot.sum())} px, expected {G.FOOTPRINT_PIXELS}", file=sys.stderr)
        return 3

    targets = [Path(p) for p in args.tif]
    if args.all:
        targets += sorted((G.repo_root() / "docs" / "downloads").glob("*.tif"))
    if not targets:
        print("nothing to validate (pass a .tif or --all)", file=sys.stderr)
        return 2

    rc = 0
    for t in targets:
        if not t.exists():
            print(f"MISSING {t}")
            rc = 1
            continue
        a = SUB.validate(t, foot, labels)
        status = "PASS" if a["all_checks_passed"] else "FAIL"
        print(f"[{status}] {t.name}")
        print(f"        {a['emitted_pixels_gt_0']:,} px with mass>0 | "
              f"range [{a['in_footprint_min']:.6g}, {a['in_footprint_max']:.6g}] | "
              f"finite {a['footprint_finite_pixels']:,}/{G.FOOTPRINT_PIXELS:,} | "
              f"nodata={a['nodata_repr']} | sha256={a['sha256'][:16]}…")
        if not a["all_checks_passed"]:
            print(f"        FAILED CHECKS: {a['failed_checks']}")
            rc = 1
        if args.json:
            print(json.dumps(a, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
