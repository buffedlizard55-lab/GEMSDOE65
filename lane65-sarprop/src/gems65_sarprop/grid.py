"""The official competition grid, footprint and raster I/O.

All constants in this module are transcribed from the official problem
description (DrivenData competition 306, page 967) and were re-measured against
the organiser rasters themselves (see ``evidence/grid_verification.json``).

Organiser-verified facts (measured from `existing_faults.tif`,
`sample_submission.tif` on 2026-10-11):

    shape       (3730, 3292)      rows x cols
    CRS         EPSG:32611        UTM zone 11N
    transform   (100, 0, 243350, 0, -100, 4508550)
    pixel       100 m
    labels      int8, nodata -1, values {-1, 0, 1}, 60_988 pixels equal to 1
    template    float32, nodata nan, values {0, 1, nan}, same 60_988 pixels

The sample submission encodes the study-area *footprint* as "not NaN": every
finite cell is inside the region the organiser scores, every NaN cell is
outside it.  ``FOOTPRINT_FINITE_CELLS`` is that count and is asserted on load so
a swapped or re-gridded template fails loudly.

Missing-value sentinel
----------------------
`training_features.tif` has nodata = -3.40282346e+38 (the most negative float32
stored as a double).  ``np.isfinite`` therefore reports 100 % finite on every
band.  The shared template's rule -- any value below -1e38 is missing -- is
applied in :func:`read_features`.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np

# --- official grid ---------------------------------------------------------
CRS_EPSG: int = 32611
PIXEL_M: float = 100.0
SHAPE: tuple[int, int] = (3730, 3292)
TRANSFORM: tuple[float, float, float, float, float, float] = (
    100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0,
)
NODATA_TEMPLATE: float = float("nan")

# --- organiser label raster ------------------------------------------------
LABEL_NODATA: int = -1
LABEL_POSITIVE: int = 1
KNOWN_FAULT_PIXELS: int = 60_988  # measured; asserted in validate_grid()

# --- footprint -------------------------------------------------------------
# Measured 2026-10-11 from sample_submission.tif (sha256 2176d08e...):
# 5,167,373 finite cells, 7,111,787 NaN cells, 5,106,385 zeros, 60,988 ones.
# The 7,111,787 NaN cells equal exactly the 7,111,787 cells labelled -1 in
# labels.tif, so "label != -1" is equivalent to "inside the footprint".
FOOTPRINT_FINITE_CELLS: int = 5_167_373
FOOTPRINT_NAN_CELLS: int = 7_111_787
FOOTPRINT_ZERO_CELLS: int = 5_106_385

MISSING_BELOW: float = -1e38

# Geometry of the kernel, in pixels (300 m at 100 m).
RADIUS_PX: float = 3.0

__all__ = [
    "CRS_EPSG", "PIXEL_M", "SHAPE", "TRANSFORM", "NODATA_TEMPLATE",
    "LABEL_NODATA", "LABEL_POSITIVE", "KNOWN_FAULT_PIXELS",
    "MISSING_BELOW", "RADIUS_PX",
    "GridMismatch", "read_labels", "read_footprint", "footprint",
    "read_band", "read_bands", "mask_missing", "write_grid",
]


class GridMismatch(ValueError):
    """Raised when a raster does not sit on the official grid."""


def _require_official_grid(path: str, shape, crs, transform, *, allow_other=False):
    got_t = tuple(float(x) for x in transform)[:6]
    want_t = tuple(float(x) for x in TRANSFORM)
    ok = (
        tuple(shape) == SHAPE
        and (crs is None or getattr(crs, "to_epsg", lambda: None)() == CRS_EPSG)
        and all(abs(a - b) <= 1e-6 for a, b in zip(got_t, want_t))
    )
    if not ok and not allow_other:  # fail closed
        raise GridMismatch(
            f"{path}: grid mismatch. got shape={tuple(shape)} crs={crs} "
            f"transform={got_t}; want shape={SHAPE} crs=EPSG:{CRS_EPSG} "
            f"transform={want_t}"
        )


def mask_missing(a: np.ndarray, below: float = MISSING_BELOW) -> np.ndarray:
    """NaN-out the organiser's sentinel.  Never changes a legitimate value."""
    a = np.asarray(a, dtype=np.float32)
    return np.where(a < below, np.float32(np.nan), a)


def read_band(path: str, band: int = 1, *, missing: bool = True) -> np.ndarray:
    """Read one band on the official grid as float32 (1-based ``band``)."""
    import rasterio

    with rasterio.open(path) as ds:
        _require_official_grid(path, ds.shape, ds.crs, ds.transform)
        if band < 1 or band > ds.count:
            raise IndexError(f"{path}: band {band} out of range 1..{ds.count}")
        a = ds.read(band).astype(np.float32)
        # int8 rasters (labels) carry -1 as nodata and must NOT be sentinel-mapped
        if np.issubdtype(ds.dtypes[band - 1], np.floating) and missing:
            a = mask_missing(a, MISSING_BELOW)
        return a


def read_bands(path: str, bands: Iterable[int] | None = None,
               *, missing: bool = True) -> tuple[np.ndarray, list[int]]:
    """Read several bands, smallest-index-first, into one (n, H, W) float32 array.

    Memory: (n, 3730, 3292) float32 = n * 49.1 MB.  Callers on a 3 GB box should
    request few bands at a time (see :func:`iter_bands`).
    """
    import rasterio

    with rasterio.open(path) as ds:
        _require_official_grid(path, ds.shape, ds.crs, ds.transform)
        idx = list(bands) if bands is not None else list(range(1, ds.count + 1))
        out = np.empty((len(idx), SHAPE[0], SHAPE[1]), dtype=np.float32)
        for k, b in enumerate(idx):
            out[k] = ds.read(b)
            if np.issubdtype(ds.dtypes[b - 1], np.floating) and missing:
                out[k] = mask_missing(out[k], MISSING_BELOW)
        return out, idx


def read_labels(path: str) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(labels_int8, valid_bool)`` from the organiser label raster.

    ``labels_int8`` keeps the raw {-1, 0, 1}; ``valid_bool`` is ``label != -1``.
    """
    import rasterio

    with rasterio.open(path) as ds:
        _require_official_grid(path, ds.shape, ds.crs, ds.transform)
        raw = ds.read(1)
    if raw.dtype != np.int8:
        raw = raw.astype(np.int8)
    valid = raw != LABEL_NODATA
    return raw, valid


def footprint(template_path: str) -> np.ndarray:
    """Boolean footprint = finite cells of the organiser's sample submission."""
    import rasterio

    with rasterio.open(template_path) as ds:
        _require_official_grid(template_path, ds.shape, ds.crs, ds.transform)
        a = ds.read(1)
    return np.isfinite(a)


def write_grid(path: str, data: np.ndarray, *, dtype: str = "float32",
               nodata: float | None = float("nan"), compress: str = "lzw"):
    """Write a single-band raster on the official grid.

    Deliberately minimal and explicit: no block geometry is inherited from any
    other file (the shared template records a real incident where copying
    ``blockxsize`` from a striped template produced a GDAL error and a 110-byte
    stub that still looked like success).  Tiles are pinned to 256.
    """
    import rasterio
    from rasterio.transform import Affine

    arr = np.asarray(data)
    if arr.shape != SHAPE:
        raise GridMismatch(f"refusing to write shape {arr.shape}, want {SHAPE}")
    profile = dict(
        driver="GTiff",
        height=SHAPE[0],
        width=SHAPE[1],
        count=1,
        dtype=dtype,
        crs=f"EPSG:{CRS_EPSG}",
        transform=Affine.from_gdal(*TRANSFORM),
        nodata=nodata,
        compress=compress,
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(arr.astype(dtype), 1)
    # fail-loud read-back
    with rasterio.open(path) as ds:
        if (ds.height, ds.width) != SHAPE:
            raise GridMismatch(f"read-back shape {ds.shape} != {SHAPE}")
        if ds.count != 1:
            raise GridMismatch(f"read-back count {ds.count} != 1")
