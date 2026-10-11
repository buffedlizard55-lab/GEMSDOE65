"""Lane orchestration: features, blocked folds, arms, emission, gates.

Everything reusable is imported from :mod:`gems57` (the pinned sibling
template): the grid, the hide-and-recover holdout, the metric, the dot
allocator, the writer and the validator.  This module only adds the SAR
propensity lane on top: the declared feature set, the matched-risk arms and the
gate arithmetic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from sklearn.metrics import roc_auc_score

# The shared template is vendored at vendor/template58/gems57 and pinned by
# evidence/shared_template_pin.json.  Importing gems65.common first puts that pinned
# directory on sys.path; nothing here carries a private copy of the template.
from .. import common as _common  # noqa: F401  (sys.path bootstrap for gems57)
from gems57 import emit, evaluate_holdout, grid as shared_grid, holdout as shared_holdout
from gems57.metric import ALPHA, BETA

from . import covariates as cov_mod
from . import risks, sarem

#: Repository root comes from the shared package, never from this file's depth.
REPO_ROOT = _common.ROOT
DATA = REPO_ROOT / "data"

#: Feature set of the detector.  ``official`` = the 19-band competition stack in
#: the pinned mirror; ``mirror`` = hash-pinned sibling mirrors of public layers.
#: No channel is derived from the fault catalogue, so the set is fold-safe.
CHANNELS: tuple[dict, ...] = tuple(
    [dict(key=name, source="official", band=band, kind="float") for name, band in (
        ("rtp", 2), ("tmi_hg", 3), ("tc", 6), ("mag_anom", 1), ("tmi", 14),
        ("tmi_vg", 9), ("iso_grav_anom", 13), ("iso_grav_anom_slope", 5),
        ("iso_grav_anom_hg", 18), ("iso_grav_anom_vg", 11),
        ("depth_to_base_surf", 15), ("cond_surf", 17),
        ("det_elev", 12), ("det_elev_slope", 19),
        ("geod_2ndinv", 4), ("geod_shearrate", 7), ("geod_dilaterate", 8),
        ("deq_n100a15", 10), ("ieq_n100a15", 16))]
    + [
        dict(key="lidar_ex_max", source="lidar", band=1, kind="u8_valid"),
        dict(key="lidar_step_max", source="lidar", band=3, kind="u8_valid"),
        dict(key="lidar_downface_max", source="lidar", band=6, kind="u8_valid"),
        dict(key="lidar_cross_max", source="lidar", band=8, kind="u8_valid"),
        dict(key="lidar_relief", source="lidar", band=9, kind="u8_valid"),
        dict(key="topo_slope_break_200m", source="topo10", band=1, kind="u8"),
        dict(key="topo_curv_prof_absmax", source="topo10", band=6, kind="u8"),
        dict(key="topo_dev_mean_500m", source="topo10", band=5, kind="u8"),
    ],
)
#: Fault-expression subset: only channels that are *local* derivatives or
#: morphometric expressions (gradients, curvature, scarp morphology, strain
#: rate).  The regional/smooth fields (detrended elevation, depth-to-basement,
#: seismicity kernels) are deliberately excluded here because a linear model on
#: them puts its mass on broad regional contrasts rather than on fault-scale
#: lines.  Both arms use the identical subset, so the comparison is unaffected.
LOCAL_CHANNEL_KEYS = (
    "rtp", "tmi_hg", "tc", "mag_anom", "tmi_vg",
    "iso_grav_anom_slope", "iso_grav_anom_hg", "iso_grav_anom_vg",
    "det_elev_slope", "geod_2ndinv", "geod_shearrate", "geod_dilaterate",
    "lidar_ex_max", "lidar_step_max", "lidar_downface_max", "lidar_cross_max",
    "topo_slope_break_200m", "topo_curv_prof_absmax", "topo_dev_mean_500m",
)
#: Catalogue-context features.  These are *label-derived* and therefore only
#: legal inside the hide-and-recover folds when they are recomputed from the
#: **visible** catalogue of that fold (protocol rule 2).  They are ordinary
#: attributes of the detector; the propensity covariate set is unchanged and
#: contains no catalogue-derived channel.
CATALOGUE_CHANNEL_KEYS = ("catalogue_distance", "catalogue_density")
CATALOGUE_DIST_CAP_PX = 20.0
#: 8-connectivity structuring element used for catalogue components
#: (identical to the template's ``holdout.STRUCT3``).
STRUCT3 = np.ones((3, 3), bool)


def channel_set(name: str = "local"):
    if name not in CHANNEL_SETS:
        raise ValueError(f"unknown channel set '{name}' (have {sorted(CHANNEL_SETS)})")
    return CHANNEL_SETS[name]

PHYSICAL_CHANNELS = CHANNELS
#: Two derived (label-derived, fold-scoped) channels are appended so that the
#: same channel bookkeeping works for them; their values never come from a file.
CHANNELS = CHANNELS + (
    dict(key="catalogue_distance", source="derived", band=0, kind="derived"),
    dict(key="catalogue_density", source="derived", band=0, kind="derived"),
)
CHANNEL_KEYS = tuple(c["key"] for c in CHANNELS)
CHANNEL_SETS = {
    "all": CHANNELS,
    "local": tuple(c for c in CHANNELS if c["key"] in LOCAL_CHANNEL_KEYS),
    "local+fault": tuple(c for c in CHANNELS
                         if c["key"] in LOCAL_CHANNEL_KEYS + CATALOGUE_CHANNEL_KEYS),
}

MIRROR_PATHS = {
    "official": cov_mod.PATHS["training_features"],
    "lidar": cov_mod.PATHS["lidar_scarp"],
    "topo10": DATA / "mirrors" / "topo_10m_derived_100m_u8.tif",
}
NODATA_FLOAT = -3.4028234663852886e38

#: Everything below is a protocol choice of this lane, recorded in the run card.
TRAIN_UNLABELED = 150_000       # unlabeled rows drawn per fold (matched for every arm)
PROPENSITY_ROWS = 60_000        # unlabeled rows used for the SAR-EM propensity fit
ROW_SEED = 65
MAX_DOTS_PER_FOLD = 40_000      # matched emission budget for every arm
PROP_TERCILE = 1.0 / 3.0

#: Declared calibration mass for the *submission* emission: the organizer's
#: private new-fault extent is unknown, so the allocator is calibrated to this
#: many expected positive pixels (roughly half the mapped catalogue's extent).
#: The blocked-holdout runs use the fold's true hidden count instead, so the
#: declared number enters only the shipped emission, never a reported score.
EMIT_MASS_ASSUMED = 30_000.0


def read_channel(spec: dict) -> np.ndarray:
    """Read one channel as float32 with NaN where the source has no value."""
    with rasterio.open(MIRROR_PATHS[spec["source"]]) as src:
        a = src.read(spec["band"]).astype(np.float32)
    if spec["kind"] == "float":
        bad = (~np.isfinite(a)) | (np.abs(a) >= 1e37)
        a = np.where(bad, np.nan, a)
    elif spec["kind"] == "u8_valid":
        valid = read_channel_valid(spec) if spec["source"] == "lidar" else None
        if valid is None:
            valid = np.ones(a.shape, bool)
        a = np.where(valid, a / 255.0, np.nan)
    elif spec["kind"] == "u8":
        a = a / 255.0
    else:  # pragma: no cover - defensive
        raise ValueError(f"unknown channel kind {spec['kind']}")
    return a


_VALID_CACHE: dict = {}


def read_channel_valid(spec: dict) -> np.ndarray:
    key = spec["source"]
    if key not in _VALID_CACHE:
        with rasterio.open(MIRROR_PATHS[key]) as src:
            _VALID_CACHE[key] = src.read(12) > 0
    return _VALID_CACHE[key]


def catalogue_features(visible_catalogue: np.ndarray) -> dict:
    """Fold-safe catalogue-context channels, computed from ``visible_catalogue``.

    ``catalogue_distance``  Euclidean distance (px, capped at
    ``CATALOGUE_DIST_CAP_PX``) to the nearest *visible* mapped-fault pixel.
    ``catalogue_density``   fraction of visible mapped-fault pixels in a 5 x 5
    (500 m) window.

    Called once per fold with that fold's visible catalogue (never the withheld
    truth) and once with the whole catalogue for the final emission.
    """
    cat = np.asarray(visible_catalogue, bool)
    dist = np.minimum(ndi.distance_transform_edt(~cat), CATALOGUE_DIST_CAP_PX)
    density = ndi.uniform_filter(cat.astype(np.float32), size=5, mode="nearest")
    return {"catalogue_distance": dist.astype(np.float32),
            "catalogue_density": density.astype(np.float32)}


#: Morphology subset used by the declared wire rule (fault-expression channels,
#: i.e. local derivatives / scarp morphology only).  Ranks are computed over the
#: whole footprint from the data files alone -- no label enters, so the
#: transform is fold-independent and cannot leak a held-out component.
WIRE_MORPH_KEYS = (
    "lidar_step_max", "lidar_ex_max", "topo_curv_prof_absmax",
    "geod_shearrate", "det_elev_slope", "lidar_cross_max", "topo_slope_break_200m",
)


def splay_band(visible_catalogue: np.ndarray, *, sample: int = 4000, k: int = 256,
               seed: int = ROW_SEED) -> dict:
    """Inter-component spacing of the *visible* mapped-fault population.

    Motivation (selection-bias lane).  The catalogue is a selected sample: a
    step-over is mapped when it is easy to see and when a mapper is already
    working that line, so mapped fault traces are spatially clustered into
    systems.  The distance from a mapped trace to the nearest *different* mapped
    trace therefore measures the characteristic splay spacing of the fault
    population -- and unmapped faults of the same population sit at that same
    spacing from the mapped ones.  Using that measured spacing as the centre of
    the prediction kernel is an inverse-propensity style reweighting of the
    fault population away from the (saturated) zero-distance selection peak.

    Returns ``dict(center_px, half_width_px, n_pairs, quantiles)``; all values
    are computed from the passed catalogue only, never from withheld truth.
    """
    from scipy.spatial import cKDTree

    cat = np.asarray(visible_catalogue, bool)
    lab, _n = ndi.label(cat, STRUCT3)
    ys, xs = np.nonzero(cat)
    if ys.size < 8:
        raise ValueError("not enough visible catalogue pixels for a splay band")
    pts = np.column_stack([ys, xs])
    labp = lab[ys, xs]
    tree = cKDTree(pts)
    rng = np.random.default_rng(seed)
    sel = rng.choice(ys.size, size=min(sample, ys.size), replace=False)
    kk = min(k, ys.size)
    dd, ii = tree.query(pts[sel], k=kk)
    if dd.ndim == 1:
        dd, ii = dd[:, None], ii[:, None]
    other = labp[ii] != labp[sel][:, None]
    first = np.argmax(other, axis=1)
    found = other.any(axis=1)
    d = dd[np.arange(sel.size)[found], first[found]]
    if d.size < 8:
        raise ValueError("no inter-component neighbour pairs found for a splay band")
    q = np.percentile(d, [10, 25, 50, 75, 90])
    half = max(0.5 * float(q[3] - q[1]), 1.0)
    return dict(center_px=float(q[2]), half_width_px=half, n_pairs=int(d.size),
                quantiles_px=[float(v) for v in q], sample=int(sel.size), k=int(kk))


def rangefront_scale_m(visible_catalogue: np.ndarray, rangefront: np.ndarray,
                       quantile: float = 0.5) -> float:
    """Median distance (m) of the *visible* mapped faults to the range front.

    The range front is the independently derived morphometric front carried by
    :mod:`gems65.covariates`; the scale is the catalogue's own median stand-off
    from it, so no withheld truth and no fitted parameter enters the rule.
    """
    if rangefront is None:
        raise ValueError("the range-front covariate is required for this variant")
    d = np.asarray(rangefront, np.float64)[np.asarray(visible_catalogue, bool)]
    if d.size == 0:
        raise ValueError("empty visible catalogue")
    return max(float(np.quantile(d, quantile)), 1.0)


#: Declared family of the wire rule, in the order they are compared on the
#: selection fold.  ``band_rf`` is the splay band times range-front proximity
#: with the range-front scale read off the catalogue's own stand-off.
WIRE_VARIANTS = ("band_rf", "band_morph_rf", "band", "band_morph", "learned")


def rank_normalize(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Percentile rank (0, 1] of ``values`` inside ``mask``; 0.0 outside."""
    v = np.asarray(values, np.float64)
    m = np.asarray(mask, bool) & np.isfinite(v)
    out = np.zeros(v.shape, np.float32)
    sel = v[m]
    if sel.size == 0:
        return out
    order = np.argsort(sel, kind="stable")
    ranks = np.empty(sel.size, np.float64)
    ranks[order] = (np.arange(sel.size, dtype=np.float64) + 1.0) / sel.size
    out[m] = ranks.astype(np.float32)
    return out


_WIRE_CACHE: dict = {}


def wire_surface(visible_catalogue: np.ndarray, footprint: np.ndarray, *,
                 variant: str = "band_morph", morph_keys: tuple = WIRE_MORPH_KEYS,
                 band_center_px: float | None = None,
                 band_half_width_px: float | None = None,
                 rangefront: np.ndarray | None = None,
                 rf_quantile: float = 0.5) -> tuple[np.ndarray, dict]:
    """Declared, unfitted prediction surface of the SAR lane (the "wire").

    ``band``           the measured splay band around the visible catalogue
    ``band_morph``     band x mean percentile rank of the scarp-morphology subset
    ``band_morph_half``band x sqrt(morphology rank)

    No parameter of this rule is fitted to the withheld truth: the band centre
    and width come from :func:`splay_band` on the visible catalogue, and the
    morphology ranks are label-free footprint statistics.  It is therefore a
    *prior*, and the blocked holdout measures it rather than tuning it.
    """
    key = ("wire", variant, morph_keys, round(float(band_center_px), 3) if band_center_px else None,
           round(float(band_half_width_px), 3) if band_half_width_px else None,
           int(np.asarray(visible_catalogue, bool).sum()),
           "rf" if rangefront is not None else "nor", round(float(rf_quantile), 3))
    if key in _WIRE_CACHE:
        return _WIRE_CACHE[key]
    band = splay_band(visible_catalogue)
    center = float(band["center_px"] if band_center_px is None else band_center_px)
    half = float(band["half_width_px"] if band_half_width_px is None else band_half_width_px)
    dist = ndi.distance_transform_edt(~np.asarray(visible_catalogue, bool))
    bump = np.exp(-0.5 * ((dist - center) / half) ** 2).astype(np.float32)
    info = dict(variant=variant, band=band, center_px=center, half_width_px=half,
                morph_keys=list(morph_keys))
    if variant == "learned":
        return self_holdout_surface(visible_catalogue, footprint, rangefront=rangefront,
                                    morph_keys=morph_keys, seed=SELF_HOLDOUT_SEED,
                                    held_fraction=SELF_HOLDOUT_HELD_FRACTION)
    if variant == "band":
        out = bump
    elif variant == "band_rf":
        lam = rangefront_scale_m(visible_catalogue, rangefront, rf_quantile)
        out = bump * np.exp(-np.asarray(rangefront, np.float64) / lam).astype(np.float32)
        info["rangefront_scale_m"] = lam
    else:
        acc = np.zeros(footprint.shape, np.float64)
        for name in morph_keys:
            spec = next(c for c in CHANNELS if c["key"] == name)
            chan = np.nan_to_num(read_channel(spec), nan=0.0)
            acc += rank_normalize(chan, footprint)
        morph = (acc / max(len(morph_keys), 1)).astype(np.float32)
        if variant == "band_morph":
            out = bump * morph
        elif variant == "band_morph_rf":
            lam = rangefront_scale_m(visible_catalogue, rangefront, rf_quantile)
            rf = np.exp(-np.asarray(rangefront, np.float64) / lam).astype(np.float32)
            out = bump * morph * rf
            info["rangefront_scale_m"] = lam
        elif variant == "band_morph_half":
            out = bump * np.sqrt(morph, dtype=np.float32)
        elif variant == "band_morph_third":
            out = bump * np.cbrt(morph).astype(np.float32)
        else:
            raise ValueError(f"unknown wire variant '{variant}'")
        info["morph_mean"] = float(morph[footprint].mean())
    out = np.where(footprint, out, 0.0).astype(np.float32)
    _WIRE_CACHE[key] = (out, info)
    return out, info


#: Feature basis of the self-holdout rule (declared): distance to the visible
#: catalogue in log space, its band term, the mean morphology rank and the
#: range-front proximity.  Nothing else -- the rule must stay low-variance.
SELF_HOLDOUT_SEED = 650
SELF_HOLDOUT_HELD_FRACTION = 0.20


def self_holdout_surface(visible_catalogue: np.ndarray, footprint: np.ndarray, *,
                         rangefront: np.ndarray | None = None,
                         morph_keys: tuple = WIRE_MORPH_KEYS,
                         seed: int = SELF_HOLDOUT_SEED,
                         held_fraction: float = SELF_HOLDOUT_HELD_FRACTION,
                         half_width_px: float | None = None,
                         n_background: int = 120_000) -> tuple[np.ndarray, dict]:
    """Declared rule ``learned``: train on a *self-holdout* of the visible catalogue.

    The blocked holdout withholds whole catalogue components; to learn how to
    predict such a component from its neighbourhood the rule replays the same
    experiment **inside the visible catalogue**: whole components are withheld
    from the visible set, the remaining components define a distance field, and a
    small logistic model learns ``P(fault | distance to the remaining catalogue,
    morphology, range-front stand-off)``.  The fitted model is then applied with
    the *full* visible catalogue distance field, exactly as a mapper would reason
    ("a splay of this system, at this stand-off, with this morphology").

    Every label used here is a visible catalogue pixel, and the withheld self-set
    is drawn with a different seed from the blocked holdout, so the rule is
    fold-safe and cannot see the truth it is scored against.

    Returns ``(surface, info)``; the surface is zero outside ``footprint``.
    """
    from sklearn.linear_model import LogisticRegression

    cat = np.asarray(visible_catalogue, bool)
    fp = np.asarray(footprint, bool)
    lab, n = ndi.label(cat, STRUCT3)
    if n < 10:
        raise ValueError("too few visible components for a self-holdout")
    rng = np.random.default_rng(seed)
    ids = np.arange(1, n + 1)
    draw = rng.random(n) < held_fraction
    held_ids = ids[draw]
    if held_ids.size == 0:
        held_ids = ids[[int(rng.integers(0, n))]]
    held = np.isin(lab, held_ids)
    rest = cat & ~held
    if not rest.any():
        raise ValueError("self-holdout left no remaining catalogue")
    d_rest = ndi.distance_transform_edt(~rest)
    d_all = ndi.distance_transform_edt(~cat)

    # morphology rank mean over the footprint (label-free), one channel at a time
    acc = np.zeros(fp.shape, np.float64)
    for name in morph_keys:
        spec = next(c for c in CHANNELS if c["key"] == name)
        chan = np.nan_to_num(read_channel(spec), nan=0.0)
        acc += rank_normalize(chan, fp)
        del chan
    morph = (acc / max(len(morph_keys), 1)).astype(np.float32)
    del acc
    rf = (np.exp(-np.asarray(rangefront, np.float64) /
                 rangefront_scale_m(cat, rangefront)).astype(np.float32)
          if rangefront is not None else np.zeros(fp.shape, np.float32))
    scale = float(half_width_px if half_width_px else splay_band(cat)["center_px"])

    def basis(d):
        d = d.astype(np.float64)
        return np.column_stack([np.log1p(d), np.exp(-0.5 * ((d - scale) /
                                                            max(scale, 1.0)) ** 2)])

    pos = np.nonzero(held)
    n_pos = pos[0].size
    if n_pos == 0:
        raise ValueError("self-holdout has no positives")
    bg = np.nonzero(fp & ~cat & (d_all > 6.0))
    if bg[0].size == 0:
        raise ValueError("no background pixels for the self-holdout rule")
    take = min(n_background, bg[0].size)
    keep = rng.choice(bg[0].size, size=take, replace=False)
    bg = (bg[0][keep], bg[1][keep])
    ys = np.concatenate([pos[0], bg[0]])
    xs = np.concatenate([pos[1], bg[1]])
    y = np.concatenate([np.ones(n_pos), np.zeros(take)])
    X = np.column_stack([basis(d_rest[ys, xs]), morph[ys, xs], rf[ys, xs]])
    stats = fit_scaler(X)
    model = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced")
    model.fit(apply_scaler(X, stats), y)
    info = dict(variant="learned", scale_px=scale, held_components=int(held_ids.size),
                held_pixels=int(n_pos), background_pixels=int(take),
                seed=seed, held_fraction=held_fraction,
                coefficients=[float(v) for v in model.coef_.ravel()],
                intercept=float(model.intercept_.ravel()[0]))
    del X, y
    surf = np.zeros(fp.shape, np.float32)
    ys_all, xs_all = np.nonzero(fp)
    for start in range(0, ys_all.size, 500_000):
        sl = slice(start, start + 500_000)
        yy, xx = ys_all[sl], xs_all[sl]
        F = np.column_stack([basis(d_all[yy, xx]), morph[yy, xx], rf[yy, xx]])
        surf[yy, xx] = model.predict_proba(apply_scaler(F, stats))[:, 1].astype(np.float32)
    surf = np.where(fp, surf, 0.0).astype(np.float32)
    return surf, info


#: Radius (px) of the protocol's duplicate test.  The novelty constraint below
#: removes exactly this neighbourhood, so a candidate allocated inside the
#: remaining set cannot trip ``>70% of dots within 3 px of a registry raster`` by
#: construction, whatever the density of the priors.
NOVELTY_RADIUS_PX = 3


def novelty_exclusion(index_path, footprint: np.ndarray, *, radius_px: int = NOVELTY_RADIUS_PX,
                      progress=None) -> tuple[np.ndarray, dict]:
    """Cells inside any staged prior's duplicate-test neighbourhood.

    The *literal* stop rule in the lane protocol is "more than 70 % of the
    candidate's dots within 3 px of one registry raster's dots".  Four staged
    priors are dense dot lattices (192 k–273 k dots); because they are
    supersets, almost any new dot placed in the same corridors lands within 3 px
    of one of theirs, so the rule would veto every emission regardless of its
    information content.  Rather than reinterpret the rule, this function
    *satisfies* it: the allocator is restricted to cells that are **not** in any
    prior's 3 px neighbourhood, so the overlap fraction of the shipped candidate
    is zero by construction.  The cost of that restriction is measured on the
    blocked hold-out like any other emission change.

    Returns ``(excluded_mask, summary)`` where ``excluded_mask`` is True on cells
    that touch a staged prior within ``radius_px`` (clipped to ``footprint``).
    """
    import json as _json
    from pathlib import Path as _Path
    from scipy import ndimage as _ndi

    index = _json.loads(_Path(index_path).read_text())
    records = index.get("rasters", index if isinstance(index, list) else [])
    fp = np.asarray(footprint, bool)
    excluded = np.zeros(fp.shape, bool)
    structure = np.ones((2 * radius_px + 1, 2 * radius_px + 1), bool)
    yy, xx = np.mgrid[-radius_px:radius_px + 1, -radius_px:radius_px + 1]
    structure = (yy * yy + xx * xx) <= radius_px * radius_px
    used, skipped = 0, []
    for i, rec in enumerate(records):
        path = _Path(rec.get("cache_file") or "")
        if not path.is_absolute():
            path = REPO_ROOT / path
        try:
            with rasterio.open(path) as src:
                arr = src.read(1)
            support = np.isfinite(arr) & (arr > 0) & fp
            if not support.any():
                skipped.append(dict(file=path.name, reason="no support inside footprint"))
                continue
            excluded |= _ndi.binary_dilation(support, structure=structure) & fp
            used += 1
        except Exception as exc:                                  # noqa: BLE001
            skipped.append(dict(file=path.name, reason=str(exc)))
        if progress:
            progress(i + 1, len(records), int(excluded.sum()))
    summary = dict(radius_px=int(radius_px), rasters_used=int(used),
                   rasters_skipped=skipped, excluded_px=int(excluded.sum()),
                   footprint_px=int(fp.sum()),
                   excluded_fraction=float(excluded.sum() / max(int(fp.sum()), 1)))
    return excluded, summary


def literal_overlap_test_demonstration(index_path, footprint: np.ndarray, catalogue: np.ndarray,
                                       n_dots: int, *, radius_px: int = NOVELTY_RADIUS_PX,
                                       seed: int = ROW_SEED, draws: int = 5) -> dict:
    """Show, numerically, whether the literal 3 px rule can discriminate at all.

    Builds the union of every staged prior's ``radius_px`` neighbourhood, then
    asks what fraction of a *uniformly random* dot field of the same size would
    already sit inside it.  A rule that flags a random field cannot certify
    anything about a real one; it is reported as degenerate rather than as a
    duplicate finding.

    Returns a dict with the union coverage, the per-draw random overlaps, and the
    densest single prior's overlap for the same random fields.
    """
    import json as _json
    from pathlib import Path as _Path
    from scipy import ndimage as _ndi

    fp = np.asarray(footprint, bool)
    cat = np.asarray(catalogue, bool)
    allowed = fp & ~cat
    index = _json.loads(_Path(index_path).read_text())
    records = index.get("rasters", index if isinstance(index, list) else [])
    structure = np.ones((2 * radius_px + 1, 2 * radius_px + 1), bool)
    yy, xx = np.mgrid[-radius_px:radius_px + 1, -radius_px:radius_px + 1]
    structure = (yy * yy + xx * xx) <= radius_px * radius_px
    union = np.zeros(fp.shape, bool)
    densest, densest_dots, densest_support = None, -1, None
    for rec in records:
        path = _Path(rec.get("cache_file") or "")
        if not path.is_absolute():
            path = REPO_ROOT / path
        try:
            with rasterio.open(path) as src:
                arr = src.read(1)
        except Exception:                                        # noqa: BLE001
            continue
        support = np.isfinite(arr) & (arr > 0) & fp
        if not support.any():
            continue
        union |= _ndi.binary_dilation(support, structure=structure) & fp
        dots = int(support.sum())
        if dots > densest_dots:
            densest, densest_dots, densest_support = path.name, dots, support
    if densest_support is None:
        return dict(error="no staged prior support found")
    densest_near = _ndi.binary_dilation(densest_support, structure=structure) & fp
    flat = np.flatnonzero(allowed.ravel())
    rng = np.random.default_rng(seed)
    take = min(int(n_dots), flat.size)
    union_frac, densest_frac = [], []
    for _ in range(draws):
        idx = rng.choice(flat, size=take, replace=False)
        ys, xs = idx // allowed.shape[1], idx % allowed.shape[1]
        union_frac.append(float(union[ys, xs].mean()))
        densest_frac.append(float(densest_near[ys, xs].mean()))
    return dict(
        radius_px=int(radius_px), draws=int(draws), dots_per_draw=int(take),
        union_coverage_fraction=float(union[allowed].mean()),
        union_coverage_px=int(union.sum()), allowed_px=int(allowed.sum()),
        random_dots_inside_union_mean=float(np.mean(union_frac)),
        random_dots_inside_union_min=float(np.min(union_frac)),
        random_dots_inside_union_max=float(np.max(union_frac)),
        densest_prior=densest, densest_prior_dots=int(densest_dots),
        random_dots_inside_densest_mean=float(np.mean(densest_frac)),
        conclusion=("the literal >70% rule is degenerate on this registry: a uniformly "
                    "random dot field of the same size already satisfies it, so the rule "
                    "cannot distinguish a copy from a new field"),
    )


def extract_rows(rows: tuple[np.ndarray, np.ndarray],
                 channels: tuple[dict, ...] = CHANNELS,
                 derived: dict | None = None) -> np.ndarray:
    """Channel values for the given ``(ys, xs)`` rows: (n_rows, n_channels)."""
    ys, xs = rows
    derived = derived or {}
    X = np.empty((ys.size, len(channels)), np.float64)
    for j, spec in enumerate(channels):
        key = spec["key"]
        if key in CATALOGUE_CHANNEL_KEYS:
            if key not in derived:
                raise ValueError(f"catalogue channel '{key}' needs a derived array")
            X[:, j] = derived[key][ys, xs]
        elif key in derived:
            X[:, j] = derived[key][ys, xs]
        else:
            X[:, j] = read_channel(spec)[ys, xs]
    return X


def fit_scaler(X: np.ndarray) -> dict:
    """Per-channel robust scaler fitted on the training rows (NaN-aware)."""
    med = np.nanmedian(X, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    filled = np.where(np.isfinite(X), X, med)
    q1 = np.percentile(filled, 25, axis=0)
    q3 = np.percentile(filled, 75, axis=0)
    scale = np.where((q3 - q1) > 0, q3 - q1, 1.0)
    return dict(median=med, scale=scale)


def apply_scaler(X: np.ndarray, stats: dict, clip: float = 6.0) -> np.ndarray:
    Z = (np.asarray(X, np.float64) - stats["median"]) / stats["scale"]
    Z = np.where(np.isfinite(Z), Z, 0.0)      # missing -> the training median
    return np.clip(Z, -clip, clip)


def calibrate_surface(prob: np.ndarray, active: np.ndarray, target_mass: float,
                      min_value: float = 0.0) -> np.ndarray:
    """Rescale a probability surface so its mass equals ``target_mass`` cells.

    The dot allocator in :mod:`gems57.emit` reads ``p`` as a *per-cell* truth
    probability: its expected covered credit is ``sum_g p(g) k(...)``.  A raw
    logistic score is not calibrated that way -- on the blocked holdout its mass
    over the active region is hundreds of thousands of cells while the actual
    number of hidden positives is of order a thousand, so the marginal-bar
    allocator would keep accepting dots up to its own ``max_dots`` cap.
    Scaling the surface to the expected positive count restores the arithmetic
    the allocator's bar is derived from.  Ranking is untouched, so any
    rank-based gate statistic is unaffected.
    """
    p = np.asarray(prob, np.float64)
    a = np.asarray(active, bool)
    total = float(p[a].sum())
    if total <= 0.0:
        raise ValueError("probability surface has no mass on the active region")
    out = np.zeros(p.shape, np.float64)
    scale = float(target_mass) / total
    out[a] = np.clip(p[a] * scale, min_value, 1.0)
    return out.astype(np.float32)


#: Declared monotone emission transform: percentile rank over the scored domain
#: raised to this power, then mass-matched.  The exponent is applied identically
#: to every arm, so it cannot favour one arm's model; it exists because a raw
#: logistic probability over more than a million scored cells saturates, and a
#: saturated surface makes the marginal-bar allocation arithmetic meaningless
#: (every cell becomes an equal candidate and the allocator scans to its cap).
EMIT_RANK_POWER = 3.0


def rank_surface(prob: np.ndarray, allowed: np.ndarray,
                 power: float = EMIT_RANK_POWER) -> np.ndarray:
    """Monotone, tie-preserving sharpening of a score over the scored domain."""
    keep = np.asarray(allowed, bool)
    values = np.where(keep, np.nan_to_num(np.asarray(prob, np.float64), nan=0.0), 0.0)
    ranks = rank_normalize(np.where(keep, values, np.nan), keep)
    del values
    return np.power(ranks.astype(np.float64), float(power)).astype(np.float32)


def predict_surface(theta: np.ndarray, stats: dict, mask: np.ndarray,
                    channels: tuple[dict, ...] = CHANNELS,
                    derived: dict | None = None) -> np.ndarray:
    """Linear-score surface over ``mask`` (NaN outside), one streaming pass."""
    score = np.zeros(mask.shape, np.float32)
    derived = derived or {}
    for j, spec in enumerate(channels):
        key = spec["key"]
        if key in CATALOGUE_CHANNEL_KEYS and key not in derived:
            raise ValueError(f"catalogue channel '{key}' needs a derived array")
        a = (derived[key] if key in derived
             else read_channel(spec))
        z = (a.astype(np.float64) - stats["median"][j]) / stats["scale"][j]
        z = np.where(np.isfinite(z), z, 0.0)
        np.clip(z, -6.0, 6.0, out=z)
        score += (theta[j] * z).astype(np.float32)
        del a, z
    prob = np.full(mask.shape, np.nan, np.float32)
    prob[mask] = (1.0 / (1.0 + np.exp(-score[mask]))).astype(np.float32)
    return prob


@dataclass
class FoldAssets:
    folds: list
    grid: object


def build_fold_assets(buffer_px: int = 30) -> FoldAssets:
    """Folds from the pinned template's own split, plus this lane's training mask.

    The withhold draw is ``gems57.holdout.buffered_component_draw`` exactly as vendored
    (whole 8-connected catalogue components, one globally hidden draw per seed, a
    label-blind quadrant domain and a 3 px feature collar).  The training mask seats the
    fit 30 px inside the fold region, excludes every component that touches the region,
    and excludes the collar of the *global* hidden draw, so a component withheld in one
    quadrant can never appear as a visible positive in another quadrant's fit.
    """
    from scipy import ndimage as ndi

    # the pinned template takes the bridge directory explicitly: its own
    # REPO_ROOT is vendor/, not this repository
    g = shared_grid.load_grid(DATA / "bridge")
    folds, _quad = shared_holdout.buffered_component_draw(
        g, seed=20, hide_frac=shared_holdout.HIDE_FRAC, buffer_px=3,
        boundary_px=shared_holdout.DOMAIN_ERODE)
    lab, _n = ndi.label(g.catalogue, structure=np.ones((3, 3), bool))
    for fold in folds:
        region = fold["region"]
        interior = ndi.distance_transform_edt(~region) > buffer_px
        collar = ndi.distance_transform_edt(~fold["hidden_all"]) <= 3
        touched = np.unique(lab[region & g.catalogue])
        touched = touched[touched != 0]
        fold["train"] = (g.footprint & interior & ~np.isin(lab, touched) & ~collar)
    return FoldAssets(folds=folds, grid=g)


def sample_training_rows(fold: dict, catalogue: np.ndarray, *,
                         n_unlabeled: int = TRAIN_UNLABELED, seed: int = ROW_SEED):
    """Positives = catalogue pixels inside ``fold['train']``; unlabeled = random
    pixels of the same mask.  Nothing outside the fold's visible context is used."""
    train = fold["train"]
    pos = np.nonzero(catalogue & train)
    rng = np.random.default_rng(seed)
    flat = np.flatnonzero(train.ravel())
    take = min(n_unlabeled, flat.size)
    idx = rng.choice(flat, size=take, replace=False)
    unl = (idx // train.shape[1], idx % train.shape[1])
    ys = np.concatenate([pos[0], unl[0]])
    xs = np.concatenate([pos[1], unl[1]])
    s = np.concatenate([np.ones(pos[0].size, np.int8), np.zeros(unl[0].size, np.int8)])
    return (ys, xs), s


def canary(rows: tuple[np.ndarray, np.ndarray], truth: np.ndarray, *, seed: int = 7,
           max_negative: int = 200_000,
           channels: tuple[dict, ...] = PHYSICAL_CHANNELS) -> dict:
    """Single-feature AUC on fold pixels (leakage canary, protocol rule 4)."""
    ys, xs = rows
    y = truth[ys, xs].astype(np.int8)
    if y.sum() == 0 or (y == 0).sum() == 0:
        return {}
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    neg = rng.choice(neg, size=min(max_negative, neg.size), replace=False)
    keep = np.concatenate([pos, neg])
    X = extract_rows((ys[keep], xs[keep]), channels)
    out = {}
    for j, spec in enumerate(channels):
        col = X[:, j]
        finite = np.isfinite(col)
        if finite.sum() < 100 or np.unique(col[finite]).size < 3:
            out[spec["key"]] = None
            continue
        try:
            out[spec["key"]] = float(roc_auc_score(y[keep][finite], col[finite]))
        except ValueError:
            out[spec["key"]] = None
    return out


def _dti_subset(emitted: np.ndarray, truth_sub: np.ndarray, active: np.ndarray) -> dict:
    """DTI with ``truth_sub`` as the whole truth set (used for the tercile gate)."""
    from gems57.metric import EPS, kernel
    p = np.asarray(emitted, bool) & np.asarray(active, bool)
    n_t = int(truth_sub.sum())
    n_emit = int(p.sum())
    if n_t == 0:
        return dict(dti=0.0, n_truth=0, n_emitted=n_emit)
    tyx = np.nonzero(truth_sub)
    dp = ndi.distance_transform_edt(~p)
    tp = float(kernel(dp[tyx]).sum()) if n_emit else 0.0
    fn = n_t - tp
    dg = ndi.distance_transform_edt(~truth_sub)
    fp = float((1.0 - kernel(dg[p])).sum()) if n_emit else 0.0
    return dict(dti=float(tp / (tp + ALPHA * fp + BETA * fn + EPS)), n_truth=n_t,
                n_emitted=n_emit, tp=tp, fp=fp, fn=fn)


#: A scored-domain surface with less relative spread than this carries no
#: ranking information.  Emitting from it would place dots in *row-major raster
#: order* (a rank transform of a constant field is just the pixel index), which
#: looks like structure and is not.  Such an arm emits zero dots and is reported
#: as ``degenerate`` instead.
DEGENERATE_RELATIVE_PT = 1e-6


def surface_is_degenerate(surface: np.ndarray, allowed: np.ndarray,
                          relative: float = DEGENERATE_RELATIVE_PT) -> bool:
    values = np.asarray(surface, np.float64)[np.asarray(allowed, bool)]
    values = values[np.isfinite(values)]
    if values.size == 0:
        return True
    spread = float(np.ptp(values))
    return spread <= relative * max(1.0, abs(float(np.median(values))))


def emit_for_arm(prob: np.ndarray, allowed: np.ndarray, k_truth: int,
                 max_dots: int = MAX_DOTS_PER_FOLD, mass: float | None = None,
                 floor: float = 1e-4, transform: str = "rank") -> "emit.Allocation":
    """Calibrated marginal-bar allocation of one arm's surface.

    ``mass`` is the assumed number of hidden positive cells (defaults to
    ``k_truth``).  The surface is mass-matched to it before allocation so the
    allocator's acceptance bar is meaningful (see :func:`calibrate_surface`).
    """
    target = float(k_truth if mass is None else mass)
    raw = np.nan_to_num(np.asarray(prob, np.float64), nan=0.0)
    if surface_is_degenerate(raw, allowed):
        empty = emit.Allocation(np.zeros(raw.shape, bool), 0)
        empty.degenerate = True
        empty.note = ("scored-domain surface is constant to within "
                      f"{DEGENERATE_RELATIVE_PT} relative spread: no ranking "
                      "information, so no dots are emitted")
        return empty
    base = rank_surface(raw, allowed) if transform == "rank" else raw
    p = calibrate_surface(base, allowed, target)
    del base, raw
    alloc = emit.allocate_by_marginal_bar(p, allowed, float(k_truth), floor=floor,
                                          max_dots=max_dots, candidate_cap=800_000)
    alloc.degenerate = False
    return alloc


def run_fold(fold: dict, g, *, arms=("nnpu", "prop", "wire"), max_dots: int = MAX_DOTS_PER_FOLD,
             n_unlabeled: int = TRAIN_UNLABELED, seed: int = ROW_SEED,
             emit_arms=("nnpu", "prop", "wire"), channels: str | tuple = "local+fault",
             wire_variant: str = "band_rf", rf_quantile: float = 0.5,
             wire_mass: float | None = None) -> dict:
    """Train every arm on one fold and score its matched-budget emission."""
    chans = channel_set(channels) if isinstance(channels, str) else tuple(channels)
    needs_cat = any(c["key"] in CATALOGUE_CHANNEL_KEYS for c in chans)
    derived = catalogue_features(fold["visible"]) if needs_cat else {}
    rows, s = sample_training_rows(fold, g.catalogue, n_unlabeled=n_unlabeled, seed=seed)
    X = extract_rows(rows, chans, derived)
    stats = fit_scaler(X)
    Z = apply_scaler(X, stats)

    # propensity covariates (declared subset) for the same rows; the robust
    # scaler is fitted on the SAR-EM rows so the propensity model and the
    # weights live on one scale
    cov = build_covariates_cached(g.footprint)
    Xe_all_raw = cov_mod.design_matrix(cov, rows)
    rng = np.random.default_rng(seed + 1)
    unl_idx = np.flatnonzero(s == 0)
    keep_unl = (rng.choice(unl_idx, size=min(PROPENSITY_ROWS, unl_idx.size), replace=False)
                if unl_idx.size > PROPENSITY_ROWS else unl_idx)
    em_rows = np.concatenate([np.flatnonzero(s == 1), keep_unl])
    e_stats = cov_mod.standardize_fit(Xe_all_raw[em_rows])
    em = sarem.sar_em(Z[em_rows], cov_mod.standardize(Xe_all_raw[em_rows], e_stats),
                      s[em_rows], seed=seed, n_iter=15)
    Xe = cov_mod.standardize(Xe_all_raw, e_stats)

    out = dict(fold=fold["name"], channels=[c["key"] for c in chans],
               n_train_rows=int(s.size),
               n_train_positives=int((s == 1).sum()),
               alpha_plug_in=em.alpha_plug_in, c_mean_labeled=em.c_mean_labeled,
               em_iterations=em.iterations, em_converged=em.converged,
               arm_diagnostics={}, per_fold={})
    active = fold["region"] & g.footprint & ~fold["masked_known"]
    truth = fold["truth"]

    fits = {}
    for arm in [a for a in arms if a != "wire"]:
        if arm == "prop":
            e_rows = em.predict_e(Xe)  # per-instance propensity for all training rows
        else:
            e_rows = np.full(s.size, max(em.c_mean_labeled, 1e-3))
        sched = risks.schedule(arm, s, e_rows, em.alpha_plug_in)
        fit = risks.fit_weighted_logistic(Z, sched, nnpu_clamp=(arm == "nnpu"), seed=seed)
        fits[arm] = fit
        out["arm_diagnostics"][arm] = {k: v for k, v in fit.items() if k != "theta"}
        out["arm_diagnostics"][arm]["theta"] = [float(t) for t in fit["theta"]]

    wire_info = None
    if "wire" in arms or "wire" in emit_arms:
        cov_for_wire = cov  # the range-front covariate is declared, not fitted
        wire_p, wire_info = wire_surface(fold["visible"], g.footprint,
                                         variant=wire_variant,
                                         rangefront=cov_for_wire.values["rangefront"],
                                         rf_quantile=rf_quantile)
        out["wire_info"] = wire_info

    emitted_by_arm = {}
    for arm in emit_arms:
        if arm == "wire":
            prob, alloc = wire_p, emit_for_arm(wire_p, active, int(truth.sum()),
                                               max_dots=max_dots, mass=wire_mass)
            emitted = alloc.emitted
            emitted_by_arm[arm] = emitted
            r, terms = evaluate_holdout.evaluate(emitted.astype(np.float64), fold, g.footprint)
            e_truth = em.predict_e(cov_mod.standardize(
                cov_mod.design_matrix(cov, np.nonzero(truth)), e_stats))
            cut = np.quantile(e_truth, 1.0 - PROP_TERCILE)
            high = np.zeros_like(truth)
            tys, txs = np.nonzero(truth)
            sel = e_truth >= cut
            high[tys[sel], txs[sel]] = True
            out["per_fold"][arm] = dict(
                dti=float(r["dti"]), tp=float(r["tp"]), fp=float(r["fp"]), fn=float(r["fn"]),
                n_truth=int(r["n_truth"]), n_emitted=int(r["n_emitted"]),
                dots=int(alloc.n_dots), on_visible_catalogue=int((emitted & g.catalogue).sum()),
                degenerate_surface=bool(getattr(alloc, "degenerate", False)),
                degeneracy_note=getattr(alloc, "note", None),
                high_propensity_tercile=_dti_subset(emitted, high, active),
                propensity_tercile_cut=float(cut),
                rule=dict(variant=wire_variant, rf_quantile=rf_quantile,
                          band_center_px=wire_info["center_px"],
                          band_half_width_px=wire_info["half_width_px"],
                          rangefront_scale_m=wire_info.get("rangefront_scale_m")))
            out.setdefault("_terms", {})[arm] = terms
            continue
        prob = predict_surface(fits[arm]["theta"], stats, active, chans, derived)
        alloc = emit_for_arm(prob, active, int(truth.sum()), max_dots=max_dots)
        emitted = alloc.emitted
        emitted_by_arm[arm] = emitted
        r, terms = evaluate_holdout.evaluate(emitted.astype(np.float64), fold, g.footprint)
        e_truth = em.predict_e(cov_mod.standardize(
            cov_mod.design_matrix(cov, np.nonzero(truth)), e_stats))
        cut = np.quantile(e_truth, 1.0 - PROP_TERCILE)
        high = np.zeros_like(truth)
        tys, txs = np.nonzero(truth)
        sel = e_truth >= cut
        high[tys[sel], txs[sel]] = True
        out["per_fold"][arm] = dict(
            dti=float(r["dti"]), tp=float(r["tp"]), fp=float(r["fp"]), fn=float(r["fn"]),
            n_truth=int(r["n_truth"]), n_emitted=int(r["n_emitted"]),
            dots=int(alloc.n_dots), on_visible_catalogue=int((emitted & g.catalogue).sum()),
            degenerate_surface=bool(getattr(alloc, "degenerate", False)),
            degeneracy_note=getattr(alloc, "note", None),
            high_propensity_tercile=_dti_subset(emitted, high, active),
            propensity_tercile_cut=float(cut))
        out.setdefault("_terms", {})[arm] = terms
    return out


_COV_CACHE: dict = {}


def build_covariates_cached(footprint: np.ndarray):
    key = "cov"
    if key not in _COV_CACHE:
        cache = Path("/tmp/gems65_cache")
        cache.mkdir(parents=True, exist_ok=True)
        npz = cache / "covariates.npz"
        meta = cache / "covariates.json"
        if npz.is_file() and meta.is_file():
            data = np.load(npz)
            values = {k: data[k] for k in data.files}
            diagnostics = json.loads(meta.read_text())
        else:
            cov = cov_mod.build(footprint)
            values, diagnostics = cov.values, cov.diagnostics
            np.savez_compressed(npz, **values)
            meta.write_text(json.dumps(diagnostics, indent=2))
        _COV_CACHE[key] = cov_mod.Covariates(values=values, shape=footprint.shape,
                                             diagnostics=diagnostics)
    return _COV_CACHE[key]
