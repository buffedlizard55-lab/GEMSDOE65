"""Local preflight validation for a GEMS submission GeoTIFF.

The DrivenData problem page requires a single-band float32 GeoTIFF on the
training grid, values in [0, 1], and null/NaN outside the study bounds. This
validator checks that representation against the supplied sample/footprint.
A local PASS is not organizer upload acceptance or a uniqueness clearance.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import rasterio

from .grid import EPSG, HEIGHT, WIDTH, TRANSFORM

SENTINELS = (-9999.0, -999.0, 9999.0, -3.4e38, 1e30)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _nodata_label(value) -> str | float | None:
    if value is None:
        return None
    if isinstance(value, (float, np.floating)) and np.isnan(value):
        return "NaN"
    return float(value)


def validate(path: Path, footprint: np.ndarray | None = None,
             catalogue: np.ndarray | None = None) -> dict:
    """Run local format/range checks on one GeoTIFF; return a JSON-safe receipt.

    When ``footprint`` is supplied, prediction values must be finite and in
    [0, 1] inside it, and NaN outside it. Without a footprint, all raster cells
    must be finite because their inside/outside status is unknown.
    """
    path = Path(path)
    with rasterio.open(path) as ds:
        a = ds.read(1)
        nodata = ds.nodata
        meta = dict(crs=str(ds.crs), shape=[ds.height, ds.width], dtype=ds.dtypes[0],
                    count=ds.count, nodata=_nodata_label(nodata),
                    transform=list(tuple(ds.transform)[:6]),
                    profile_compress=ds.profile.get("compress"))
        desc = ds.descriptions
        h, w = ds.height, ds.width

    if a.ndim != 2:
        raise ValueError('prediction TIFF must contain a 2-D first band')
    for mask_name, mask in (("footprint", footprint), ("catalogue", catalogue)):
        if mask is not None and np.asarray(mask).shape != a.shape:
            raise ValueError(f"{mask_name} shape {np.asarray(mask).shape} != raster shape {a.shape}")
    footprint = None if footprint is None else np.asarray(footprint, dtype=bool)
    catalogue = None if catalogue is None else np.asarray(catalogue, dtype=bool)

    finite = np.isfinite(a)
    finite_values = a[finite]
    has_finite = bool(finite_values.size)
    lo = float(finite_values.min()) if has_finite else None
    hi = float(finite_values.max()) if has_finite else None
    mean = float(finite_values.mean()) if has_finite else None
    in_range = bool(has_finite and lo >= 0.0 and hi <= 1.0)
    checks = {
        "single_band": meta["count"] == 1,
        "dtype_float32": meta["dtype"] == "float32",
        f"dimensions_{HEIGHT}x{WIDTH}": (h, w) == (HEIGHT, WIDTH),
        f"crs_epsg_{EPSG}": meta["crs"] == f"EPSG:{EPSG}",
        "transform_matches_sample_submission": meta["transform"] == list(tuple(TRANSFORM)[:6]),
        "no_inf_anywhere": bool(not np.isinf(a).any()),
        "no_sentinel_values": bool(not np.isin(finite_values, SENTINELS).any()),
    }
    if footprint is None:
        checks["no_nan_without_footprint"] = bool(finite.all())
        checks["range_0_1_all_cells"] = in_range
        checks["nodata_nan"] = bool(isinstance(nodata, (float, np.floating)) and np.isnan(nodata))
    else:
        n_fp = int(footprint.sum())
        inside = a[footprint]
        outside = a[~footprint]
        inside_finite = np.isfinite(inside)
        checks["in_footprint_all_finite"] = bool(n_fp > 0 and inside_finite.all())
        checks["in_footprint_range_0_1"] = bool(
            n_fp > 0 and inside_finite.all()
            and (inside >= 0.0).all() and (inside <= 1.0).all())
        checks["outside_footprint_nan"] = bool(np.isnan(outside).all())
        checks["nodata_nan"] = bool(isinstance(nodata, (float, np.floating)) and np.isnan(nodata))
    if catalogue is not None:
        checks["zero_dots_on_mapped_catalogue"] = int((a[catalogue] > 0).sum()) == 0

    receipt = {
        "file": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "meta": meta,
        "band_description": list(desc),
        "n_finite": int(finite.sum()),
        "n_nan": int(np.isnan(a).sum()),
        "n_infinite": int(np.isinf(a).sum()),
        "min_finite": lo, "max_finite": hi, "mean_finite": mean,
        "emitted_positive_pixels": int((a > 0).sum()),
        "checks": checks,
        "all_checks_passed": bool(all(checks.values())),
        "validation_class": "local format/range preflight against the published sample-grid representation; not organizer acceptance or uniqueness clearance",
    }
    if catalogue is not None:
        receipt["on_catalogue_positive_pixels"] = int((a[catalogue] > 0).sum())
    if footprint is not None:
        n_fp = int(footprint.sum())
        receipt["in_footprint_positive_pixels"] = int((a[footprint] > 0).sum())
        receipt["footprint_fraction"] = float(receipt["in_footprint_positive_pixels"] / n_fp) if n_fp else 0.0
        receipt["outside_footprint_finite_pixels"] = int(np.isfinite(a[~footprint]).sum())
    return receipt


def assert_submittable(receipt: dict) -> None:
    """Raise unless every local format/range check passed (not organizer acceptance)."""
    bad = [k for k, v in receipt["checks"].items() if not v]
    if bad:
        raise AssertionError(f"submission fails the local format/range preflight: {bad}")
