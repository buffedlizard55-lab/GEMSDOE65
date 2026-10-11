"""Experiment 2: emission rule.  Compares the DTI-bar allocation (bar-only) with
the predeclared price-curve budget, for every arm, on the SAME holdout draw.

Reuses the score fields written by `run_lane.py gate` so the models are
identical; only the emission rule changes.  Nothing here re-trains anything.
"""
from __future__ import annotations
import hashlib, json, pathlib, sys, time
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import importlib.util as _u
spec = _u.spec_from_file_location("drv", ROOT / "scripts" / "run_lane.py")
drv = _u.module_from_spec(spec); spec.loader.exec_module(drv)

from gems65_sarprop import lane                                    # noqa: E402
from gems65_sarprop.template.emit import allocate_by_marginal_bar  # noqa: E402
from gems65_sarprop.template.metric import dti_exact               # noqa: E402

B_GRID = (500, 1000, 2000, 4000, 8000, 16000, 32000, 64000, 100000, 160000)


def main():
    t0 = time.time()
    g, folds, hidden, region, visible, masked_known = drv.load_draw()
    scores = dict(np.load("/tmp/gems65/scores_holdout.npz"))
    allowed = g.footprint & ~masked_known
    truth = hidden & region
    K = float(hidden.sum())
    rep = {"evidence_class": "HOLDOUT-DTI (template dti_exact, alpha 0.2, beta 0.8, 300 m kernel)",
           "instrument": f"buffered whole-component draw seed {drv.DRAW_SEED}, "
                         f"hide_frac {drv.HIDE_FRAC}, 3 px collar",
           "withheld_positives": int(hidden.sum()),
           "b_grid_predeclared": list(B_GRID),
           "emission_rules": {}, "runtime_s": None}
    for rule in ("bar_only", "price_curve", "price_curve_nms3"):
        rep["emission_rules"][rule] = {}
        for nm in ("nnpu", "sar", "scar"):
            sc = scores[nm]
            p = lane.rescale_to_prior(sc, allowed, K)
            if rule == "bar_only":
                a = allocate_by_marginal_bar(p, allowed, K, floor=1e-4, max_dots=lane.MAX_DOTS)
                emitted, budget = a.emitted & allowed, int(a.emitted.sum())
                surrogate = float(a.surrogate_dti)
                curve = None
            elif rule == "price_curve":
                r = lane.allocate_topb(p, allowed, K, b_grid=B_GRID)
                emitted, budget = r["emitted"], r["budget"]
                surrogate = r["surrogate_dti"]
                curve = r["curve"]
            if rule == "price_curve_nms3":
                r = lane.allocate_nms(p, allowed, K, radius_px=3, b_grid=B_GRID)
                emitted, budget = r["emitted"], r["budget"]
                surrogate = r["surrogate_dti"]
                curve = r["curve"]
            ev = dti_exact(emitted.astype(np.float32), truth, valid=g.footprint, known=masked_known)
            ent = {"n_dots": budget, "surrogate_dti": surrogate,
                   "holdout_dti": float(ev["dti"]), "tpw": float(ev["tp"]),
                   "fpw": float(ev["fp"]), "fnw": float(ev["fn"]),
                   "n_truth": int(ev["n_truth"])}
            if curve is not None:
                ent["curve"] = curve
            rep["emission_rules"][rule][nm] = ent
            np.save(f"/tmp/gems65/dots_{rule}_{nm}.npy", emitted)
            print(f"  {rule:11s} {nm:5s} dots={budget:6d} HOLDOUT-DTI={ev['dti']:.6f} "
                  f"TPw={ev['tp']:.1f} FPw={ev['fp']:.0f}")
    rep["runtime_s"] = round(time.time() - t0, 1)
    (ROOT / "evidence" / "emission.json").write_text(json.dumps(rep, indent=1) + "\n")
    print("wrote evidence/emission.json")


if __name__ == "__main__":
    main()
