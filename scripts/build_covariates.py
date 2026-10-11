#!/usr/bin/env python3
"""Build + cache the lane's covariate stack and write its receipt."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: F401
from gems65 import covariates as cov
from gems65.paths import CACHE, COVARIATE_CACHE, EXTERNAL, FEATURES_TIF

def main() -> None:
    t0 = time.time()
    feats = FEATURES_TIF
    lidar = EXTERNAL / "lidar_scarp_features_u8.tif"
    topo = EXTERNAL / "topo_10m_derived_100m_u8.tif"
    for p in (feats, lidar):
        if not p.exists():
            raise SystemExit(f"missing input {p}; run scripts/fetch_data.py first")
    out = cov.build_covariates(feats, lidar, cache=COVARIATE_CACHE, dequant_topo=topo)
    rec = out["receipt"]
    rec["seconds"] = round(time.time() - t0, 1)
    rec["inputs"] = {"features": str(feats), "lidar": str(lidar), "topo_10m": str(topo)}
    Path(COVARIATE_CACHE).with_suffix(".receipt.json").write_text(json.dumps(rec, indent=2))
    print(json.dumps({k: v for k, v in rec.items() if k != "covariate_summary"}, indent=2))
    print("--- covariate summary ---")
    for k, v in rec["covariate_summary"].items():
        print(f"{k:20s} med {v['median']:10.3f}  mean_on_cat {v['mean_on_catalogue']:10.3f}"
              f"  mean_off_cat {v['mean_off_catalogue']:10.3f}")

if __name__ == "__main__":
    main()
