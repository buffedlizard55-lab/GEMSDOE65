"""Experiment 1b: the honest budget curve -- MEASURED holdout DTI per budget.

`allocate_nms` chooses the budget that maximises a *surrogate* (the price curve
under the model's own p).  This script checks the surrogate against the real
evaluator by scoring every predeclared budget with template.metric.dti_exact on
the same allocation order, so the budget transferred to the live run is backed
by a measurement, not by the model's self-estimate.
"""
from __future__ import annotations
import json, pathlib, sys, time
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import importlib.util as _u
spec = _u.spec_from_file_location("drv", ROOT / "scripts" / "run_lane.py")
drv = _u.module_from_spec(spec); spec.loader.exec_module(drv)
from gems65 import lane                       # noqa: E402
from gems65.template.metric import dti_exact  # noqa: E402

B_GRID = (500, 1000, 2000, 4000, 8000, 16000, 32000, 64000, 100000, 160000)


def main():
    t0 = time.time()
    g, folds, hidden, region, visible, masked_known = drv.load_draw()
    scores = dict(np.load("/tmp/gems65/scores_holdout.npz"))
    allowed = g.footprint & ~masked_known
    truth = hidden & region
    K = float(hidden.sum())
    rep = {"evidence_class": "HOLDOUT-DTI (relative instrument)",
           "b_grid_predeclared": list(B_GRID), "arms": {}, "runtime_s": None}
    for nm in ("sar", "nnpu"):
        p = lane.rescale_to_prior(scores[nm], allowed, K)
        a = lane.allocate_nms(p, allowed, K, radius_px=3, b_grid=B_GRID)
        order = a["scan_order"]
        rows = []
        for b in B_GRID:
            m = np.zeros(allowed.shape, bool)
            sel = order[:b]
            m[sel[:, 0], sel[:, 1]] = True
            m &= allowed
            ev = dti_exact(m.astype(np.float32), truth, valid=g.footprint, known=masked_known)
            rows.append({"budget": int(b), "n_dots": int(m.sum()),
                         "holdout_dti": float(ev["dti"]), "tpw": float(ev["tp"]),
                         "fpw": float(ev["fp"]), "fnw": float(ev["fn"])})
            print(f"  {nm:5s} b={b:7d} dots={int(m.sum()):6d} HOLDOUT-DTI={ev['dti']:.6f} "
                  f"TPw={ev['tp']:.0f}", flush=True)
        best = max(rows, key=lambda r: r["holdout_dti"])
        rep["arms"][nm] = {"curve": rows, "measured_argmax": best}
        print(f"  -> {nm}: surrogate picked {a['budget']}, measurement picks "
              f"{best['budget']} (DTI {best['holdout_dti']:.6f})", flush=True)
    rep["runtime_s"] = round(time.time() - t0, 1)
    (ROOT / "evidence" / "budget_curve.json").write_text(json.dumps(rep, indent=1) + "\n")
    print("wrote evidence/budget_curve.json")


if __name__ == "__main__":
    main()
