"""Observability (propensity) covariates + the structural detector feature stack.

Everything here is derived from the OFFICIAL competition rasters in ``data/`` plus two
official, public-domain external products that are already vendored under
``data/external/`` with their own provenance receipts:

* ``derived_sgmc_faults_100m_u8.tif`` -- the USGS SGMC (state geologic map) compilation
  rasterised onto this exact competition grid.  Source: ``https://mrdata.usgs.gov/geology/state/shp/NV.zip``
  and ``.../CA.zip`` (USGS, public domain).  Used only as an *off-catalogue* truth proxy.
* ``dem1m_high_prior_openness_lrm.npz`` -- topographic-openness / local-relief-model
  statistics computed from eight official USGS 3DEP 1 m EarthMRI DEM tiles
  (``prd-tnm.s3.amazonaws.com`` NV_WestCentral_EarthMRI_2020_D20 project, public domain).
  Used only as the *lidar coverage* propensity covariate.

The five preregistered propensity covariates (see README "This session's method lane"):

==== ============================== =======================================================
 z1  ``relief``                     local relief of detrended elevation (band 12), 500 m window
 z2  ``slope``                      detrended-elevation slope (official band 19)
 z3  ``basin_fill``                 depth-to-basement / sedimentary-cover thickness (band 15),
                                    the gravity-derived basin-fill proxy
 z4  ``lidar_cov``                  1 m 3DEP lidar coverage mask (official tiles)
 z5  ``dist_rangefront``            distance to the basin-margin ("range front") escarpment

z5 is an OPERATIONAL proxy, not an independently mapped range front: it is the Euclidean
distance to the locus where the gravity-derived basin-fill thickness drops from basin
values to range-block values.  An independently mapped range front would require a
separate, verified structural linework product; none was obtained in this session, and
the substitution is recorded in ``docs/IRREGULARITIES.md`` rather than hidden.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import ndimage

from . import grid

NOD = grid.NODATA_F32

# official band numbers (1-based) -> covariate use
BAND_DET_ELEV = 12        # det_elev
BAND_DEPTH_BASE = 15      # depth_to_base_surf
BAND_DET_ELEV_SLOPE = 19  # det_elev_slope


# --------------------------------------------------------------------------------------
# propensity covariates
# --------------------------------------------------------------------------------------
def local_relief(det_elev: np.ndarray, size: int = 5) -> np.ndarray:
    """Local relief = max - min of detrended elevation over a ``size x size`` window."""
    a = np.where(np.isfinite(det_elev) & (det_elev > NOD * np.float32(0.5)), det_elev, np.nan)
    mx = ndimage.maximum_filter(a, size=size, mode="nearest")
    mn = ndimage.minimum_filter(a, size=size, mode="nearest")
    out = mx - mn
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def lidar_coverage(data_dir: Path = grid.DATA) -> np.ndarray:
    """Boolean 1 m 3DEP lidar coverage from the eight official EarthMRI 1 m tiles."""
    z = np.load(Path(data_dir) / "external" / "dem1m_high_prior_openness_lrm.npz")
    m = np.zeros((grid.open_template()["height"], grid.open_template()["width"]), bool)
    m.ravel()[z["cov_fp_indices"]] = True
    return m


def basin_margin_front(depth_to_base: np.ndarray, quantile: float = 0.5) -> np.ndarray:
    """Operational range-front proxy: the escarpment at the edge of the basin fill.

    A pixel is a "range front" pixel when the basin-fill thickness is thin (below the
    footprint median) *and* it is adjacent to thick basin fill, i.e. it sits on the
    mountain-block side of the basin margin.  This is the topographic expression of the
    range-bounding (range-front) fault system, derived only from official bands.
    """
    a = np.where(
        np.isfinite(depth_to_base) & (depth_to_base > NOD * np.float32(0.5)),
        depth_to_base,
        np.nan,
    )
    finite = np.isfinite(a)
    t = np.nanmedian(a[finite])
    basin = finite & (a > t)
    # erode the basin so the "edge" band is the mountain-block shoulder, not the basin centre
    basin_edge = basin & ~ndimage.binary_erosion(basin, iterations=2, border_value=1)
    shoulder = ndimage.binary_dilation(basin_edge, iterations=3) & ~basin
    return shoulder & finite


def build_propensity_covariates(data_dir: Path = grid.DATA) -> dict:
    """Return the five preregistered propensity covariates as float32 (H, W) arrays."""
    det_elev = grid.read_band(Path(data_dir) / "training_features.tif", BAND_DET_ELEV, fill=np.nan)
    depth = grid.read_band(Path(data_dir) / "training_features.tif", BAND_DEPTH_BASE, fill=np.nan)
    slope = grid.read_band(Path(data_dir) / "training_features.tif", BAND_DET_ELEV_SLOPE, fill=0.0)
    foot = grid.read_footprint(Path(data_dir) / "sample_submission.tif")

    relief = local_relief(det_elev)
    front = basin_margin_front(depth)
    dist_front = ndimage.distance_transform_edt(~front).astype(np.float32)
    lidar = lidar_coverage(data_dir).astype(np.float32)

    basin_fill = np.where(np.isfinite(depth), depth, 0.0).astype(np.float32)
    slope = np.where(np.isfinite(slope), slope, 0.0).astype(np.float32)

    cov = {
        "relief": relief,
        "slope": slope,
        "basin_fill": basin_fill,
        "lidar_cov": lidar,
        "dist_rangefront": dist_front,
    }
    cov["_footprint"] = foot
    cov["_front_px"] = front
    return cov


# --------------------------------------------------------------------------------------
# structural detector channels (reused from the shared template's cached feature stack)
# --------------------------------------------------------------------------------------
CHANNELS = [
    *[f"band{i:02d}" for i in range(1, 20)],
    "curv_s1", "curv_s2", "ridge_s1", "ridge_s2", "ridge_s3",
    "relief5", "tophat2", "tmi_edge", "rtp_edge", "grav_edge", "cond_edge",
    "depth_grad", "coherence_s2", "strike_cos", "strike_sin", "footprint",
]

NEED = {12, 14, 2, 13, 17, 15}


def _sm(a, s):
    return ndimage.gaussian_filter(a, s, mode="nearest")


def _grad_mag(a):
    gy, gx = np.gradient(a)
    return np.hypot(gx, gy)


def _hessian_ridge(a, sigma):
    """Sato/Frangi-style ridge response: largest |eigenvalue| with the ridge sign convention."""
    axx = ndimage.gaussian_filter(a, sigma, order=(0, 2), mode="nearest")
    ayy = ndimage.gaussian_filter(a, sigma, order=(2, 0), mode="nearest")
    axy = ndimage.gaussian_filter(a, sigma, order=(1, 1), mode="nearest")
    tmp = np.sqrt(np.maximum(((axx - ayy) * 0.5) ** 2 + axy ** 2, 0.0))
    l1 = (axx + ayy) * 0.5 + tmp
    l2 = (axx + ayy) * 0.5 - tmp
    big = np.where(np.abs(l1) >= np.abs(l2), l1, l2)
    small = np.where(np.abs(l1) >= np.abs(l2), l2, l1)
    return -small * (big < 0).astype(np.float32)


def _structure_tensor(a, sigma):
    gx = ndimage.gaussian_filter(a, sigma, order=(0, 1), mode="nearest")
    gy = ndimage.gaussian_filter(a, sigma, order=(1, 0), mode="nearest")
    jxx = _sm(gx * gx, sigma)
    jyy = _sm(gy * gy, sigma)
    jxy = _sm(gx * gy, sigma)
    tr = jxx + jyy + 1e-12
    coh = np.sqrt(np.maximum(((jxx - jyy) * 0.5) ** 2 + jxy ** 2, 0.0)) / tr
    theta = 0.5 * np.arctan2(2 * jxy, (jxx - jyy) + 1e-12)
    return coh.astype(np.float32), theta.astype(np.float32), np.sqrt(tr).astype(np.float32)


def build_feature_stack(features_path: Path, out_path: Path, log=print) -> dict:
    """Build the (H, W, F) float32 stack as a disk-backed array; returns a small receipt.

    This is the shared template's cached feature stack (``src/gems32/features.py``) reused
    verbatim in behaviour: the 19 official bands as given (sentinel -> 0, plus a footprint
    flag) and 16 derived line/structure transforms.  No distance-to-catalogue channel is
    included, by design -- that single column makes a detector AUC 1.0 on the visible
    catalogue and transfers nothing off it.
    """
    import rasterio

    with rasterio.open(features_path) as s:
        h, w, nb = s.height, s.width, s.count
        stack = np.lib.format.open_memmap(
            out_path, mode="w+", dtype=np.float32,
            shape=(h, w, len(CHANNELS) + max(0, nb - 19)),
        )
        kept = {}
        footprint = None
        for i in range(1, nb + 1):
            raw = s.read(i)
            if i == 1:
                footprint = np.isfinite(raw) & (raw > NOD * np.float32(0.5))
            a = np.where(raw < NOD * np.float32(0.5), np.float32(0.0), raw.astype(np.float32))
            del raw
            stack[:, :, i - 1] = a
            if i in NEED:
                kept[i] = a
            else:
                del a
            if log is not None and (i % 5 == 0 or i == nb):
                log(f"  band {i:2d}/{nb} read")

    dem = kept[12]
    c = 19
    stack[:, :, c] = ndimage.gaussian_laplace(dem, 1.0, mode="nearest"); c += 1
    stack[:, :, c] = ndimage.gaussian_laplace(dem, 2.5, mode="nearest"); c += 1
    for sigma in (1.0, 2.0, 3.5):
        stack[:, :, c] = _hessian_ridge(dem, sigma); c += 1
    loc = ndimage.maximum_filter(dem, size=5) - ndimage.minimum_filter(dem, size=5)
    stack[:, :, c] = loc; c += 1
    stack[:, :, c] = dem - ndimage.grey_opening(dem, size=(5, 5)); c += 1
    stack[:, :, c] = _sm(_grad_mag(kept[14]), 1.0); c += 1
    stack[:, :, c] = _sm(_grad_mag(kept[2]), 1.0); c += 1
    stack[:, :, c] = _sm(_grad_mag(kept[13]), 1.5); c += 1
    stack[:, :, c] = _sm(_grad_mag(kept[17]), 1.5); c += 1
    stack[:, :, c] = _sm(_grad_mag(kept[15]), 1.5); c += 1
    coh, theta, _ = _structure_tensor(dem, 2.0)
    stack[:, :, c] = coh; c += 1
    stack[:, :, c] = np.cos(2 * theta); c += 1
    stack[:, :, c] = np.sin(2 * theta); c += 1
    stack[:, :, c] = footprint.astype(np.float32); c += 1
    stack.flush()
    return dict(
        channels=CHANNELS, n_channels=len(CHANNELS), shape=[h, w],
        footprint_px=int(footprint.sum()), path=str(out_path),
    )
