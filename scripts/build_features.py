"""Build the cached feature stack for the GEMSDOE65 SAR-propensity PU lane.

Channels (in order) come from two verified inputs only:

* ``data/raw/training_features.tif`` -- the official competition feature stack,
  sha256 ``4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5``
  (re-assembled from the five pinned ``part-000..004`` blobs; the manifest in
  ``data/bridge/manifest.json`` of the transport repo pins that hash).
* ``data/external/geodawn_dem_a2_100m.tif`` -- the public GeoDAWN airborne-DEM
  mirror used here **only** as a survey-coverage indicator (finite mask), i.e.
  "was 1 m GeoDAWN lidar acquired and gridded here".  It is a coverage
  covariate, not a fault detector.

Derived channels:

* ``relief_1km`` -- local relief = max-min of the official detrended elevation
  in a 10 px (1 km) window, the "local relief" covariate of the brief.
* ``dist_range_front_px`` -- Euclidean distance (px) to the nearest mountain-
  block / basin-fill contact, i.e. a range front.  Defined on the official
  ``depth_to_base_surf`` band (basin fill) and the official detrended elevation,
  with the thresholds written into the metadata JSON so the definition is
  auditable.  No catalogue pixel enters this channel.

No catalogue-derived channel exists in the stack: every catalogue-based feature
of the protocol would have to be rebuilt from the *visible* faults inside each
holdout fold, so the lane deliberately uses geophysics/terrain covariates only
(leakage canary result recorded in the run card).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor"))

from gems57 import grid as G  # noqa: E402  (shared template)

FEATURES_TIF = ROOT / "data" / "raw" / "training_features.tif"
COVERAGE_TIF = ROOT / "data" / "external" / "geodawn_dem_a2_100m.tif"
OUT_DIR = ROOT / "data" / "derived"
NODATA = np.float32(-3.4028235e38)

# The 19 official bands, in file order.  Names are the band descriptions.
OFFICIAL = [
    "mag_anom", "rtp", "tmi_hg", "geod_2ndinv", "iso_grav_anom_slope", "tc",
    "geod_shearrate", "geod_dilaterate", "tmi_vg", "deq_n100a15",
    "iso_grav_anom_vg", "det_elev", "iso_grav_anom", "tmi", "depth_to_base_surf",
    "ieq_n100a15", "cond_surf", "iso_grav_anom_hg", "det_elev_slope",
]
DERIVED = ["relief_1km", "lidar_coverage", "dist_range_front_px"]
CHANNELS = OFFICIAL + DERIVED

# Propensity covariates of the registered lane (indices into CHANNELS).
PROPENSITY = {
    "relief_1km": CHANNELS.index("relief_1km"),
    "slope": CHANNELS.index("det_elev_slope"),
    "basin_fill_gdd": CHANNELS.index("depth_to_base_surf"),
    "lidar_coverage": CHANNELS.index("lidar_coverage"),
    "dist_range_front_px": CHANNELS.index("dist_range_front_px"),
}


def _clean(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, np.float32)
    bad = ~np.isfinite(a) | (a <= NODATA / 2)
    return np.where(bad, np.nan, a).astype(np.float32)


def _fill_nan(a: np.ndarray, fill: float) -> np.ndarray:
    """NaN-safe replacement used only for window/distance arithmetic."""
    out = a.copy()
    out[~np.isfinite(out)] = fill
    return out


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    grid = G.load_grid(ROOT / "data" / "bridge")
    fp = np.asarray(grid.footprint, bool)
    h, w = grid.shape

    with rasterio.open(FEATURES_TIF) as src:
        if (src.height, src.width) != (h, w):
            raise SystemExit(f"feature raster shape {src.height}x{src.width} != grid {h}x{w}")
        if str(src.crs) != f"EPSG:{G.EPSG}":
            raise SystemExit(f"feature raster CRS {src.crs} != EPSG:{G.EPSG}")
        if tuple(src.transform)[:6] != tuple(G.TRANSFORM)[:6]:
            raise SystemExit("feature raster transform != official grid transform")
        bands = [_clean(src.read(i + 1)) for i in range(src.count)]

    # --- derived covariates -------------------------------------------------
    det_elev = _fill_nan(bands[OFFICIAL.index("det_elev")],
                         float(np.nanmedian(bands[OFFICIAL.index("det_elev")])))
    relief = (ndi.maximum_filter(det_elev, size=10) -
              ndi.minimum_filter(det_elev, size=10)).astype(np.float32)
    basin = bands[OFFICIAL.index("depth_to_base_surf")]
    basin_med = float(np.nanmedian(basin[fp]))
    relief_med = float(np.nanmedian(relief[fp]))
    # Range front: contact between mountain block (relief above the footprint
    # median) and basin fill (depth-to-basement above its footprint median).
    mountain = (relief > relief_med) & fp
    basin_fill = (np.nan_to_num(basin, nan=-np.inf) > basin_med) & fp
    block = ndi.binary_closing(mountain, structure=np.ones((7, 7), bool))
    contact = block & ndi.binary_dilation(basin_fill, iterations=2)
    dist_front = ndi.distance_transform_edt(~contact).astype(np.float32)

    lidar = np.zeros((h, w), bool)
    coverage_transform = None
    coverage_nodata = None
    if COVERAGE_TIF.is_file():
        with rasterio.open(COVERAGE_TIF) as src:
            if (src.height, src.width) != (h, w):
                raise SystemExit("GeoDAWN coverage mirror is not on the official grid shape")
            # The public mirror differs from the official grid origin by 0.034 m
            # (2.9e-7 px) -- a reprojection rounding artefact, recorded rather
            # than silently accepted. Offsets above 1 m are rejected.
            dx = abs(src.transform.c - G.TRANSFORM.c)
            dy = abs(src.transform.f - G.TRANSFORM.f)
            if dx > 1.0 or dy > 1.0 or src.transform.a != G.TRANSFORM.a or src.transform.e != G.TRANSFORM.e:
                raise SystemExit(f"GeoDAWN coverage mirror is not on the official grid (dx={dx}, dy={dy})")
            coverage_transform = list(tuple(src.transform)[:6])
            coverage_nodata = float(src.nodata) if src.nodata is not None else None
            cov = src.read(1)
            # The mirror's explicit nodata tag is -999999.0; a finite-value test
            # alone would keep the sentinel, so both are applied.
            finite = np.isfinite(cov)
            if coverage_nodata is not None:
                finite &= (cov != coverage_nodata)
            lidar = finite
    else:
        raise SystemExit(f"coverage mirror missing: {COVERAGE_TIF}")

    stack = np.lib.format.open_memmap(OUT_DIR / "feature_stack.npy", mode="w+",
                                      dtype=np.float32, shape=(len(CHANNELS), h, w))
    for i, a in enumerate(bands):
        stack[i] = a
    stack[len(OFFICIAL)] = relief
    stack[len(OFFICIAL) + 1] = lidar.astype(np.float32)
    stack[len(OFFICIAL) + 2] = dist_front
    stack.flush()
    del stack

    meta = dict(
        channels=CHANNELS,
        shape=[h, w],
        crs=f"EPSG:{G.EPSG}",
        transform=list(tuple(G.TRANSFORM)[:6]),
        footprint_cells=int(fp.sum()),
        feature_tif_sha256="4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5",
        coverage_tif_sha256=__import__("hashlib").sha256(COVERAGE_TIF.read_bytes()).hexdigest(),
        lidar_coverage_cells=int(lidar.sum()),
        coverage_mirror_transform=coverage_transform,
        coverage_mirror_nodata=coverage_nodata,
        coverage_mirror_note=("Public GeoDAWN DEM mirror; origin differs from the official grid "
                              "by 0.034 m (2.9e-7 px). Used as a coverage mask only. Official "
                              "identity of the mirror is not authenticated."),
        range_front_definition=dict(relief_window_px=10, relief_median_m=relief_med,
                                    basin_median_m=basin_med,
                                    morph_close_px=7, basin_dilate_px=2),
        propensity_covariates=PROPENSITY,
        catalogue_channels=[],
        note=("Derived from the official feature stack plus a GeoDAWN DEM coverage "
              "mask; no catalogue pixel is used in any channel."),
    )
    (OUT_DIR / "feature_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps({k: v for k, v in meta.items() if k != "channels"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
