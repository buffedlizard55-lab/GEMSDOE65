"""Grid constants and raster I/O for the DOE GEMS Prize Challenge (DrivenData 306).

Every constant in this module is MEASURED in this checkout from hash-pinned bytes; see
``registry/data_manifest.json`` for the sha256 of each input and
``scripts/01_prepare_data.py`` for the command that reproduces them.

Grid (verified by reading ``sample_submission.tif``, sha256 2176d08e...):
    width  3292, height 3730, EPSG:32611, transform (100, 0, 243350, 0, -100, 4508550)
    footprint (finite in sample_submission) = 5,167,373 px
    labels.tif int8 {-1, 0, 1}: 60,988 catalogue pixels
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import rasterio

WIDTH = 3292
HEIGHT = 3730
EPSG = 32611
TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
SHAPE = (HEIGHT, WIDTH)
TOTAL_PIXELS = HEIGHT * WIDTH                 # 12,279,160
FOOTPRINT_PIXELS = 5_167_373                  # measured
LABEL_PIXELS = 60_988                         # measured
PIXEL_M = 100.0                               # 1 px = 100 m
KERNEL_RADIUS_M = 300.0                       # official triangular-kernel radius
KERNEL_RADIUS_PX = KERNEL_RADIUS_M / PIXEL_M  # 3.0 px
ALPHA = 0.2
BETA = 0.8

# sha256 pins, copied verbatim from the owner-supplied mirror receipt and re-verified here.
EXPECTED_SHA256 = {
    "training_features.tif": "4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
    "labels.tif": "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093",
    "sample_submission.tif": "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc",
    "external/lidar_scarp_features_u8.tif": "d580bb8bdcdb941e32fefb8b38044bc5bf04e199bf2e83498c3576e6fc465568",
}

# Authoritative band names + categories, read from the GeoTIFF band tags of the pinned
# training_features.tif (tag keys: band_name / data_category / description).
BANDS = [
    (1, "mag_anom", "magnetic_data"),
    (2, "rtp", "magnetic_data"),
    (3, "tmi_hg", "magnetic_data"),
    (4, "geod_2ndinv", "geodetic_strain"),
    (5, "iso_grav_anom_slope", "gravity_data"),
    (6, "tc", "magnetic_data"),
    (7, "geod_shearrate", "geodetic_strain"),
    (8, "geod_dilaterate", "geodetic_strain"),
    (9, "tmi_vg", "magnetic_data"),
    (10, "deq_n100a15", "seismic"),
    (11, "iso_grav_anom_vg", "gravity_data"),
    (12, "det_elev", "topographic"),
    (13, "iso_grav_anom", "gravity_data"),
    (14, "tmi", "magnetic_data"),
    (15, "depth_to_base_surf", "subsurface"),
    (16, "ieq_n100a15", "seismic"),
    (17, "cond_surf", "subsurface"),
    (18, "iso_grav_anom_hg", "gravity_data"),
    (19, "det_elev_slope", "topographic"),
]
BAND_NAMES = [b[1] for b in BANDS]
BAND_INDEX = {name: idx for idx, name, _ in BANDS}

# Band 12 of external/lidar_scarp_features_u8.tif is "valid" per that product's own JSON
# sidecar (external/lidar_scarp_features.json, key "bands"); 0 == "no lidar" per
# "quantisation_rule".  Used as the lidar-coverage propensity covariate.
LIDAR_VALID_BAND = 12


def data_dir() -> Path:
    """Location of the hash-pinned competition data (outside git; restored by script 00)."""
    return Path(os.environ.get("GEMS65_DATA", "/home/user/.cache/gems_data/data"))


def work_dir() -> Path:
    return Path(os.environ.get("GEMS65_WORK", "/home/user/.cache/gems65_work"))


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_footprint(ddir: Path | None = None) -> np.ndarray:
    ddir = ddir or data_dir()
    with rasterio.open(ddir / "sample_submission.tif") as ds:
        a = ds.read(1)
    foot = np.isfinite(a)
    assert foot.shape == SHAPE, foot.shape
    return foot


def read_labels(ddir: Path | None = None) -> np.ndarray:
    ddir = ddir or data_dir()
    with rasterio.open(ddir / "labels.tif") as ds:
        a = ds.read(1)
    return (a == 1) & np.isfinite(a.astype(np.float32))


def read_band(name: str, ddir: Path | None = None, window=None) -> np.ndarray:
    """Read one feature band as float32 with the sentinel replaced by NaN."""
    ddir = ddir or data_dir()
    idx = BAND_INDEX[name]
    with rasterio.open(ddir / "training_features.tif") as ds:
        b = ds.read(idx, window=window).astype(np.float32)
    b[b < -1e38] = np.nan
    return b


def read_lidar_band(i: int, ddir: Path | None = None) -> np.ndarray:
    ddir = ddir or data_dir()
    with rasterio.open(ddir / "external" / "lidar_scarp_features_u8.tif") as ds:
        return ds.read(i)


def check_grid(tif_path: Path) -> dict:
    """Independent re-read of a candidate's geometry (never trusts the writer)."""
    with rasterio.open(tif_path) as ds:
        return {
            "path": str(tif_path),
            "width": ds.width,
            "height": ds.height,
            "count": ds.count,
            "dtype": ds.dtypes[0],
            "crs": str(ds.crs),
            "transform": [round(float(v), 6) for v in tuple(ds.transform)[:6]],
            "nodata": None if ds.nodata is None else float(ds.nodata),
            "shape_ok": (ds.width, ds.height) == (WIDTH, HEIGHT),
            "crs_ok": str(ds.crs).endswith("32611"),
            "transform_ok": tuple(round(float(v), 6) for v in tuple(ds.transform)[:6]) == TRANSFORM,
            "single_band_ok": ds.count == 1,
            "dtype_ok": ds.dtypes[0] == "float32",
        }
