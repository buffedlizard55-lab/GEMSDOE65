#!/usr/bin/env python3
"""Cross-session drift check: this lane's field vs the sibling lane-65 session's rasters.

The parallel-run protocol's duplicate test is rank-correlation > 0.90 or > 70 % of dots
within 3 px of one comparator raster.  Applied literally against the whole registry it
is unmeetable for sparse fields (IR-65-UNIQ-01), but applied against the *other session
of the same lane* it is exactly the right question: did two independent implementations
of the same lane converge on the same answer?  This writes
``evidence/cross_session_drift.json``.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: F401,E402

from gems57 import uniqueness  # noqa: E402
from gems57.grid import load_grid  # noqa: E402
from gems65.paths import DATA, EVIDENCE, ensure_dirs  # noqa: E402

_bootstrap.assert_template60(uniqueness, load_grid)

MINE = "gemsdoe65-gems65-sar2inv-a2-38k"
RHO_LIMIT, OVERLAP_LIMIT, JACCARD_LIMIT = 0.90, 0.70, 0.50


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    ensure_dirs()
    grid = load_grid(DATA / "bridge")
    fp = grid.footprint
    dl = Path("docs/downloads")
    mine_p = next(p for p in sorted(dl.glob("*.tif")) if MINE in p.name)
    with rasterio.open(mine_p) as ds:
        mine = ds.read(1).astype(np.float32)
    rows = []
    for theirs_p in sorted(dl.glob("*.tif")):
        if theirs_p.name == mine_p.name:
            continue
        with rasterio.open(theirs_p) as ds:
            theirs = ds.read(1).astype(np.float32)
        theirs = np.where(np.isfinite(theirs), theirs, 0.0)
        theirs[~fp] = 0
        rho = uniqueness.surface_rho(mine, theirs, fp)   # dict, NaN where undefined
        fwd = uniqueness.dot_overlap(mine, theirs)
        rev = uniqueness.dot_overlap(theirs, mine)

        def num(x):
            x = float(x)
            return None if not np.isfinite(x) else x

        r_full = num(rho["spearman_full_footprint"])
        r_union = num(rho["spearman_on_dot_union"])
        rows.append({
            "file": theirs_p.name, "sha256": _sha(theirs_p),
            "their_dots": int(((theirs > 0) & fp).sum()),
            "spearman_full_footprint": r_full,
            "spearman_on_dot_union": r_union,
            "n_dot_union": int(rho["n_dot_union"]),
            "my_dots_within_3px_of_theirs": float(fwd),
            "their_dots_within_3px_of_mine": float(rev),
            "jaccard_dot_sets": num(rho["jaccard_dot_sets"]),
            "duplicate_by_rho": bool(r_full is not None and r_full > RHO_LIMIT),
            "duplicate_by_overlap": bool(fwd > OVERLAP_LIMIT),
        })
    out = {
        "evidence_class": "REGISTRY-MEASUREMENT",
        "question": "did two independent implementations of the same lane converge?",
        "candidate": {"file": mine_p.name, "sha256": _sha(mine_p),
                      "dots": int(((mine > 0) & fp).sum())},
        "comparators": "every other raster published under docs/downloads/ by the first "
                       "lane-65 session (arena/1217c9a0-gemsdoe65)",
        "limits": {"rho": RHO_LIMIT, "forward_overlap": OVERLAP_LIMIT,
                   "jaccard": JACCARD_LIMIT},
        "n_comparators": len(rows),
        "worst_spearman": max((r["spearman_full_footprint"] for r in rows
                               if r["spearman_full_footprint"] is not None), default=None),
        "worst_spearman_on_dot_union": max((r["spearman_on_dot_union"] for r in rows
                                            if r["spearman_on_dot_union"] is not None),
                                           default=None),
        "worst_forward_overlap": max((r["my_dots_within_3px_of_theirs"] for r in rows),
                                     default=None),
        "worst_jaccard": max((r["jaccard_dot_sets"] for r in rows), default=None),
        "duplicate_by_any_limit": any(r["duplicate_by_rho"] or r["duplicate_by_overlap"]
                                      for r in rows),
        "rows": rows,
        "reading": "a low rank-correlation and a low dot overlap between two sessions of the "
                   "same lane means they placed mass in different places, i.e. the lane's "
                   "answer is not reproducible across implementations -- which is itself the "
                   "most important cross-session result and is reported as such, not hidden.",
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "cross_session_drift.json").write_text(
        json.dumps(out, indent=2, allow_nan=False, default=str) + "\n")
    print(json.dumps({k: out[k] for k in ("n_comparators", "worst_spearman",
                                          "worst_forward_overlap", "worst_jaccard",
                                          "duplicate_by_any_limit")}, indent=1))


if __name__ == "__main__":
    main()
