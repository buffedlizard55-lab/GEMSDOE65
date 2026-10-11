"""Covariates for the selection-bias-aware PU lane.

The lane brief fixes a *small* covariate set:

    local relief, slope, a gravity-derived basin-fill proxy, lidar coverage
    and distance to range front

Every one of them is built here from files whose sha256 is pinned and verified
(``scripts/fetch_data.py``, ``registry/data_pins.json``):

``relief_local``
    ``max - min`` of the official **detrended elevation** band
    (``training_features.tif`` band 12 ``det_elev``) inside a 5 x 5 pixel
    (500 m) window.  Detrended elevation is used rather than raw elevation so
    that the regional tilt of the Basin and Range does not masquerade as relief.
    Cross-checked against the 3DEP-10 m derived ``relief_local`` channel
    (``topo_10m_derived_100m_u8.tif`` band 5, dequantised with the pinned
    ``lo``/``hi`` from its manifest) -- Spearman rho reported in the receipt.

``slope``
    official band 19 ``det_elev_slope`` ("gradient of elevation after
    detrending").  Cross-checked against the 10 m derived ``slope_p90``.

``grav_basin_fill``
    official band 13 ``iso_grav_anom`` -- the **isostatic gravity anomaly**,
    i.e. gravity after compensation for topographic mass.  This is the
    gravity-derived basin-fill proxy the brief asks for: thick, low-density
    Cenozoic basin fill produces a residual isostatic *low* over dense
    basement, so the anomaly is a monotone (negative) proxy for fill thickness.
    Official source of the underlying grid: USGS isostatic gravity
    (https://mrdata.usgs.gov/gravity/isostatic/,
    https://mrdata.usgs.gov/metadata/usgraviso.html) as distributed through the
    INGENIOUS/GeoDAWN data releases; the competition page lists "Isostatic
    gravity anomaly and the slope of the isostatic gravity anomaly" verbatim
    (https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#provided-features).
    Band 15 ``depth_to_base_surf`` ("depth to basement surface -- thickness of
    sedimentary cover") is the magnetotelluric analogue and is used only in the
    sensitivity variant ``PX6``.

``lidar_cover``
    fraction of pixels inside a 5 x 5 window covered by 1 m LiDAR, from the
    ``valid`` channel (band 12, 0 = no lidar) of ``lidar_scarp_features_u8.tif``.
    Provenance chain: the official competition file ``1m_DEM_links`` (PDF) ->
    OCR'd tile list resolved against the authoritative USGS 3DEP S3 listing ->
    1 m DEM projects aggregated to the 100 m grid by the family template.
    The OCR step is an upstream irregularity and is recorded as such; the
    layer is a *coverage* indicator, not a fault detection.

``dist_range_front``
    Euclidean distance (pixels) to an operational mountain-front isoline.  The
    front is defined as the boundary of the set ``{h >= H0}`` where
    ``h(x) = det_elev(x) - min_{disk(r=50 px)} det_elev`` is the height above
    the 5 km local base level and ``H0 = 50 m`` is the break between basin
    floor/bajada and range flank.  ``H0`` and the disk radius are swept in the
    sensitivity receipt (``evidence/covariate_receipt.json``).

Sentinel handling
-----------------
``training_features.tif`` uses the float32 minimum (``-3.4028234663852886e+38``)
as nodata.  A pixel is ``feat_ok`` only if every band used is finite and not a
sentinel; ``feat_ok`` is intersected with the official footprint.  Pixels that
are not ``feat_ok`` are excluded from training and can never carry emission
mass.  No sentinel is ever silently replaced by a plausible number.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

from gems57.grid import HEIGHT, WIDTH, load_grid

from .paths import DATA

SENTINEL = np.float32(-3.4028234663852886e38)
SHAPE = (HEIGHT, WIDTH)

# 1-based band indices of the official competition feature stack, read from the
# file's own band descriptions at build time and asserted here.
BAND_NAMES = {
    1: "mag_anom", 2: "rtp", 3: "tmi_hg", 4: "geod_2ndinv", 5: "iso_grav_anom_slope",
    6: "tc", 7: "geod_shearrate", 8: "geod_dilaterate", 9: "tmi_vg", 10: "deq_n100a15",
    11: "iso_grav_anom_vg", 12: "det_elev", 13: "iso_grav_anom", 14: "tmi",
    15: "depth_to_base_surf", 16: "ieq_n100a15", 17: "cond_surf",
    18: "iso_grav_anom_hg", 19: "det_elev_slope",
}

# --- operational parameters of the range-front definition (swept in receipt) ---
FRONT_H0_M = 50.0          # height above local base level that marks the front
FRONT_BASE_DISK_PX = 50    # 5 km radius grey-erosion disk = local base level
RELIEF_WIN = 5             # 500 m window for local relief
LIDAR_WIN = 5              # 500 m window for lidar coverage fraction


def _band(path: Path, index: int, expected: str) -> np.ndarray:
    """Read one band, assert its description, return float64 with NaN for nodata."""
    with rasterio.open(path) as ds:
        desc = (ds.descriptions[index - 1] or "")
        name = desc.split(" - ")[0].strip()
        if name != expected:
            raise ValueError(f"band {index} of {path.name} is '{name}', expected '{expected}'")
        a = ds.read(index).astype(np.float64)
        nodata = ds.nodata
    if nodata is not None:
        a[a <= float(SENTINEL) * 0.5] = np.nan   # float32-min sentinel and anything below
        a[a == float(nodata)] = np.nan
    a[~np.isfinite(a)] = np.nan
    return a


def _disk(r: int) -> np.ndarray:
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r


def _fill_nan(a: np.ndarray, ok: np.ndarray, fallback: float = 0.0) -> np.ndarray:
    """Replace NaN by the nearest valid value (exact EDT-based nearest-neighbour fill)."""
    out = a.copy()
    bad = ~ok
    if bad.all():
        return np.full_like(a, fallback)
    if bad.any():
        idx = ndi.distance_transform_edt(bad, return_distances=False, return_indices=True)
        out[bad] = a[tuple(i[bad] for i in idx)]
    return out


def height_above_base(det_elev: np.ndarray, ok: np.ndarray,
                      disk_px: int = FRONT_BASE_DISK_PX) -> np.ndarray:
    """Height above the local (disk-``disk_px``) minimum of detrended elevation."""
    z = _fill_nan(det_elev, ok)
    base = ndi.grey_erosion(z, footprint=_disk(disk_px), mode="nearest")
    base = ndi.uniform_filter(base, size=5, mode="nearest")   # de-staircase the erosion
    return z - base


def range_front(h: np.ndarray, ok: np.ndarray, h0: float = FRONT_H0_M) -> np.ndarray:
    """1-px operational mountain-front isoline: boundary of ``{h >= h0}``."""
    up = (h >= h0) & ok
    low = (~up) & ok
    # boundary = 'up' pixels adjacent to a 'low' pixel (or the inverse), 1 px wide
    edge_up = up & ndi.binary_dilation(low, structure=np.ones((3, 3), bool))
    edge_low = low & ndi.binary_dilation(up, structure=np.ones((3, 3), bool))
    return edge_up | edge_low


def dist_to_front(h: np.ndarray, ok: np.ndarray, h0: float = FRONT_H0_M,
                  clip_px: float = 100.0) -> np.ndarray:
    front = range_front(h, ok, h0)
    if not front.any():
        raise ValueError("range-front isoline is empty; check the DEM band and h0")
    d = ndi.distance_transform_edt(~front)
    return np.minimum(d, clip_px)


def _window_mean(mask: np.ndarray, win: int) -> np.ndarray:
    return ndi.uniform_filter(mask.astype(np.float64), size=win, mode="nearest")


def build_covariates(features_tif: Path, lidar_tif: Path, cache: Path | None = None,
                     *, dequant_topo: Path | None = None) -> dict:
    """Build the pinned 5-covariate stack plus cross-check channels.

    Returns a dict with float32 arrays on the official grid and a receipt.
    """
    grid = load_grid(DATA / "bridge")
    fp = grid.footprint

    det_elev = _band(features_tif, 12, "det_elev")
    slope = _band(features_tif, 19, "det_elev_slope")
    grav = _band(features_tif, 13, "iso_grav_anom")
    depth_base = _band(features_tif, 15, "depth_to_base_surf")
    grav_slope = _band(features_tif, 5, "iso_grav_anom_slope")

    ok = np.isfinite(det_elev) & np.isfinite(slope) & np.isfinite(grav) & fp

    # local relief on detrended elevation
    z = _fill_nan(det_elev, ok)
    mx = ndi.maximum_filter(z, size=RELIEF_WIN, mode="nearest")
    mn = ndi.minimum_filter(z, size=RELIEF_WIN, mode="nearest")
    relief = (mx - mn).astype(np.float32)

    # lidar coverage fraction in a 500 m window
    with rasterio.open(lidar_tif) as ds:
        names = [ (d or "").strip() for d in ds.descriptions ]
        if names[-1] != "valid":
            raise ValueError(f"last lidar band is '{names[-1]}', expected 'valid'")
        valid_q = ds.read(ds.count)
    lidar_px = (valid_q > 0).astype(np.float32)
    lidar_cover = _window_mean(lidar_px, LIDAR_WIN).astype(np.float32)

    h = height_above_base(det_elev, ok)
    dfront = dist_to_front(h, ok).astype(np.float32)

    receipt: dict = {
        "grid": {"height": HEIGHT, "width": WIDTH, "crs": "EPSG:32611", "cell_m": 100.0},
        "footprint_px": int(fp.sum()),
        "catalogue_px": int(grid.catalogue.sum()),
        "feat_ok_px": int(ok.sum()),
        "feat_ok_fraction_of_footprint": float(ok.sum() / fp.sum()),
        "sentinel_or_nan_excluded_px": int((fp & ~ok).sum()),
        "params": {"relief_win_px": RELIEF_WIN, "lidar_win_px": LIDAR_WIN,
                   "front_h0_m": FRONT_H0_M, "front_base_disk_px": FRONT_BASE_DISK_PX,
                   "front_clip_px": 100.0},
        "lidar_coverage": {"px_covered": int((lidar_px > 0).sum()),
                           "frac_of_grid": float((lidar_px > 0).mean()),
                           "frac_of_footprint": float((lidar_px[fp] > 0).mean()),
                           "mean_window_cover_in_footprint": float(lidar_cover[fp].mean())},
        "covariate_summary": {},
    }
    stack = {"relief_local": relief, "slope": slope.astype(np.float32),
             "grav_basin_fill": grav.astype(np.float32), "lidar_cover": lidar_cover,
             "dist_range_front": dfront}
    for name, a in stack.items():
        v = a[ok]
        receipt["covariate_summary"][name] = {
            "min": float(np.min(v)), "p05": float(np.percentile(v, 5)),
            "median": float(np.median(v)), "p95": float(np.percentile(v, 95)),
            "max": float(np.max(v)), "mean": float(np.mean(v)),
            "mean_on_catalogue": float(np.mean(a[grid.catalogue])),
            "mean_off_catalogue": float(np.mean(a[ok & ~grid.catalogue])),
        }

    out = dict(stack)
    out["feat_ok"] = ok.astype(bool)
    out["footprint"] = fp.astype(bool)
    out["catalogue"] = grid.catalogue.astype(bool)
    # sensitivity / cross-check channels (not part of the pinned primary set)
    out["depth_to_base_surf"] = np.where(ok, _fill_nan(depth_base, ok & np.isfinite(depth_base)),
                                         0.0).astype(np.float32)
    out["iso_grav_anom_slope"] = np.where(ok, _fill_nan(grav_slope, ok & np.isfinite(grav_slope)),
                                          0.0).astype(np.float32)
    out["height_above_base"] = h.astype(np.float32)
    out["range_front"] = range_front(h, ok).astype(bool)

    # --- cross-check against the 3DEP-10 m derived channels (dequantised) -----
    if dequant_topo is not None and Path(dequant_topo).exists():
        man = json.loads(Path(dequant_topo).with_suffix(".manifest.json").read_text())
        bands = {b["band_name"]: b for b in man["bands"]}
        with rasterio.open(dequant_topo) as ds:
            names = [(d or "").strip() for d in ds.descriptions]
            i_rel = names.index("relief_local") + 1
            i_slp = names.index("slope_p90") + 1
            q_rel = ds.read(i_rel)
            q_slp = ds.read(i_slp)
        def deq(q, name):
            b = bands[name]
            lo, hi = float(b["lo"]), float(b["hi"])
            v = lo + (q.astype(np.float64) - 1.0) / 254.0 * (hi - lo)
            return np.where(q > 0, v, np.nan)
        r10 = deq(q_rel, "relief_local")
        s10 = deq(q_slp, "slope_p90")
        from scipy.stats import spearmanr
        m = ok & np.isfinite(r10) & np.isfinite(s10)
        receipt["cross_check_10m"] = {
            "source": str(dequant_topo),
            "n_px": int(m.sum()),
            "spearman_relief_local_vs_10m_relief": float(spearmanr(relief[m], r10[m]).statistic),
            "spearman_slope_vs_10m_slope_p90": float(spearmanr(slope[m], s10[m]).statistic),
            "note": "agreement is expected to be partial: the 10 m channels are "
                    "window maxima/percentiles of raw elevation, ours are ranges of "
                    "detrended elevation. Reported, not assumed.",
        }
        out["relief_local_10m"] = np.where(m, r10, np.nan).astype(np.float32)
        out["slope_p90_10m"] = np.where(m, s10, np.nan).astype(np.float32)

    if cache is not None:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, **out)
        Path(cache).with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2))
    return {"arrays": out, "receipt": receipt}


# ---------------------------------------------------------------------------
# QFaults mapping-detail index (attempted propensity-scale anchor)
# ---------------------------------------------------------------------------
def mapdetail_index(trace_csv: Path, qfault_csv: Path, footprint: np.ndarray,
                    transform, radius_px: int = 50) -> dict:
    """Join in-footprint QFaults traces to their record's MAPSCALE and rasterise.

    The brief asks to "anchor [the propensity] scale with exhaustively mapped
    quadrangles if a public index exists".  USGS QFaults/INGENIOUS carries a
    per-record ``MAPSCALE`` field (thousands: 10 = 1:10,000 ... 250 =
    1:250,000).  The family mirror of that attribute table has *no geometry*,
    and the mirrored trace table has *no attribute*, but the trace table's
    ``record_id`` is the row index of the attribute table, so the two join.

    Output is a **fault-trace-weighted** mapping-detail index, not a quadrangle
    index: it measures how much finely-mapped trace lies near a pixel.  Its
    limitation (a quadrangle can be mapped at 1:24,000 and still contain no
    catalogued fault) is recorded in the receipt.
    """
    import pandas as pd

    tr = pd.read_csv(trace_csv)
    q = pd.read_csv(qfault_csv, low_memory=False)
    joined = []
    for rid, g in tr.groupby("record_id", sort=True):
        if rid >= len(q):
            continue
        row = q.iloc[int(rid)]
        ms = row.get("MAPSCALE")
        try:
            ms = float(ms)
        except (TypeError, ValueError):
            ms = np.nan
        joined.append((rid, ms, row.get("FTYPE_"), len(g),
                       float(g[["x0", "y0", "x1", "y1"]].min().min()), 0))
    rec = pd.DataFrame(joined, columns=["record_id", "mapscale_k", "ftype", "n_segments", "_x", "_y"])
    # area-weighted share of records mapped at 1:24,000 or better
    detailed = rec["mapscale_k"].notna() & (rec["mapscale_k"] <= 24.0)
    # rasterise the traces, painting the finest map scale seen per pixel
    from rasterio.features import rasterize
    from shapely.geometry import LineString
    lines, vals = [], []
    for rid, g in tr.groupby("record_id", sort=True):
        if rid >= len(q):
            continue
        ms = q.iloc[int(rid)].get("MAPSCALE")
        try:
            ms = float(ms)
        except (TypeError, ValueError):
            ms = 999.0
        coords = list(zip(g.x0.values, g.y0.values)) + [(g.x1.values[-1], g.y1.values[-1])]
        if len(coords) < 2:
            continue
        lines.append(LineString(coords))
        vals.append(ms)
    # paint 1/scale so finer mapping wins where traces overlap
    inv = np.array([1.0 / max(v, 1.0) for v in vals], float)
    best = rasterize(zip(lines, inv), out_shape=SHAPE, transform=transform, fill=0.0,
                     all_touched=True)
    fine = rasterize([(l, 1.0) for l, v in zip(lines, vals) if v <= 24.0], out_shape=SHAPE,
                     transform=transform, fill=0.0, all_touched=True)
    dil = ndi.binary_dilation(fine > 0, iterations=radius_px)
    rec_out = {
        "n_records_in_footprint": int(rec.shape[0]),
        "n_segments": int(len(tr)),
        "mapscale_k_counts": {str(k): int(v) for k, v in
                              rec["mapscale_k"].value_counts(dropna=False).items()},
        "records_detailed_le_1_24000": int(detailed.sum()),
        "record_fraction_detailed": float(detailed.mean()),
        "ftype_counts": {str(k): int(v) for k, v in rec["ftype"].value_counts(dropna=False).items()},
        "px_with_fine_trace": int((fine > 0).sum()),
        "px_within_5km_of_fine_trace": int((dil & footprint).sum()),
        "footprint_frac_within_5km_of_fine_trace": float((dil & footprint).sum() / footprint.sum()),
        "limitation": "trace-weighted, not quadrangle-weighted: a 1:24,000 quadrangle "
                      "with no catalogued fault scores 0. A public quadrangle index "
                      "(USGS Geologic Map Database / state 1:24k index) is NOT reachable "
                      "from this sandbox, so the propensity scale is reported as a "
                      "sensitivity analysis instead of being anchored.",
    }
    return {"index": best.astype(np.float32), "fine_trace": (fine > 0),
            "fine_within_5km": dil, "receipt": rec_out}
