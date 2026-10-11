"""Study-area grid: CRS, shape, geotransform and the scored footprint.

Every constant here is read from the two bridged files committed in
``data/bridge/`` and re-verified by ``scripts/run_lane.py verify`` (writes ``evidence/verify_grid.json``):

* ``existing_faults.tif``  sha256 ``7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093``
  (byte-identical to the ``labels.tif`` recorded in
  ``GEMSDOE32/data/restore_receipt.json``, sha256 ``7ba308cc...`` -- i.e. the
  public "labels" raster *is* the mapped-fault catalogue; the scored truth is
  not published.)
* ``sample_submission.tif`` sha256 ``2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc``

Verified properties
-------------------
CRS ``EPSG:32611`` (UTM zone 11N), shape ``3730 x 3292``, transform
``(100, 0, 243350, 0, -100, 4508550)``, 100 m pixels, bounds
``(243350, 4135550) - (572550, 4508550)``.  The sample submission carries
``nodata = NaN`` with 7,111,787 NaN cells and 5,167,373 finite cells; the finite
cells define our bridge-relative footprint. Official-origin identity is not
independently authenticated by the bridge hashes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine

EPSG = 32611
HEIGHT = 3730
WIDTH = 3292
TRANSFORM = Affine(100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
PIXEL_M = 100.0

# --- names the earlier lanes' modules (gates.py, submission_writer.py) import ---
# Added at merge time so those modules keep working unchanged rather than being
# forked. Same six pinned numbers, same measured shape; no second source of truth.
SHAPE = (HEIGHT, WIDTH)
CELL_M = PIXEL_M
CRS_EPSG = f"EPSG:{EPSG}"

SHA256_EXISTING_FAULTS = "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093"
SHA256_SAMPLE_SUBMISSION = "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc"

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "bridge"


@dataclass(frozen=True)
class Grid:
    footprint: np.ndarray      # bool, scored study-area cells (sample_submission finite)
    catalogue: np.ndarray      # bool, mapped USGS/INGENIOUS fault cells inside the footprint
    crs: object
    transform: object
    height: int
    width: int

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)


def _check(src, what: str) -> None:
    if str(src.crs) != f"EPSG:{EPSG}":
        raise ValueError(f"{what}: CRS is {src.crs}, expected EPSG:{EPSG}")
    if (src.height, src.width) != (HEIGHT, WIDTH):
        raise ValueError(f"{what}: shape {src.height}x{src.width}, expected {HEIGHT}x{WIDTH}")
    if tuple(src.transform)[:6] != tuple(TRANSFORM)[:6]:
        raise ValueError(f"{what}: transform {tuple(src.transform)}, expected {tuple(TRANSFORM)}")


def load_grid(data_dir: Path | None = None) -> Grid:
    d = Path(data_dir) if data_dir else DATA_DIR
    with rasterio.open(d / "existing_faults.tif") as src:
        _check(src, "existing_faults.tif")
        cat = src.read(1)
    with rasterio.open(d / "sample_submission.tif") as src:
        _check(src, "sample_submission.tif")
        sub = src.read(1)
    footprint = np.isfinite(sub)
    catalogue = (cat > 0) & footprint
    return Grid(footprint=footprint, catalogue=catalogue, crs=src.crs,
                transform=TRANSFORM, height=HEIGHT, width=WIDTH)


def write_submission(path: Path, values: np.ndarray, *, mode: str = "nan") -> dict:
    """Serialize predictions using the official sample's null/NaN outside mask.

    ``mode="nan"`` is the submission representation: finite in-range
    probabilities are required inside the footprint, and cells outside it are
    written as NaN with a NaN nodata tag. Existing NaNs are accepted only
    outside the footprint. ``mode="zeros"`` is retained for internal
    diagnostics and is not portal-format compliant.
    """
    values = np.asarray(values)
    if values.shape != (HEIGHT, WIDTH):
        raise ValueError(f"values shape {values.shape} != {(HEIGHT, WIDTH)}")
    if not np.issubdtype(values.dtype, np.number):
        raise ValueError("values must be numeric")
    footprint = load_grid().footprint
    if mode == "nan":
        if np.isinf(values).any():
            raise ValueError("submission cannot contain infinite values")
        if not np.isfinite(values[footprint]).all():
            raise ValueError("submission values inside the footprint must be finite")
        if (values[footprint] < 0.0).any() or (values[footprint] > 1.0).any():
            raise ValueError("submission values inside the footprint must be in [0,1]; no clipping")
        if np.any(np.isfinite(values[~footprint]) & (values[~footprint] != 0.0)):
            raise ValueError("only zero/NaN input is allowed outside the footprint")
        out = values.astype(np.float32, copy=True)
        out[~footprint] = np.nan
        nodata = float("nan")
    elif mode == "zeros":
        if not np.isfinite(values).all():
            raise ValueError("diagnostic zeros mode requires all values finite")
        if (values < 0.0).any() or (values > 1.0).any():
            raise ValueError("values must be in [0,1]; no clipping")
        out = values.astype(np.float32, copy=False)
        nodata = None
    else:
        raise ValueError("mode must be 'nan' or 'zeros'")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path, "w", driver="GTiff", height=HEIGHT, width=WIDTH, count=1,
        dtype="float32", crs=f"EPSG:{EPSG}", transform=TRANSFORM,
        nodata=nodata, compress="lzw", tiled=False,
    ) as dst:
        dst.write(out, 1)
        dst.set_band_description(1, "predicted_new_fault_probability")
    return {"path": str(path), "mode": mode,
            "nodata": "NaN" if nodata is not None and np.isnan(nodata) else nodata}

def read_geotiff(path: str | Path) -> dict:
    """Everything a validator can complain about, re-derived from the bytes on disk.

    Kept byte-compatible with the earlier lanes' receipt format so their gates
    still read what they expect.
    """
    import hashlib

    p = Path(path)
    with rasterio.open(p) as src:
        a = src.read(1)
        info = dict(
            path=str(p), bytes=p.stat().st_size,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            bands=src.count, dtype=src.dtypes[0], height=src.height, width=src.width,
            crs=str(src.crs) if src.crs is not None else None,
            transform=[float(v) for v in tuple(src.transform)[:6]],
            res=[float(v) for v in src.res],
            nodata=src.nodata, nodata_repr=repr(src.nodata),
        )
    finite = np.isfinite(a)
    info.update(
        finite_pixels=int(finite.sum()),
        min=float(np.nanmin(a)) if finite.any() else None,
        max=float(np.nanmax(a)) if finite.any() else None,
        positive_pixels=int((a > 0).sum()),
        nonzero_in_footprint=int(((a > 0) & finite).sum()),
        unique_values=int(len(np.unique(a[finite]))) if finite.any() else 0,
    )
    return info


def write_geotiff(path: str | Path, arr: np.ndarray, *, nodata: float | None = None) -> dict:
    """Write a single-band float32 GeoTIFF on the pinned grid and re-read it.

    NaN cells are permitted only when the caller explicitly sets ``nodata`` to
    NaN; the shared submission writer uses that form for cells outside the
    official study footprint. This low-level function cannot verify where those
    cells occur, so pass its result through the footprint-aware validator.
    """
    from rasterio.transform import from_origin

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if arr.dtype != np.float32:
        raise TypeError(f"submission must be float32, got {arr.dtype}")
    if arr.shape != SHAPE:
        raise ValueError(f"submission must be {SHAPE}, got {arr.shape}")
    allow_nan = nodata is not None and np.isnan(nodata)
    if np.isinf(arr).any() or (np.isnan(arr).any() and not allow_nan):
        raise ValueError("NaN is allowed only with nodata=NaN; infinite values are never allowed")
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        raise ValueError("GeoTIFF must contain at least one finite probability")
    if finite.min() < 0.0 or finite.max() > 1.0:
        raise ValueError(f"submission out of range: min={finite.min()} max={finite.max()}")
    tr = Affine(*[float(v) for v in tuple(TRANSFORM)[:6]])
    west, north, xs, ys = tr.c, tr.f, tr.a, -tr.e
    check = from_origin(west, north, xs, ys)
    if tuple(float(v) for v in check)[:6] != tuple(tr)[:6]:
        raise AssertionError(f"transform drifted: {tuple(check)[:6]} != {tuple(tr)[:6]}")
    if abs(xs) != CELL_M or abs(ys) != CELL_M:
        raise AssertionError(f"cell size {xs} x {ys} != {CELL_M} m")
    profile = dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                   dtype="float32", crs=CRS_EPSG, transform=tr,
                   tiled=True, blockxsize=256, blockysize=256,
                   compress="deflate", predictor=2)
    if nodata is not None:
        profile["nodata"] = float(nodata)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr, 1)
    return read_geotiff(path)
