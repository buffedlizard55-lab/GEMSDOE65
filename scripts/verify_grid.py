"""Verify the placed official rasters against the pinned grid and write a receipt.

Fail-closed: any mismatch exits non-zero and writes nothing.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import numpy as np
import rasterio

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems65 import grid as G  # noqa: E402

PINS = {
    "data/bridge/existing_faults.tif": ("7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093", 425830),
    "data/bridge/labels.tif": ("7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093", 425830),
    "data/bridge/sample_submission.tif": ("2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc", 1599597),
    "data/training_features.tif": ("4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5", 418912844),
}


def sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    report: dict = {"generated_utc": None, "files": {}, "grid": {}, "ok": True}
    import datetime
    report["generated_utc"] = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")

    for rel, (want_sha, want_bytes) in PINS.items():
        p = ROOT / rel
        if not p.exists():
            report["files"][rel] = {"present": False}
            continue
        got_bytes = p.stat().st_size
        got_sha = sha256(p)
        entry = {
            "present": True, "bytes": got_bytes, "sha256": got_sha,
            "pin_sha256": want_sha, "pin_bytes": want_bytes,
            "sha_match": got_sha == want_sha, "bytes_match": got_bytes == want_bytes,
        }
        report["files"][rel] = entry
        if not (entry["sha_match"] and entry["bytes_match"]):
            report["ok"] = False

    lab = ROOT / "data/bridge/labels.tif"
    tmpl = ROOT / "data/bridge/sample_submission.tif"
    if lab.exists() and tmpl.exists():
        raw, valid = G.read_labels(str(lab))
        fp = G.footprint(str(tmpl))
        with rasterio.open(tmpl) as ds:
            sub = ds.read(1)
        with rasterio.open(str(lab)) as ds:
            labt = ds.read(1)
        g = {
            "shape": list(raw.shape), "crs": f"EPSG:{G.CRS_EPSG}",
            "transform": list(G.TRANSFORM),
            "footprint_finite_cells": int(fp.sum()),
            "footprint_nan_cells": int((~fp).sum()),
            "template_zeros": int((sub == 0).sum()),
            "template_ones": int((sub == 1).sum()),
            "label_positive": int((labt == 1).sum()),
            "label_zero": int((labt == 0).sum()),
            "label_nodata": int((labt == G.LABEL_NODATA).sum()),
            "positives_inside_footprint": int(((labt == 1) & fp).sum()),
            "label_nodata_equals_outside_footprint": bool(
                np.array_equal(labt == G.LABEL_NODATA, ~fp)),
        }
        g["footprint_pin_ok"] = g["footprint_finite_cells"] == G.FOOTPRINT_FINITE_CELLS
        g["catalogue_pin_ok"] = g["label_positive"] == G.KNOWN_FAULT_PIXELS
        report["grid"] = g
        if not (g["footprint_pin_ok"] and g["catalogue_pin_ok"]
                and g["label_nodata_equals_outside_footprint"]):
            report["ok"] = False

    out = ROOT / "evidence/grid_verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    print("VERDICT", "PASS" if report["ok"] else "FAIL")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
