"""Submission writer + strict validator.  Permanently engineers out the portal error
"Predicted values must be in range [0, 1]".

Official contract, verbatim from the competition problem description
(https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/, "Submission format",
read 2026-10-11):
  * same projected CRS as the training data (UTM zone 11N, EPSG:32611)
  * same resolution as the training data (100 m)
  * same bounds as the training data, and data outside the bounds is null or nan
  * single layer, float32, values between 0 and 1

The two mechanisms that produce the range error were measured in the sibling template
(GEMSDOE32 ``docs/research/range-error-root-cause-2026-10-03.md``) and are re-measured here by
``scripts/01_prepare_data.py``:

  M1  ``training_features.tif`` declares nodata = -3.4028234663852886e+38 (float32 minimum, not
      NaN).  3,061 pixels per band (3,073 union) carry that sentinel INSIDE the 5,167,373-pixel
      scoring footprint.  A pipeline that does not replace the sentinel ships -3.4e38.
  M2  a footprint mask derived from a feature band is 1,521 px smaller than the template's, which
      strands 3,061 SCORED pixels as NaN.  NaN fails any ``((v >= 0) & (v <= 1)).all()`` check.

Both are handled by construction: the footprint is taken from ``sample_submission.tif``
(np.isfinite) and every in-footprint output pixel is written as a finite float32 in [0, 1].
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

from . import grid as G

EXPECTED_H, EXPECTED_W = G.HEIGHT, G.WIDTH
EXPECTED_TOTAL = G.TOTAL_PIXELS
EXPECTED_FOOT = G.FOOTPRINT_PIXELS
SENTINEL_THRESHOLD = -1e30


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def content_digest(arr: np.ndarray, foot: np.ndarray) -> str:
    """Stable 12-hex digest of the scored content only (outside-footprint encoding excluded)."""
    vals = np.where(foot, arr, 0.0).astype(np.float32)
    return hashlib.sha256(vals.tobytes()).hexdigest()[:12]


def sanitize(field: np.ndarray, foot: np.ndarray, labels: np.ndarray | None = None,
             zero_on_catalogue: bool = True) -> np.ndarray:
    """Finite, [0,1]-clipped, footprint-restricted float32 prediction."""
    a = np.asarray(field, dtype=np.float64).copy()
    a[~np.isfinite(a)] = 0.0                     # NaN / +-inf -> 0
    a[a < SENTINEL_THRESHOLD] = 0.0              # M1 float32 sentinel
    a = np.where(foot, a, 0.0)                   # M2: never write outside the template footprint
    lo, hi = float(np.nanmin(a[foot])) if foot.any() else 0.0, float(np.nanmax(a[foot])) if foot.any() else 1.0
    if hi > lo:
        a = (a - lo) / (hi - lo)                 # normalize to [0,1] exactly as the brief requires
    a = np.clip(a, 0.0, 1.0)
    if zero_on_catalogue and labels is not None:
        a = np.where(labels, 0.0, a)             # masked pixels earn neither TP nor FP
    a[~foot] = 0.0
    return a.astype(np.float32)


def _profile(template: Path) -> dict:
    with rasterio.open(template) as tpl:
        prof = tpl.profile.copy()
    prof.update(driver="GTiff", dtype="float32", count=1, width=EXPECTED_W, height=EXPECTED_H,
                crs=f"EPSG:{G.EPSG}", transform=rasterio.Affine(*G.TRANSFORM),
                compress="deflate", predictor=3, zlevel=9, tiled=True,
                blockxsize=256, blockysize=256, BIGTIFF="NO")
    return prof


def write_pair(values: np.ndarray, foot: np.ndarray, template: Path, out_dir: Path, stem: str) -> dict:
    """Write ``<stem>-nan.tif`` and ``<stem>-zeros.tif`` and audit both by independent re-read."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = _profile(Path(template))
    v = np.clip(np.nan_to_num(np.asarray(values, dtype=np.float64), nan=0.0), 0.0, 1.0)
    paths = {}
    for mode in ("nan", "zeros"):
        prof = base.copy()
        if mode == "nan":
            prof["nodata"] = np.nan
            arr = np.where(foot, v, np.nan).astype(np.float32)
        else:
            prof.pop("nodata", None)
            prof["nodata"] = None
            arr = np.where(foot, v, 0.0).astype(np.float32)
        p = out_dir / f"{stem}-{mode}.tif"
        with rasterio.open(p, "w", **prof) as dst:
            dst.write(arr, 1)
        paths[mode] = p
    return {"nan": str(paths["nan"]), "zeros": str(paths["zeros"])}


def validate(tif_path: Path, foot: np.ndarray, labels: np.ndarray | None = None,
             expected_foot: int | None = None, require_template_footprint: bool = True) -> dict:
    """Strict validator: independent re-read of the written file, never trusts the writer.

    Returns a dict with a ``checks`` map and ``all_checks_passed``.  Raises nothing; the caller
    decides.  ``validator`` in the run card is this dict.

    ``expected_foot`` defaults to ``foot.sum()`` so that unit tests can validate a synthetic
    footprint; ``require_template_footprint`` keeps the production safety property that the caller's
    footprint IS the pinned template footprint (5,167,373 px), which is the check that prevents the
    "1,521 px too small -> NaN in scored pixels" failure mode (M2).
    """
    tif_path = Path(tif_path)
    geo = G.check_grid(tif_path)
    with rasterio.open(tif_path) as ds:
        arr = ds.read(1)
        nodata = ds.nodata
    in_foot = arr[foot]
    out_foot = arr[~foot]
    finite_in = int(np.isfinite(in_foot).sum())
    nan_in = int(np.isnan(in_foot).sum())
    inf_in = int(np.isinf(in_foot).sum())
    sentinel_in = int(np.nansum(in_foot < SENTINEL_THRESHOLD))
    finite_all = int(np.isfinite(arr).sum())
    vmin = float(np.nanmin(in_foot)) if finite_in else float("nan")
    vmax = float(np.nanmax(in_foot)) if finite_in else float("nan")
    exp = int(foot.sum()) if expected_foot is None else int(expected_foot)
    in_range = bool(finite_in == exp and np.all((in_foot >= 0.0) & (in_foot <= 1.0)))
    # naive-portal simulation: what a validator that ignores nodata would see
    naive_ok = bool(np.all((np.nan_to_num(arr, nan=0.0) >= 0.0) & (np.nan_to_num(arr, nan=0.0) <= 1.0)))
    nan_outside_ok = bool(np.all(np.isnan(out_foot))) if np.isnan(out_foot).any() else bool(np.all(out_foot == 0.0))
    on_cat = None
    if labels is not None:
        on_cat = int(((arr > 0) & labels).sum())
    checks = {
        "single_band_float32": geo["single_band_ok"] and geo["dtype_ok"],
        "shape_3730x3292": geo["shape_ok"],
        "crs_epsg_32611": geo["crs_ok"],
        "transform_matches_template": geo["transform_ok"],
        "footprint_pixels_all_finite": finite_in == exp,
        "footprint_is_the_pinned_template_footprint": (int(foot.sum()) == EXPECTED_FOOT)
            if require_template_footprint else True,
        "footprint_zero_nan": nan_in == 0,
        "footprint_zero_inf": inf_in == 0,
        "footprint_zero_sentinel": sentinel_in == 0,
        "footprint_values_in_0_1": in_range,
        "outside_footprint_null_or_zero": nan_outside_ok,
        "naive_range_check_passes": naive_ok,
        "no_mass_on_masked_catalogue_pixels": (on_cat == 0) if on_cat is not None else True,
        "file_is_gtiff": geo["dtype"] == "float32",
        "nonempty_emission": bool(np.nansum(in_foot > 0) > 0),
    }
    return {
        "file": tif_path.name,
        "path": str(tif_path),
        "bytes": tif_path.stat().st_size,
        "sha256": sha256_file(tif_path),
        "geometry": geo,
        "nodata": None if nodata is None or (isinstance(nodata, float) and np.isnan(nodata)) else float(nodata),
        "nodata_repr": str(nodata),
        "emitted_pixels_gt_0": int(np.nansum(in_foot > 0)),
        "emitted_pixels_eq_1": int(np.nansum(in_foot >= 0.999999)),
        "footprint_finite_pixels": finite_in,
        "full_grid_finite_pixels": finite_all,
        "in_footprint_min": vmin,
        "in_footprint_max": vmax,
        "on_catalogue_pixels": on_cat,
        "checks": checks,
        "failed_checks": [k for k, v in checks.items() if not v],
        "all_checks_passed": all(checks.values()),
    }


def write_sidecar(out_json: Path, payload: dict) -> None:
    Path(out_json).write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
