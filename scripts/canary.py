"""Leakage canary (parallel-run protocol rule 4).

Each feature is tested ALONE against the blocked holdout.  AUC above 0.90 in
either direction means leakage until proven otherwise.  Tested on the SAME rows
the models were fitted on, so the canary measures the feature, not the model.
"""
from __future__ import annotations
import json, pathlib, sys
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import importlib.util as _u
spec = _u.spec_from_file_location("drv", ROOT / "scripts" / "run_lane.py")
drv = _u.module_from_spec(spec); spec.loader.exec_module(drv)
from gems65 import lane
from sklearn.metrics import roc_auc_score

def main():
    g, folds, hidden, region, visible, masked_known = drv.load_draw()
    d = np.load(drv.CACHE)
    rows, cols = d["rows"], d["cols"]
    truth = hidden[rows, cols] & region[rows, cols]
    allowed = (g.footprint & ~masked_known)[rows, cols]
    names = lane.build_design_names()
    X = d["X"].astype(np.float64)          # (19, n)
    Z = d["Z"].astype(np.float64)          # (5, n)
    cols_all = [X[i] for i in range(X.shape[0])] + [Z[i] for i in range(Z.shape[0])]
    rows_out = lane.canary(cols_all, truth & allowed, allowed, names=names,
                           n_sample=60_000, seed=11)
    worst = max((r["discriminative_auc"] for r in rows_out), default=0.0)
    out = {"evidence_class": "HOLDOUT-DTI instrument / feature diagnostics (not a score)",
           "definition": "max(AUC, 1-AUC) per feature alone, truth = withheld "
                         "catalogue pixels inside a label-blind eroded quadrant",
           "threshold": 0.90, "worst_discriminative_auc": worst,
           "flag": bool(worst > 0.90), "features": rows_out}
    (ROOT / "evidence" / "canary.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"worst discriminative AUC = {worst:.4f}  flag={out['flag']}")
    for r in rows_out[:8]:
        print(f"   {r['feature']:24s} auc={r['auc']:.4f}")
main()
