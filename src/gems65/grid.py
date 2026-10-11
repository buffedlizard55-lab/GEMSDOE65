"""Competition grid geometry, footprint, and raster IO for the GEMSDOE65 lane.

Geometry is read from the official competition rasters themselves (never invented):

* ``data/sample_submission.tif`` -- the official template. ``EPSG:32611`` (UTM 11N),
  100 m, width 3292 x height 3730, origin (243350, 4508550), single float32 band,
  ``nodata = NaN`` outside the region footprint.
* ``data/training_features.tif`` -- the official 19-band feature stack, float32,
  ``nodata = -3.4028235e+38`` outside the footprint.
* ``data/labels.tif`` -- the official catalogue (``existing_faults.tif``), int8,
  ``1`` mapped fault, ``0`` no fault, ``-1`` outside.

Provenance (byte-verified 2026-10-11 against the owner mirror manifest
``data/bridge/manifest.json`` in the sibling ``GEMSDOE`` repository, which itself pins
the official DrivenData data-tab / Dropbox mirror URLs):

    training_features.tif   sha256 4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5  418912844 B
    labels.tif              sha256 7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093     425830 B
    sample_submission.tif   sha256 2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc    1599597 B

Nothing in this module downloads, mirrors, or caches anything from the DrivenData site.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

NODATA_F32 = np.float32(-3.4028234663852886e38)
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"

PINNED_SHA256 = {
    "training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    "labels.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
}
PINNED_BYTES = {
    "training_features.tif": 418912844,
    "labels.tif": 425830,
    "sample_submission.tif": 1599597,
}


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_pinned_inputs(data_dir: Path = DATA) -> dict:
    """Re-hash the three official rasters against the pinned digests.

    Returns a receipt.  ``ok`` is False if any file is missing or its digest differs;
    callers must refuse to run the experiment in that case.
    """
    receipt: dict = {"checked_utc": None, "files": {}, "ok": True}
    from datetime import datetime, timezone

    receipt["checked_utc"] = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    for name, want in PINNED_SHA256.items():
        p = Path(data_dir) / name
        if not p.is_file():
            receipt["files"][name] = {"status": "missing", "sha256": None}
            receipt["ok"] = False
            continue
        got = sha256_file(p)
        ok = got == want and p.stat().st_size == PINNED_BYTES[name]
        receipt["files"][name] = {
            "status": "verified" if ok else "MISMATCH",
            "sha256": got,
            "bytes": p.stat().st_size,
            "expected_sha256": want,
            "expected_bytes": PINNED_BYTES[name],
        }
        receipt["ok"] = receipt["ok"] and ok
    return receipt


def open_template(path: str | Path = DATA / "sample_submission.tif") -> dict:
    with rasterio.open(path) as s:
        return dict(
            driver="GTiff",
            dtype="float32",
            count=1,
            crs=s.crs,
            transform=s.transform,
            width=s.width,
            height=s.height,
            nodata=np.nan,
        )


def read_footprint(path: str | Path = DATA / "sample_submission.tif") -> np.ndarray:
    """Region footprint taken from the OFFICIAL TEMPLATE's own finite mask.

    Measured 2026-10-11: 5,167,373 finite pixels of 12,279,160.  The feature stack's
    band-1 finite mask is slightly smaller (5,165,852) because 1,521 rim pixels carry
    ``nodata`` in the feature stack but not in the template.  The template is the
    authority for what the portal will score, so it defines the footprint here.
    """
    with rasterio.open(path) as s:
        a = s.read(1)
    return np.isfinite(a)


def read_labels(path: str | Path = DATA / "labels.tif") -> np.ndarray:
    """Catalogue raster -> boolean (>=1 is a mapped fault, 0 no-fault, -1 outside)."""
    with rasterio.open(path) as s:
        a = s.read(1)
    return a >= 1


def read_band(path: str | Path, band: int, fill: float = 0.0) -> np.ndarray:
    """Read one official feature band, replacing the -3.4e38 sentinel with ``fill``."""
    with rasterio.open(path) as s:
        a = s.read(band).astype(np.float32)
    return np.where(a < NODATA_F32 * np.float32(0.5), np.float32(fill), a)


def band_descriptions(path: str | Path = DATA / "training_features.tif") -> list[str]:
    with rasterio.open(path) as s:
        return list(s.descriptions)


def write_submission(
    arr: np.ndarray,
    template_path: str | Path = DATA / "sample_submission.tif",
    out_path: str | Path = None,
    footprint: np.ndarray | None = None,
    outside: str = "zeros",
) -> Path:
    """Write a legal single-band float32 GeoTIFF on the exact official template grid.

    ``outside='zeros'`` writes 0.0 outside the footprint and sets ``nodata=None``, so that
    **every one of the 12,279,160 cells** satisfies ``0 <= v <= 1`` and there is no NaN
    anywhere.  This is the variant that permanently removes the DrivenData
    ``"Predicted values must be in range [0, 1]"`` error, which is raised when the
    validator's range test sees a NaN comparison return False.

    ``outside='nan'`` reproduces the sample submission's convention (NaN outside the
    footprint) for callers that want a byte-for-byte format match with the template.
    """
    meta = open_template(template_path)
    out = np.asarray(arr, dtype=np.float32)
    assert out.shape == (meta["height"], meta["width"]), (out.shape, meta)
    if footprint is not None:
        vals = out[footprint]
        assert np.isfinite(vals).all(), "non-finite value inside the footprint"
        assert (vals >= 0).all() and (vals <= 1).all(), "value outside [0, 1] inside the footprint"
        out = np.where(footprint, out, np.nan if outside == "nan" else np.float32(0.0))
    if outside == "nan":
        meta["nodata"] = np.nan
    else:
        meta["nodata"] = None
    meta["compress"] = "deflate"
    meta["tiled"] = True
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **meta) as dst:
        dst.write(out, 1)
    return out_path


def check_submission(path: str | Path, footprint: np.ndarray) -> dict:
    """Independent re-read of a written submission; returns a receipt dict."""
    with rasterio.open(path) as s:
        a = s.read(1)
        meta = dict(
            crs=str(s.crs),
            width=s.width,
            height=s.height,
            transform=tuple(round(float(x), 6) for x in s.transform)[:6],
            dtype=s.dtypes[0],
            count=s.count,
            nodata=s.nodata,
        )
    finite_in = np.isfinite(a[footprint])
    in_range_in = finite_in & (a[footprint] >= 0) & (a[footprint] <= 1)
    outside = a[~footprint]
    return dict(
        path=str(path),
        sha256=sha256_file(path),
        bytes=Path(path).stat().st_size,
        meta=meta,
        footprint_px=int(footprint.sum()),
        finite_inside=int(finite_in.sum()),
        in_range_inside=int(in_range_in.sum()),
        outside_nan=int(np.isnan(outside).sum()),
        outside_zero=int((outside == 0).sum()),
        outside_other=int((~np.isnan(outside) & (outside != 0)).sum()),
        full_grid_finite_px=int(np.isfinite(a).sum()),
        full_grid_in_0_1=bool(np.isfinite(a).all() and (a >= 0).all() and (a <= 1).all()),
        positive_px=int(((a > 0) & footprint).sum()),
        min_in=float(np.nanmin(a[footprint])),
        max_in=float(np.nanmax(a[footprint])),
        ok_range=bool(in_range_in.sum() == finite_in.sum() == int(footprint.sum())),
        ok_outside=bool(np.isnan(outside).all() or (outside == 0).all()),
    )


def sha256(path: str | Path) -> str:
    return sha256_file(path)


def write_json(obj, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=False), encoding="utf-8")
    return p
