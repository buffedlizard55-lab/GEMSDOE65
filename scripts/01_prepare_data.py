"""Stage 01 -- verify the pinned data, build covariates + the footprint feature matrix.

Run:  python scripts/01_prepare_data.py
Out:  <work>/X_footprint.npy, <work>/flat_idx.npy, <work>/covariates.npz, <work>/masks.npz,
      evidence/covariates.json, registry/data_manifest.json
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems65 import covariates as CV  # noqa: E402
from gems65 import features as FT  # noqa: E402
from gems65 import grid as G  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    t0 = time.time()
    ddir = G.data_dir()
    work = G.work_dir()
    work.mkdir(parents=True, exist_ok=True)
    repo = G.repo_root()

    # ---- 1. hash verification against the pinned manifest
    hashes = {}
    for rel, expect in G.EXPECTED_SHA256.items():
        p = ddir / rel
        got = sha256(p)
        hashes[rel] = {"sha256": got, "expected": expect, "match": got == expect, "bytes": p.stat().st_size}
        print(f"[hash] {rel:44s} {'MATCH' if got == expect else 'MISMATCH'}  {p.stat().st_size:,} bytes")
        if got != expect:
            print("FATAL: pinned hash mismatch; refusing to continue.", file=sys.stderr)
            return 2

    # ---- 2. geometry verification against the official template
    foot = G.read_footprint(ddir)
    labels = G.read_labels(ddir) & foot
    with rasterio.open(ddir / "sample_submission.tif") as ds:
        geo = {
            "width": ds.width, "height": ds.height, "count": ds.count, "dtype": ds.dtypes[0],
            "crs": str(ds.crs), "transform": [float(v) for v in tuple(ds.transform)[:6]],
            "nodata": str(ds.nodata),
        }
    assert geo["width"] == G.WIDTH and geo["height"] == G.HEIGHT, geo
    assert geo["transform"] == list(G.TRANSFORM), geo
    assert geo["crs"].endswith("32611"), geo
    n_foot = int(foot.sum())
    n_lab = int(labels.sum())
    print(f"[grid] {geo['width']}x{geo['height']} {geo['crs']} footprint={n_foot:,} labels={n_lab:,}")
    assert n_foot == G.FOOTPRINT_PIXELS, (n_foot, G.FOOTPRINT_PIXELS)
    assert n_lab == G.LABEL_PIXELS, (n_lab, G.LABEL_PIXELS)

    # sentinel audit (mechanism M1 of the range error)
    sent_foot = {}
    with rasterio.open(ddir / "training_features.tif") as ds:
        for i in range(1, 20):
            b = ds.read(i)
            sent_foot[G.BAND_NAMES[i - 1]] = int(((b < -1e30) & foot).sum())
            del b
    union_sent = int(sum(sent_foot.values()))
    print(f"[sentinel] float32-sentinel band-pixels inside footprint: {union_sent:,} "
          f"(max single band {max(sent_foot.values()):,})")

    np.savez_compressed(work / "masks.npz", foot=foot, labels=labels)

    # ---- 3. covariates
    cv = CV.build_covariates(ddir, footprint=foot)
    CV.save_covariates(cv, work / "covariates.npz")
    print(f"[covariates] lidar coverage {cv.stats['lidar_coverage_frac_of_footprint']:.4f} of footprint; "
          f"range-front px {cv.stats['range_front_px']:,}; "
          f"basin_fill vs log(depth_to_base) r={cv.stats['basin_fill_vs_log_depth_to_base_pearson_r']:.3f}")

    # ---- 4. feature matrix
    info = FT.build_feature_matrix(ddir, work, foot)
    info["sentinel_band_pixels_inside_footprint"] = sent_foot
    print(f"[features] {info['n_footprint_pixels']:,} x {info['n_features']} -> {info['x_path']}")

    # ---- 5. evidence + registry
    ev = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seconds": round(time.time() - t0, 1),
        "grid": {"epsg": G.EPSG, "width": G.WIDTH, "height": G.HEIGHT,
                 "transform": list(G.TRANSFORM), "footprint_pixels": n_foot,
                 "label_pixels": n_lab, "sample_submission_geometry": geo},
        "hashes": hashes,
        "covariate_stats": cv.stats,
        "feature_matrix": {k: v for k, v in info.items() if k != "sentinel_pixels_inside_footprint_fixed"},
        "sentinel_pixels_inside_footprint_fixed": info["sentinel_pixels_inside_footprint_fixed"],
    }
    (repo / "evidence").mkdir(exist_ok=True)
    (repo / "evidence" / "covariates.json").write_text(json.dumps(ev, indent=2), encoding="utf-8")

    man = {
        "schema_version": 1,
        "note": ("Every hash was recomputed from the restored bytes in this checkout. The mirror is "
                 "owner-supplied and integrity-pinned; it is NOT organizer-authenticated. The "
                 "login-walled origin is https://www.drivendata.org/competitions/306/competition-doe-gems/data/"),
        "files": [
            {"dest": k, "sha256": v["sha256"], "bytes": v["bytes"], "pin_match": v["match"],
             "mirror": {"training_features.tif": "github.com/buffedlizard55-lab/GEMSDOE@c0c06ac82178f26b94fce3397036ef8f12a2f3a0 data/bridge/gems-geodawn-numerical-features.tif.part-000..004",
                        "labels.tif": "github.com/buffedlizard55-lab/GEMSDOE@c0c06ac82178f26b94fce3397036ef8f12a2f3a0 data/bridge/existing_faults.tif (byte-identical to labels.tif)",
                        "sample_submission.tif": "github.com/buffedlizard55-lab/GEMSDOE@c0c06ac82178f26b94fce3397036ef8f12a2f3a0 data/bridge/example_submission.tif",
                        "external/lidar_scarp_features_u8.tif": "github.com/buffedlizard55-lab/GEMSDOE24@07345ea0604953d7efb858d9cfbc21e20c7aca0b data/external/lidar_scarp_features_u8.tif"}[k]}
            for k, v in hashes.items()
        ],
        "upstream_official_origins": [
            {"file": "training_features.tif / labels.tif / sample_submission.tif",
             "official_origin": "DrivenData competition 306 data page (login required)",
             "url": "https://www.drivendata.org/competitions/306/competition-doe-gems/data/"},
            {"file": "external/lidar_scarp_features_u8.tif",
             "official_origin": "derived from USGS 3DEP 1 m DEM tiles",
             "url": "https://www.usgs.gov/3d-elevation-program",
             "tile_index": "external/dem_links.json (716 tiles, prd-tnm S3 URLs)"},
        ],
    }
    (repo / "registry").mkdir(exist_ok=True)
    (repo / "registry" / "data_manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    print(f"[done] {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
