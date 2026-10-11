"""Propensity covariates x_e and classifier features, all non-catalogue by construction.

The lane's propensity model may only see the five covariates named in the brief
(local relief, slope, gravity-derived basin-fill proxy, lidar coverage, distance to range
front).  Every one of them is derived from terrain / gravity / survey-coverage data and NONE
of them is derived from the fault catalogue, so a blocked holdout that hides whole catalogue
segments cannot leak through the covariate set.  This is checked numerically by
``scripts/05_leakage_canary.py`` (single-feature holdout AUC must stay below 0.90).

Definitions, with the physical justification and the exact source of every input:

relief  local relief = max - min of ``det_elev`` (band 12, tag description "Detrended
        elevation - topography with regional trends removed") over a 5x5 px (500 m) window.
        Detrending removes only the long-wavelength regional tilt, so a 500 m window of the
        detrended surface retains the local relief that makes a scarp visible to a mapper.

slope   ``det_elev_slope`` (band 19, "Detrended elevation slope"), used as provided by the
        organizers.  Steep relief is the single strongest observability driver: the brief's
        own cited evidence is that ~92% of mapped step-overs sit on range-front faults
        "partly because steep relief makes them easy to see".

basin   Gravity-derived basin-fill proxy = -z( lowpass(iso_grav_anom, sigma=10 px) ), i.e.
        high where the isostatic gravity anomaly (band 13, category ``gravity_data``,
        "gravity after compensating for topographic mass") is low, which is the signature of
        a thick, low-density sedimentary basin fill.  Validated in prep against
        ``depth_to_base_surf`` (band 15, "Depth to basement surface - thickness of
        sedimentary cover"): the two must correlate positively if the proxy is real, and the
        measured Pearson r is written to ``evidence/covariates.json``.

lidar   Survey coverage = band 12 (``valid``) of ``external/lidar_scarp_features_u8.tif`` > 0.
        That product's own sidecar ``external/lidar_scarp_features.json`` names band 12
        ``valid`` and states the quantisation rule "0 = no lidar".  The layer was derived by
        the owner's CI from USGS 3DEP 1 m DEM tiles; the 716-tile index it used is mirrored
        at ``external/dem_links.json`` and points at USGS ``prd-tnm`` S3 URLs (public domain).
        Measured coverage inside the footprint is reported, and it is the observable stand-in
        for the brief's "~25% of the region has detailed (~1:24,000) mapping".

front   Distance to range front.  Range mask R = (relief >= q70(relief)) & (lowpass(det_elev,
        sigma=5) >= median(lowpass)); the range front is the outer 2 px rim of R
        (R & ~erode(R, 2)) and the covariate is the Euclidean distance transform to it, in
        pixels (1 px = 100 m).  Basin-and-range geomorphology: the mountain front is where
        range blocks meet basin fill, and it is where catalogue fault density peaks.

Classifier features phi(x) are the 19 provided bands plus four derived terrain terms
(relief, plan/profile-free curvature proxy, and two horizontal-gradient magnitudes).  All are
standardised with statistics computed on the training population of each fold only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.ndimage import (
    binary_dilation,
    binary_erosion,
    distance_transform_edt,
    gaussian_filter,
    maximum_filter,
    minimum_filter,
)

from . import grid as G

RELIEF_WIN = 5           # px, 500 m
BASIN_SIGMA = 10.0       # px, ~1 km sigma -> ~2-3 km effective wavelength
FRONT_SMOOTH_SIGMA = 5.0
FRONT_RELIEF_Q = 0.70
FRONT_RIM_PX = 2
DERIVED_NAMES = ("relief", "curv", "grad_det_elev", "grad_iso_grav")
COVARIATE_NAMES = ("relief", "slope", "basin_fill", "lidar_cov", "dist_range_front")


def _zn(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Standardise inside a mask; NaN-safe; returns 0 where undefined."""
    v = a[mask]
    v = v[np.isfinite(v)]
    if v.size == 0:
        return np.zeros_like(a, dtype=np.float32)
    mu, sd = float(np.mean(v)), float(np.std(v))
    out = (a - mu) / (sd + 1e-9)
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def local_relief(det_elev: np.ndarray, win: int = RELIEF_WIN) -> np.ndarray:
    a = np.nan_to_num(det_elev, nan=float(np.nanmedian(det_elev)))
    mx = maximum_filter(a, size=win, mode="nearest")
    mn = minimum_filter(a, size=win, mode="nearest")
    return (mx - mn).astype(np.float32)


def curvature_proxy(det_elev: np.ndarray, sigma: float = 1.0) -> np.ndarray:
    """Laplacian of a lightly smoothed detrended elevation: negative = crest, positive = base."""
    a = np.nan_to_num(det_elev, nan=float(np.nanmedian(det_elev)))
    s = gaussian_filter(a, sigma=sigma, mode="nearest")
    gy, gx = np.gradient(s)
    gyy = np.gradient(gy, axis=0)
    gxx = np.gradient(gx, axis=1)
    return (-(gyy + gxx)).astype(np.float32)


def grad_mag(a: np.ndarray) -> np.ndarray:
    b = np.nan_to_num(a, nan=float(np.nanmedian(a)))
    gy, gx = np.gradient(b)
    return np.hypot(gy, gx).astype(np.float32)


def range_front_distance(det_elev: np.ndarray, relief: np.ndarray, footprint: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (distance-to-range-front in px, range-front mask)."""
    r = np.where(footprint, relief, np.nan)
    q = float(np.nanquantile(r, FRONT_RELIEF_Q))
    smooth = gaussian_filter(np.nan_to_num(det_elev, nan=float(np.nanmedian(det_elev))),
                             FRONT_SMOOTH_SIGMA, mode="nearest")
    med = float(np.median(smooth[footprint]))
    rng_mask = footprint & (relief >= q) & (smooth >= med)
    if not rng_mask.any():
        return np.full(det_elev.shape, 999.0, np.float32), rng_mask
    rim = rng_mask & ~binary_erosion(rng_mask, iterations=FRONT_RIM_PX)
    if not rim.any():
        rim = rng_mask
    dist = distance_transform_edt(~rim).astype(np.float32)
    dist[~footprint] = np.nan
    return dist, rim


def basin_fill_proxy(iso_grav: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    a = np.where(footprint, iso_grav, np.nan)
    fill = np.nanmedian(a)
    sm = gaussian_filter(np.nan_to_num(a, nan=fill), BASIN_SIGMA, mode="nearest")
    z = _zn(sm, footprint)
    return (-z).astype(np.float32)   # high == thick, light basin fill (low isostatic anomaly)


@dataclass
class CovariateStack:
    """The five propensity covariates, on the competition grid, plus provenance stats."""
    relief: np.ndarray
    slope: np.ndarray
    basin_fill: np.ndarray
    lidar_cov: np.ndarray
    dist_range_front: np.ndarray
    stats: dict

    def matrix(self, idx: np.ndarray) -> np.ndarray:
        """Row-major flat pixel indices -> (n, 5) float64 design matrix in COVARIATE_NAMES order."""
        return np.column_stack([
            self.relief.ravel()[idx].astype(np.float64),
            self.slope.ravel()[idx].astype(np.float64),
            self.basin_fill.ravel()[idx].astype(np.float64),
            self.lidar_cov.ravel()[idx].astype(np.float64),
            self.dist_range_front.ravel()[idx].astype(np.float64),
        ])

    def as_dict(self):
        return {
            "relief": self.relief, "slope": self.slope, "basin_fill": self.basin_fill,
            "lidar_cov": self.lidar_cov, "dist_range_front": self.dist_range_front,
        }


def build_covariates(ddir: Path | None = None, footprint: np.ndarray | None = None) -> CovariateStack:
    """Compute the five covariates from the pinned rasters.  Deterministic, no randomness."""
    ddir = ddir or G.data_dir()
    foot = footprint if footprint is not None else G.read_footprint(ddir)

    det_elev = G.read_band("det_elev", ddir)
    slope = G.read_band("det_elev_slope", ddir)
    iso_grav = G.read_band("iso_grav_anom", ddir)
    depth_base = G.read_band("depth_to_base_surf", ddir)

    relief = local_relief(det_elev)
    basin = basin_fill_proxy(iso_grav, foot)
    dist_front, rim = range_front_distance(det_elev, relief, foot)

    lid = G.read_lidar_band(G.LIDAR_VALID_BAND, ddir) > 0
    lidar_cov = (lid & foot).astype(np.float32)

    # Every covariate must be FINITE inside the footprint.  The source bands carry the float32
    # sentinel (-3.4028234663852886e+38 -> NaN) at 3,061-3,073 pixels INSIDE the footprint
    # (mechanism M1 of the range-error root cause), so a raw pass-through of det_elev_slope would
    # poison the propensity model with NaNs.  Fill with the in-footprint median, then mask outside.
    filled = {}
    for nm, arr in (("relief", relief), ("slope", slope), ("basin_fill", basin),
                    ("dist_range_front", dist_front)):
        bad = foot & ~np.isfinite(arr)
        good = foot & np.isfinite(arr)
        med = float(np.median(arr[good])) if good.any() else 0.0
        arr[bad] = med
        arr[~foot] = np.nan
        filled[nm] = {"in_footprint_nan_filled": int(bad.sum()), "fill_value": med}
    bad_lid = foot & ~np.isfinite(lidar_cov)
    lidar_cov[bad_lid] = 0.0
    lidar_cov[~foot] = np.nan
    filled["lidar_cov"] = {"in_footprint_nan_filled": int(bad_lid.sum()), "fill_value": 0.0}

    # validity check of the basin-fill proxy against an independent subsurface band
    m = foot & np.isfinite(basin) & np.isfinite(depth_base)
    r_depth = float(np.corrcoef(basin[m], np.log1p(np.clip(depth_base[m], 0, None)))[0, 1])
    lab = G.read_labels(ddir)
    stats = {
        "relief_win_px": RELIEF_WIN,
        "basin_sigma_px": BASIN_SIGMA,
        "front_relief_quantile": FRONT_RELIEF_Q,
        "front_rim_px": FRONT_RIM_PX,
        "lidar_band_used": G.LIDAR_VALID_BAND,
        "footprint_px": int(foot.sum()),
        "lidar_coverage_frac_of_footprint": float(lidar_cov[foot].mean()),
        "lidar_coverage_frac_of_grid": float(lid.mean()),
        "range_front_px": int(rim.sum()),
        "range_mask_px": int((foot & (relief >= np.nanquantile(relief[foot], FRONT_RELIEF_Q))).sum()),
        "basin_fill_vs_log_depth_to_base_pearson_r": r_depth,
        "label_share_in_lidar_covered": float(lab[lidar_cov > 0].sum() / max(int(lab.sum()), 1)),
        "in_footprint_nan_fill": filled,
        "covariate_quantiles": {
            name: {f"p{int(q*100)}": float(np.nanquantile(arr[foot], q))
                   for q in (0.05, 0.25, 0.5, 0.75, 0.95)}
            for name, arr in (("relief", relief), ("slope", slope), ("basin_fill", basin),
                              ("dist_range_front", dist_front))
        },
    }
    return CovariateStack(relief, slope, basin, lidar_cov, dist_front, stats)


def save_covariates(cv: CovariateStack, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        relief=cv.relief.astype(np.float32), slope=cv.slope.astype(np.float32),
        basin_fill=cv.basin_fill.astype(np.float32), lidar_cov=cv.lidar_cov.astype(np.float32),
        dist_range_front=cv.dist_range_front.astype(np.float32),
    )


def load_covariates(path: Path, stats: dict | None = None) -> CovariateStack:
    z = np.load(path)
    return CovariateStack(
        z["relief"].astype(np.float32), z["slope"].astype(np.float32),
        z["basin_fill"].astype(np.float32), z["lidar_cov"].astype(np.float32),
        z["dist_range_front"].astype(np.float32), stats or {},
    )
