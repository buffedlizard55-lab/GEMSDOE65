"""Stage 05 -- calibrate the blocked holdout against nine owner-reported LIVE scores.

WHY THIS EXISTS.  The lane's gate is a blocked-holdout DTI comparison.  Before spending a slot on
anything, the instrument itself has to be checked: does a higher holdout DTI actually mean a higher
live score?  This script scores every registry raster that carries an owner-reported live score on
the SAME 8 blocked cells used by stage 02, and reports the rank correlation.

KNOWN HANDICAP (stated, not hidden): every registry artifact was built to avoid ALL catalogue
pixels (the live metric masks them), while this holdout withholds only part of the catalogue, so
registry dots are structurally kept away from the withheld truth.  The handicap is identical for all
nine rasters, so the RANKING is still informative even though the absolute levels are depressed.

Run:  python scripts/05_holdout_calibration.py
Out:  evidence/holdout_calibration.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems65 import grid as G
from gems65 import holdout as HO
from gems65 import metric as M


def spearman(x, y):
    """Tie-corrected Spearman (average ranks).  See IR-65-003: argsort-argsort ranking breaks ties
    by array position and returns ~0.97 for any pair of 99%-zero dot fields."""
    from scipy.stats import rankdata
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if x.size < 3:
        return float("nan")
    rx = rankdata(x, method="average"); ry = rankdata(y, method="average")
    rx = rx - rx.mean(); ry = ry - ry.mean()
    d = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    return float((rx * ry).sum() / d) if d > 0 else float("nan")


def main() -> int:
    t0 = time.time()
    repo, ddir = G.repo_root(), G.data_dir()
    foot = G.read_footprint(ddir)
    labels = G.read_labels(ddir)
    ctx = HO.build_holdout(foot, labels)
    receipt = json.loads((repo / "registry" / "registry_receipt.json").read_text())
    entries = [r for r in receipt["rasters"] if Path(r["dest"]).exists()]

    rows = []
    for r in entries:
        p = Path(r["dest"])
        with rasterio.open(p) as ds:
            a = ds.read(1).astype(np.float32)
        mask = (np.nan_to_num(a, nan=0.0) > 0) & foot
        cells = []
        for c in ctx.cells:
            sl = c.bbox
            cells.append(HO.score_prediction((mask[sl] & c.active).astype(np.float64), c))
        pooled = M.dti_pooled(cells)
        rows.append({
            "raster": p.name,
            "reported_live_score": r.get("reported_score"),
            "score_class": r.get("score_class"),
            "dots": int(mask.sum()),
            "holdout_pooled_dti": pooled["dti"],
            "holdout_mean_cell_dti": float(np.mean([c["dti"] for c in cells])),
            "holdout_coverage": pooled["coverage"],
            "holdout_tp": pooled["tp"],
        })
        print(f"  {p.name[:56]:56s} dots={rows[-1]['dots']:6d} "
              f"holdout_pooled={pooled['dti']:.5f} live={r.get('reported_score')}")

    scored = [x for x in rows if x["reported_live_score"] is not None]
    rho = spearman([x["holdout_pooled_dti"] for x in scored], [x["reported_live_score"] for x in scored])
    rho_mean = spearman([x["holdout_mean_cell_dti"] for x in scored], [x["reported_live_score"] for x in scored])
    rho_dots = spearman([x["dots"] for x in scored], [x["reported_live_score"] for x in scored])
    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seconds": round(time.time() - t0, 1),
        "evidence_class": "HOLDOUT-DTI (proxy truth = withheld catalogue segments) vs OWNER-REPORT live scores",
        "n_scored_rasters": len(scored),
        "spearman_holdout_pooled_vs_live": rho,
        "spearman_holdout_mean_cell_vs_live": rho_mean,
        "spearman_dot_count_vs_live": rho_dots,
        "known_handicap": ("registry artifacts exclude ALL catalogue pixels; this holdout withholds only "
                           "part of the catalogue, so all nine are penalised equally and only the ranking "
                           "is informative"),
        "rows": rows,
    }
    (repo / "evidence" / "holdout_calibration.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[calibration] spearman(holdout_pooled, live) = {rho:+.3f}   "
          f"spearman(holdout_mean_cell, live) = {rho_mean:+.3f}   "
          f"spearman(dot_count, live) = {rho_dots:+.3f}   n={len(scored)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
