"""Validate the top-ranked local hypothesis on the spatially blocked holdout.

HYPOTHESIS (ranked #1 among those whose data is already on disk)
    Thermal-fluid pathway layer.  Hot springs and wells with elevated measured or
    geothermometry-inferred temperatures mark permeable fault pathways.  A
    surface-rupture catalogue under-represents blind, buried and small-
    displacement structures, but those are exactly the structures that channel
    fluid -- so a hot-site density field should carry information about faults
    that are MISSING from the catalogue.

WHY THIS TEST AND NOT A RETRAIN
    Promoting a new layer into the submission is what the protocol forbids
    without holdout evidence.  This test answers the question the promotion
    decision actually asks -- "would adding this layer change the emitted file
    for the better?" -- at the EMISSION level, holding the fitted model and the
    propensity field completely fixed.  Only the ranking the emission rule walks
    changes.  If a blend does not beat lambda = 0 on the blocked holdout, the
    layer does not get promoted, whatever a retrain might have shown.

    A positive result here is a licence to spend a retrain; it is not itself a
    promotion, and nothing in this script writes a submission.
"""
from __future__ import annotations
import csv, json, pathlib, sys, time
import numpy as np
from scipy import ndimage as ndi

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import importlib.util as _u
spec = _u.spec_from_file_location("drv", ROOT / "scripts" / "run_lane.py")
drv = _u.module_from_spec(spec); spec.loader.exec_module(drv)
from gems65 import lane                       # noqa: E402
from gems65.template.metric import dti_exact  # noqa: E402

WELLSPRING_CSV = "/tmp/reg2/G48/data/raw/external/gdr_wellspring_in_footprint.csv"
QFAULT_CSV = "/tmp/reg2/G48/data/raw/external/gdr_qfaults_traces.csv"
LAMBDAS = (0.0, 0.25, 0.5, 1.0)          # predeclared before any score was read
HOT_C = 40.0                              # "hot" = measured or inferred above 40 C
SIGMA_PX = 4.0                            # ~400 m kernel: fault-pathway scale


def hot_site_field(shape):
    """Temperature-weighted hot-site density from the local GDR well/spring table."""
    rows, cols, weights = [], [], []
    seen = {}
    n_rows = 0
    with open(WELLSPRING_CSV) as f:
        for r in csv.DictReader(f):
            n_rows += 1
            try:
                y, x = int(r["row"]), int(r["col"])
            except (TypeError, ValueError):
                continue
            if not (0 <= y < shape[0] and 0 <= x < shape[1]):
                continue
            cls = (r.get("thermalclass") or "").strip().lower()
            temp = float(r["temp_c"]) if r.get("temp_c") else np.nan
            geoth = max([float(r[k]) for k in ("geothermquartz_c", "geothermchalc_c",
                                               "geothermcat_c") if r.get(k)] or [np.nan])
            t = np.nanmax([temp, geoth])
            hot = (cls in ("hot", "warm")) or (np.isfinite(t) and t >= HOT_C)
            if not hot:
                continue
            w = 1.0 + (t / 100.0 if np.isfinite(t) else 0.0)
            key = (y, x)
            if seen.get(key, -1) >= w:
                continue
            seen[key] = w
    for (y, x), w in seen.items():
        rows.append(y); cols.append(x); weights.append(w)
    f = np.zeros(shape, np.float64)
    np.add.at(f, (rows, cols), weights)
    return ndi.gaussian_filter(f, SIGMA_PX), {"csv_rows": n_rows, "hot_sites": len(rows),
                                              "kernel_sigma_px": SIGMA_PX, "hot_rule":
                                              f"thermalclass in (Hot,Warm) or max(T, geotherm) >= {HOT_C} C"}


def main():
    t0 = time.time()
    g, folds, hidden, region, visible, masked_known = drv.load_draw()
    scores = dict(np.load("/tmp/gems65/scores_holdout.npz"))
    allowed = g.footprint & ~masked_known
    truth = hidden & region
    K = float(hidden.sum())
    rep = {"evidence_class": "HOLDOUT-DTI (relative instrument)",
           "hypothesis": "thermal-fluid pathway layer (hot springs / geothermometry)",
           "lambdas_predeclared": list(LAMBDAS), "runtime_s": None}

    w_raw, meta = hot_site_field(hidden.shape)
    rep["feature"] = {**meta, "nonzero_cells": int((w_raw > 0).sum()),
                      "inside_allowed": int(((w_raw > 0) & allowed).sum())}
    w = np.zeros_like(w_raw, np.float32)
    sel = allowed & (w_raw > 0)
    if sel.sum() > 10:
        mu, sd = float(w_raw[sel].mean()), float(w_raw[sel].std())
        w[allowed] = (w_raw[allowed] / max(sd, 1e-9)).astype(np.float32)
    rep["feature"]["standardised_mean_inside_allowed"] = float(w[allowed].mean())
    np.save("/tmp/gems65/wellspring_field.npy", w)

    # --- leakage canary on the new layer alone ------------------------------
    from sklearn.metrics import roc_auc_score
    yy = truth[allowed]
    ww = w[allowed]
    ok = ww > 0
    rep["canary"] = {
        "auc_allowed_all_cells": (float(roc_auc_score(yy, ww)) if yy.any() and yy.any() < 1 else None),
        "auc_where_feature_is_nonzero": (float(roc_auc_score(yy[ok], ww[ok]))
                                         if ok.sum() > 32 and 0 < yy[ok].sum() < ok.sum() else None),
        "base_rate": float(yy.mean()), "rate_where_feature_nonzero": (float(yy[ok].mean())
                                                                     if ok.any() else None),
        "n_nonzero": int(ok.sum()),
        "threshold": 0.90, "note": "above 0.90 would be leakage until proven otherwise"}

    # --- emission-level marginal test ---------------------------------------
    s = scores["sar"]
    zs = np.zeros_like(s, np.float32)
    m = allowed & np.isfinite(s)
    zs[m] = ((s[m] - s[m].mean()) / max(s[m].std(), 1e-9)).astype(np.float32)
    rows = []
    for lam in LAMBDAS:
        blend = zs + lam * w
        p = lane.rescale_to_prior(np.exp(blend.astype(np.float64)), allowed, K)
        a = lane.allocate_nms(p, allowed, K, radius_px=3,
                              b_grid=(500, 1000, 2000, 4000, 8000, 16000, 32000,
                                      64000, 100000, 160000))
        order = a["scan_order"]
        emit = np.zeros(allowed.shape, bool)
        emit[order[:, 0], order[:, 1]] = True
        emit &= allowed
        dist = ndi.distance_transform_edt(~masked_known)
        emit = lane.prune_band(emit, dist, 2.0)
        ev = dti_exact(emit.astype(np.float32), truth, valid=g.footprint, known=masked_known)
        rows.append({"lambda": lam, "n_dots": int(emit.sum()), "holdout_dti": float(ev["dti"]),
                     "tpw": float(ev["tp"]), "fpw": float(ev["fp"])})
        print(f"  lambda={lam:<5} dots={int(emit.sum()):6d} HOLDOUT-DTI={ev['dti']:.6f} "
              f"TPw={ev['tp']:.0f}", flush=True)
    base = next(r for r in rows if r["lambda"] == 0.0)
    best = max(rows, key=lambda r: r["holdout_dti"])
    rep["emission_level_test"] = {
        "baseline_lambda0_dti": base["holdout_dti"], "rows": rows,
        "best": best,
        "supported": bool(best["holdout_dti"] > base["holdout_dti"] + 1e-6
                          and best["lambda"] > 0),
        "decision_rule": ("promote the layer only if some lambda > 0 beats lambda = 0 on "
                          "the blocked holdout by more than 1e-6; otherwise it is a "
                          "negative result and the layer is not promoted")}
    rep["runtime_s"] = round(time.time() - t0, 1)
    (ROOT / "evidence" / "hypothesis_thermal_pathway.json").write_text(json.dumps(rep, indent=1) + "\n")
    print("supported:", rep["emission_level_test"]["supported"],
          "| best lambda:", best["lambda"], "->", f"{best['holdout_dti']:.6f}")
    print("wrote evidence/hypothesis_thermal_pathway.json")


if __name__ == "__main__":
    main()
