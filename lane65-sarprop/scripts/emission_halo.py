"""Experiment 3: exclude the halo around KNOWN faults when emitting.

Mechanism
---------
`template.metric.dti_exact` scores on `active = valid & ~known`, and the credit
field `q` is built from `active & truth` ONLY.  A dot sitting on (or within the
kernel radius of) an already-catalogued fault therefore earns zero true-positive
credit and still counts 1.0 towards the false-positive mass.  Since the model is
trained on the catalogue, its highest scores sit exactly in that halo -- the most
expensive real estate on the map.

This script measures, on the same blocked holdout and the same fitted arms, how
much HOLDOUT-DTI is recovered by forbidding dots within `halo_px` of a visible
(known) fault.  Halo widths are predeclared {0, 2, 3, 4}; 0 is the incumbent.
"""
from __future__ import annotations
import json, pathlib, sys, time
import numpy as np
from scipy import ndimage as ndi

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import importlib.util as _u
spec = _u.spec_from_file_location("drv", ROOT / "scripts" / "run_lane.py")
drv = _u.module_from_spec(spec); spec.loader.exec_module(drv)
from gems65_sarprop import lane                              # noqa: E402
from gems65_sarprop.template.metric import dti_exact         # noqa: E402

B_GRID = (500, 1000, 2000, 4000, 8000, 16000, 32000, 64000, 100000, 160000)
HALOS = (0, 2, 3, 4)


def main():
    t0 = time.time()
    g, folds, hidden, region, visible, masked_known = drv.load_draw()
    scores = dict(np.load("/tmp/gems65/scores_holdout.npz"))
    truth = hidden & region
    K = float(hidden.sum())
    st = ndi.generate_binary_structure(2, 2)
    dil = {h: (masked_known if h == 0 else ndi.binary_dilation(masked_known, st, iterations=h))
           for h in HALOS}
    rep = {"evidence_class": "HOLDOUT-DTI (relative instrument; NOT comparable to "
                             "leaderboard DTI because the leaderboard scores against "
                             "the full truth set, this scores against withheld pixels only)",
           "question": "is the 3 px halo of KNOWN faults worth emitting into?",
           "halo_px_predeclared": list(HALOS),
           "budget_rule": "price_curve_nms3, b_grid predeclared",
           "results": {}, "runtime_s": None}
    for nm in ("nnpu", "sar", "scar"):
        rep["results"][nm] = {}
        for h in HALOS:
            allowed = g.footprint & ~dil[h]
            p = lane.rescale_to_prior(scores[nm], allowed, K)
            a = lane.allocate_nms(p, allowed, K, radius_px=3, b_grid=B_GRID)
            ev = dti_exact(a["emitted"].astype(np.float32), truth,
                           valid=g.footprint, known=masked_known)
            rep["results"][nm][str(h)] = {
                "allowed_cells": int(allowed.sum()), "n_dots": int(a["emitted"].sum()),
                "budget": a["budget"], "surrogate_dti": float(a["surrogate_dti"]),
                "holdout_dti": float(ev["dti"]), "tpw": float(ev["tp"]),
                "fpw": float(ev["fp"]), "fnw": float(ev["fn"])}
            print(f"  {nm:5s} halo={h}px allowed={allowed.sum():8d} dots={a['emitted'].sum():6d} "
                  f"HOLDOUT-DTI={ev['dti']:.6f} TPw={ev['tp']:.1f} FPw={ev['fp']:.0f}", flush=True)
    rep["runtime_s"] = round(time.time() - t0, 1)
    (ROOT / "evidence" / "emission_halo.json").write_text(json.dumps(rep, indent=1) + "\n")
    print("wrote evidence/emission_halo.json")


if __name__ == "__main__":
    main()
