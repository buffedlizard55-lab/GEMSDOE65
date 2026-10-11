"""Stage 04 -- the registry-calibrated live-mirror instrument.

WHAT IT IS.  This checkout can read nine prior submission rasters that carry an owner-reported live
score (registry/registry_rasters.json + registry/registry_receipt.json).  Taken together they are a
calibration set for a *relative* instrument: score every raster -- including the new candidate --
against a common pseudo-truth built from the best-scoring artifact, and check that the resulting
ordering reproduces the reported live ordering.  If it does, the instrument can rank a new candidate
against the family it resembles.

WHAT IT IS NOT.  The pseudo-truth is a submission, not the hidden truth.  The instrument therefore
measures "how much does this candidate look like the 0.2778 family", and it is deliberately
pessimistic about a candidate whose whole point is to be different.  Every number it emits is
labelled MIRROR-DTI and is never written as a score or a projection of one.

Reported:
  * per-raster MIRROR-DTI against the anchor pseudo-truth, next to its owner-reported live score;
  * Spearman rank correlation between the two (the instrument's own quality);
  * a leave-one-out version, so the anchor is not scored against itself;
  * the candidate's MIRROR-DTI and where it falls in the live-score ordering.

Run:  python scripts/04_live_mirror.py docs/downloads/<candidate>-nan.tif
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems65 import grid as G
from gems65 import metric as M


def read(path: Path) -> np.ndarray:
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float32)
    return np.nan_to_num(a, nan=0.0)


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
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate", nargs="?", default=None)
    ap.add_argument("--anchor", default=None, help="override the pseudo-truth anchor raster")
    args = ap.parse_args()

    repo = G.repo_root()
    ddir = G.data_dir()
    foot = G.read_footprint(ddir)
    labels = G.read_labels(ddir)
    receipt = json.loads((repo / "registry" / "registry_receipt.json").read_text())
    # keyed by FILENAME: r["dest"] is an absolute path, so keying by dest and looking up by
    # .name raised KeyError on the anchor (fixed 2026-10-11).
    reg = {Path(r["dest"]).name: r for r in receipt["rasters"]}

    entries = [r for r in receipt["rasters"] if Path(r["dest"]).exists() and r.get("reported_score")]
    if not entries:
        print("no scored registry rasters available; run scripts/00_fetch_registry.py first", file=sys.stderr)
        return 2

    # anchor = highest owner-reported score (ties -> most dots, i.e. the less-thinned artifact)
    if args.anchor:
        anchor = Path(args.anchor)
    else:
        best = max(entries, key=lambda r: (r["reported_score"], r.get("positive_pixels", 0)))
        anchor = Path(best["dest"])
    print(f"[anchor] {anchor.name}  reported live {reg.get(anchor.name, {}).get('reported_score')}")
    A = read(anchor) > 0
    A = A & foot & ~labels                      # pseudo-truth restricted to scoreable pixels
    n_anchor = int(A.sum())
    print(f"[anchor] pseudo-truth pixels: {n_anchor:,}")

    rows = []
    for r in entries + ([{"dest": args.candidate, "reported_score": None,
                          "score_class": "CANDIDATE"}] if args.candidate else []):
        p = Path(r["dest"])
        if not p.exists():
            continue
        P = read(p)
        mask = (P > 0) & foot & ~labels
        if not mask.any():
            continue
        c = M.components(P.astype(np.float64), A, valid=foot, known=labels)
        rows.append({
            "raster": p.name,
            "path": str(p),
            "reported_live_score": r.get("reported_score"),
            "score_class": r.get("score_class"),
            "dots": int(mask.sum()),
            "MIRROR_DTI": c["dti"],
            "MIRROR_credit_per_dot": c["credit_per_unit_mass"],
            "MIRROR_coverage_of_anchor": c["TP_w"] / max(n_anchor, 1),
            "overlap_with_anchor_dots": int((mask & A).sum()),
        })
        print(f"  {p.name[:58]:58s} dots={rows[-1]['dots']:6d} "
              f"MIRROR={rows[-1]['MIRROR_DTI']:.5f} live={r.get('reported_score')}")

    scored = [x for x in rows if x["reported_live_score"] is not None]
    loo = []
    for i, r in enumerate(scored):
        other = max([s for s in scored if s["raster"] != r["raster"]],
                    key=lambda s: s["reported_live_score"])
        # rows carry both "raster" (display name) and "path"; the LOO loop must read the PATH
        # (fixed 2026-10-11: reading Path(other["raster"]) raised CPLE_OpenFailedError).
        B = read(Path(other["path"])) > 0
        B = B & foot & ~labels
        P = read(Path(r["path"]))
        c = M.components(np.nan_to_num(P, nan=0.0).astype(np.float64), B, valid=foot, known=labels)
        loo.append({"raster": r["raster"], "pseudo_truth": other["raster"],
                    "MIRROR_DTI": c["dti"], "reported_live_score": r["reported_live_score"]})
    rho = spearman(np.array([x["MIRROR_DTI"] for x in scored], float),
                   np.array([x["reported_live_score"] for x in scored], float))
    rho_loo = spearman(np.array([x["MIRROR_DTI"] for x in loo], float),
                       np.array([x["reported_live_score"] for x in loo], float))

    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_class": "MIRROR-DTI (instrument, not a score; pseudo-truth is a submission, not the hidden truth)",
        "anchor": str(anchor),
        "anchor_reported_live_score": reg[anchor.name]["reported_score"],
        "anchor_pseudo_truth_pixels": n_anchor,
        "instrument_quality": {
            "spearman_mirror_vs_live_anchor_pseudo_truth": rho,
            "spearman_mirror_vs_live_leave_one_out": rho_loo,
            "n_scored_rasters": len(scored),
            "interpretation": ("rho near 1 means the mirror ranks the family the way the leaderboard did; "
                               "it says nothing about faults outside the family"),
        },
        "rows": rows,
        "leave_one_out": loo,
        "candidate": next((x for x in rows if x["score_class"] == "CANDIDATE"), None),
    }
    (repo / "evidence" / "live_mirror.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[instrument] spearman(mirror, live) anchor={rho:.3f} leave-one-out={rho_loo:.3f} "
          f"n={len(scored)} -> evidence/live_mirror.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
