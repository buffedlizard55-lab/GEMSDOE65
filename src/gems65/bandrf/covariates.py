"""The declared propensity covariate set of this lane.

Five covariates, each with a stated source and a stated limitation.  All of
them are read on the pinned competition grid (3730 x 3292, EPSG:32611, 100 m)
from mirrors that are hash-pinned by ``scripts/restore_inputs.py``; none is
computed from the fault catalogue, so the set is label-free and safe to use
inside the hide-and-recover folds.

==================  ==========================================================
covariate           definition used here
==================  ==========================================================
``relief``          local relief: range (max - min) of the mirrored 100 m DEM in
                    a 5 x 5 (500 m) window; where the DEM has no data the same
                    statistic is taken from the official ``det_elev`` band.
``slope``           official band 19 ``det_elev_slope`` ("gradient of elevation
                    after detrending").
``basinfill``       official band 15 ``depth_to_base_surf`` -- the competition
                    stack's own "depth to basement surface / thickness of
                    sedimentary cover", i.e. a gravity-derived basin-fill proxy.
``lidar``           1 where the mirrored 1 m-lidar-derived
                    ``lidar_scarp_features_u8`` band 12 (``valid``) is positive,
                    else 0: a survey-coverage indicator, not a geological layer.
``rangefront``      Euclidean distance (m) to a range front mapped from
                    topography alone: mountain = (relief >= 100 m) & (slope >=
                    5 deg); front = mountain pixels adjacent to non-mountain;
                    distance transform on the front mask, capped at 3000 m.
==================  ==========================================================

None of these is claimed to be organizer-authenticated: ``relief`` comes from a
mirrored USGS-style DEM and ``lidar`` from a mirrored derived layer.  The three
official bands (``det_elev_slope``, ``depth_to_base_surf``, ``det_elev``) are
read from the pinned 19-band competition mirror.

No public, exhaustive 1:24,000 quadrangle index for this footprint was found in
this session, so the propensity **scale** is not anchored to an independent
coverage measure and every downstream number that uses ``e(x)`` is reported as
a sensitivity analysis (see the run card).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

from .. import common as _common  # noqa: F401  (repository root + sys.path bootstrap)

REPO_ROOT = _common.ROOT
DATA = REPO_ROOT / "data"

#: Mirrored inputs, restored by ``scripts/restore_inputs.py`` (hash-pinned).
PATHS = {
    "dem": DATA / "mirrors" / "geodawn_dem_a2_100m.tif",
    "lidar_scarp": DATA / "mirrors" / "lidar_scarp_features_u8.tif",
    "training_features": DATA / "official" / "training_features.tif",
}

#: Official band names in the 19-band stack (order verified from the file tags).
OFFICIAL_BANDS = {
    "mag_anom": 1, "rtp": 2, "tmi_hg": 3, "geod_2ndinv": 4, "iso_grav_anom_slope": 5,
    "tc": 6, "geod_shearrate": 7, "geod_dilaterate": 8, "tmi_vg": 9,
    "deq_n100a15": 10, "iso_grav_anom_vg": 11, "det_elev": 12, "iso_grav_anom": 13,
    "tmi": 14, "depth_to_base_surf": 15, "ieq_n100a15": 16, "cond_surf": 17,
    "iso_grav_anom_hg": 18, "det_elev_slope": 19,
}

DEM_NODATA_BELOW = -1000.0     # the mirrored DEM flags void as -999999
RELIF_WINDOW = 5               # 500 m at 100 m pixels
RELIEF_MOUNTAIN_M = 100.0      # protocol threshold (metres of 500 m relief)
SLOPE_MOUNTAIN_DEG = 5.0       # protocol threshold (degrees)
FRONT_CAP_M = 3000.0           # distance cap for the range-front covariate

COVARIATE_NAMES = ("relief", "slope", "basinfill", "lidar", "rangefront")


@dataclass
class Covariates:
    """The five named covariates on the competition grid, plus diagnostics."""

    values: dict
    shape: tuple
    diagnostics: dict

    def stack(self, names=COVARIATE_NAMES) -> np.ndarray:
        return np.stack([self.values[n] for n in names], axis=-1)


def read_band(path: Path, band: int = 1) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(band)


def _window_range(a: np.ndarray, size: int) -> np.ndarray:
    mx = ndi.maximum_filter(a, size=size, mode="nearest")
    mn = ndi.minimum_filter(a, size=size, mode="nearest")
    return (mx - mn).astype(np.float32)


def build(footprint: np.ndarray, *, paths: dict | None = None) -> Covariates:
    """Compute the five covariates on the full grid (NaN-free inside footprint).

    ``footprint`` is the scored study-region mask (``sample_submission`` finite
    cells, which by construction contain every catalogue pixel).
    """
    p = dict(PATHS if paths is None else paths)
    footprint = np.asarray(footprint, bool)
    missing = [k for k, v in p.items() if not Path(v).is_file()]
    if missing:
        raise FileNotFoundError(
            f"missing mirrored inputs {missing}; run scripts/restore_inputs.py first")

    det_elev = read_band(p["training_features"], OFFICIAL_BANDS["det_elev"])
    det_elev_slope = read_band(p["training_features"], OFFICIAL_BANDS["det_elev_slope"])
    basinfill = read_band(p["training_features"], OFFICIAL_BANDS["depth_to_base_surf"])

    dem = read_band(p["dem"])
    dem_valid = dem > DEM_NODATA_BELOW
    relief_dem = _window_range(np.where(dem_valid, dem, 0.0), RELIF_WINDOW)
    relief_elev = _window_range(np.where(np.isfinite(det_elev), det_elev, 0.0), RELIF_WINDOW)
    relief = np.where(dem_valid, relief_dem, relief_elev).astype(np.float32)

    lidar_band = read_band(p["lidar_scarp"], 12)
    lidar = (lidar_band > 0).astype(np.float32)

    slope_deg = np.degrees(np.arctan(np.abs(det_elev_slope).astype(np.float64))).astype(np.float32)
    mountain = (relief >= RELIEF_MOUNTAIN_M) & (slope_deg >= SLOPE_MOUNTAIN_DEG) & footprint
    basin = (~mountain) & footprint
    front = mountain & ndi.binary_dilation(basin, iterations=1)
    distance_px = ndi.distance_transform_edt(~front)
    rangefront = np.minimum(distance_px * 100.0, FRONT_CAP_M).astype(np.float32)

    values = {"relief": relief, "slope": slope_deg, "basinfill": basinfill.astype(np.float32),
              "lidar": lidar, "rangefront": rangefront}
    diagnostics = {
        "dem_valid_px": int((dem_valid & footprint).sum()),
        "footprint_px": int(footprint.sum()),
        "relief_from_det_elev_px": int((~dem_valid & footprint).sum()),
        "mountain_fraction": float(mountain.sum() / max(footprint.sum(), 1)),
        "lidar_fraction": float((lidar[footprint] > 0).mean()),
        "rangefront_front_px": int(front.sum()),
        "relief_threshold_m": RELIEF_MOUNTAIN_M,
        "slope_threshold_deg": SLOPE_MOUNTAIN_DEG,
        "relief_window_px": RELIF_WINDOW,
        "rangefront_cap_m": FRONT_CAP_M,
        "sources": {k: str(v) for k, v in p.items()},
    }
    for name, arr in values.items():
        v = arr[footprint]
        diagnostics[f"{name}_p05"] = float(np.percentile(v, 5))
        diagnostics[f"{name}_p50"] = float(np.percentile(v, 50))
        diagnostics[f"{name}_p95"] = float(np.percentile(v, 95))
    return Covariates(values=values, shape=footprint.shape, diagnostics=diagnostics)


def design_matrix(cov: Covariates, rows: tuple[np.ndarray, np.ndarray],
                  names=COVARIATE_NAMES) -> np.ndarray:
    """Covariate values at ``rows`` as a float64 matrix (n_rows x n_names)."""
    ys, xs = rows
    return np.stack([cov.values[n][ys, xs] for n in names], axis=1).astype(np.float64)


def standardize_fit(X: np.ndarray) -> dict:
    """Robust (median/IQR) scaling fitted on the training rows only."""
    med = np.median(X, axis=0)
    q1 = np.percentile(X, 25, axis=0)
    q3 = np.percentile(X, 75, axis=0)
    scale = np.where((q3 - q1) > 0, q3 - q1, 1.0)
    return dict(median=med, scale=scale)


def standardize(X: np.ndarray, stats: dict, clip: float = 6.0) -> np.ndarray:
    Z = (np.asarray(X, np.float64) - stats["median"]) / stats["scale"]
    return np.clip(Z, -clip, clip)
