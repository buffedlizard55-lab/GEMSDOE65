"""Experiment 4: does pruning near-catalogue dots pay, and does it explain 0.2778?

Two measurements that must be read together.

(a) SCORE RECONSTRUCTION.  Measure the 0.2778 submission raster from the registry
    bytes: dot count, value support, and the exact histogram of each dot's
    distance to the nearest mapped fault.  A hard filter that deleted every dot
    inside 2 px leaves a hole in that histogram at 1, sqrt(2) and 2.

(b) PRUNE ON THE HOLDOUT.  The halo experiment in emission_halo.py forbade the
    halo *before* allocating, so the displaced capacity was refilled from
    lower-ranked cells and the comparison confounded two effects.  Here the
    allocation is frozen (the same saturated SAR set the gate used) and dots are
    only DELETED, never replaced -- which is what the 0.2778 author did.  The
    predicted effect on the holdout is the same sign as the leaderboard effect if
    the mechanism is the same: pure false positives removed, true positives kept.
"""
from __future__ import annotations
import json, pathlib, sys, time
import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import importlib.util as _u
spec = _u.spec_from_file_location("drv", ROOT / "scripts" / "run_lane.py")
drv = _u.module_from_spec(spec); spec.loader.exec_module(drv)
from gems65 import lane                              # noqa: E402
from gems65.template.metric import dti_exact         # noqa: E402

SCORE_2778 = dict(sha16="c55bafc470054e82",
                  file="/tmp/gems_registry_cache/c55bafc470054e82.tif",
                  source="GEMSDOE32:docs/downloads/gemsdoe32-h33-h33-2-b2-"
                         "20261004T220000Z-e5eb6e7e-zeros.tif",
                  organizer_score=0.2778)
PRUNE_RADII = (2.0, 2.236, 2.828, 3.0)


def main():
    t0 = time.time()
    g, folds, hidden, region, visible, masked_known = drv.load_draw()
    dist_known = ndi.distance_transform_edt(~masked_known)
    dist_cat = ndi.distance_transform_edt(~g.catalogue)
    rep = {"evidence_class": "MEASURED + HOLDOUT-DTI", "runtime_s": None}

    # (a) reconstruction of the scored raster ---------------------------------
    with rasterio.open(SCORE_2778["file"]) as ds:
        a = ds.read(1)
    d = np.isfinite(a) & (a > 0)
    dd = dist_cat[d]
    edges = [0, 1, 1.5, 2, 2.236, 2.5, 2.9, 3.0, 3.5, 4, 5, 10, 50, 250]
    h, e = np.histogram(dd, bins=edges)
    rep["score_02778"] = {
        **SCORE_2778,
        "n_dots": int(d.sum()),
        "finite_pixels": int(np.isfinite(a).sum()),
        "nan_pixels": int(np.isnan(a).sum()),
        "values": [float(v) for v in np.unique(a[np.isfinite(a)])],
        "dots_on_mapped_fault": int((d & g.catalogue).sum()),
        "min_dist_px": float(dd.min()), "median_dist_px": float(np.median(dd)),
        "p95_dist_px": float(np.percentile(dd, 95)),
        "n_within_2px": int((dd <= 2.0).sum()),
        "n_at_sqrt5": int(np.isclose(dd, np.sqrt(5)).sum()),
        "hist": [[float(lo), float(hi), int(c)] for lo, hi, c in zip(e[:-1], e[1:], h)],
        "removed_by_the_02708_to_02778_filter": 2545,
        "arithmetic": {
            "note": ("D0 - D1 = alpha * 2545 = 509.0 exactly, if the removed dots "
                     "earned no truth credit; DTI1/DTI0 = D0/D1 then pins the "
                     "denominators and the true-positive mass."),
            "alpha": 0.2, "dti_before": 0.2708, "dti_after": 0.2778,
            "denominator_after": float(0.2 * 2545 * 0.2708 / (0.2778 - 0.2708)),
            "implied_true_positive_mass": float(0.2778 * 0.2 * 2545 * 0.2708 / (0.2778 - 0.2708)),
            "implied_truth_set_size_if_FP_is_dots_minus_TP": float(
                (0.2 * 2545 * 0.2708 / (0.2778 - 0.2708)
                 - 0.2778 * 0.2 * 2545 * 0.2708 / (0.2778 - 0.2708)
                 - 0.2 * (37654 - 1200)) / 0.8 + 0.2778 * 0.2 * 2545 * 0.2708 / (0.2778 - 0.2708)),
        },
    }

    # (b) prune-only experiment on the frozen saturated SAR allocation ---------
    scores = dict(np.load("/tmp/gems65/scores_holdout.npz"))
    allowed = g.footprint & ~masked_known
    truth = hidden & region
    K = float(hidden.sum())
    p = lane.rescale_to_prior(scores["sar"], allowed, K)
    alloc = lane.allocate_nms(p, allowed, K, radius_px=3,
                              b_grid=(500, 1000, 2000, 4000, 8000, 16000, 32000,
                                      64000, 100000, 160000))
    order = alloc["scan_order"]
    full = np.zeros(allowed.shape, bool)
    full[order[:, 0], order[:, 1]] = True
    full &= allowed
    rows = []
    for r in (None,) + PRUNE_RADII:
        m = full.copy()
        # prune on the holdout must use the VISIBLE catalogue, which is the only
        # catalogue that exists in a hide-and-recover draw.
        if r is not None:
            m &= dist_known > r
        ev = dti_exact(m.astype(np.float32), truth, valid=g.footprint, known=masked_known)
        rows.append({"prune_radius_px": r, "n_dots": int(m.sum()),
                     "holdout_dti": float(ev["dti"]), "tpw": float(ev["tp"]),
                     "fpw": float(ev["fp"]), "fnw": float(ev["fn"])})
        print(f"  prune>{r}: dots={int(m.sum()):6d} HOLDOUT-DTI={ev['dti']:.6f} "
              f"TPw={ev['tp']:.0f} FPw={ev['fp']:.0f}", flush=True)
    rep["prune_only"] = {"arm": "sar (saturated nms3 allocation)",
                         "instrument": "same blocked draw as the gate",
                         "rows": rows,
                         "interpretation": ("prune-only isolates the false-positive "
                                            "deletion effect from the refill effect "
                                            "that confounded emission_halo.json")}
    rep["runtime_s"] = round(time.time() - t0, 1)
    (ROOT / "evidence" / "prune.json").write_text(json.dumps(rep, indent=1) + "\n")
    print("wrote evidence/prune.json")


if __name__ == "__main__":
    main()
