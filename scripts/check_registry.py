"""Uniqueness / duplicate check of the candidate against every recoverable prior.

Definitions are the shared template's (``gems57.uniqueness.dot_overlap`` and
``gems57.uniqueness.surface_rho``) and the protocol thresholds are the run-card
ones: flag a duplicate when a Spearman rank correlation exceeds 0.90, or when
more than 70 % of this candidate's dots sit within 3 px of one prior raster's
dots.  The prior set here is every raster committed in the family's public
registry mirror (``60GEMSDOE/registry/rasters``) plus the extras listed on the
command line.  Un-fetched priors are a stated scope limitation, never a claim of
absence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor"))

from gems57 import grid as G  # noqa: E402
from gems57 import uniqueness as U  # noqa: E402

RHO_LIMIT = 0.90
OVERLAP_LIMIT = 0.70


def _read(path):
    with rasterio.open(path) as src:
        return src.read(1), (src.height, src.width)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--priors", nargs="*", default=[])
    ap.add_argument("--out", default=str(ROOT / "registry" / "registry_check.json"))
    args = ap.parse_args()

    grid = G.load_grid(ROOT / "data" / "bridge")
    fp = grid.footprint
    mine, shape = _read(args.candidate)
    if shape != grid.shape:
        raise SystemExit(f"candidate shape {shape} != grid {grid.shape}")
    my_dots = np.isfinite(mine) & (mine > 0)
    cand_sha = hashlib.sha256(Path(args.candidate).read_bytes()).hexdigest()

    rows, skipped = [], []
    for p in args.priors:
        p = Path(p)
        try:
            theirs, tshape = _read(p)
        except Exception as exc:  # unreadable prior is a scope limitation, not a pass
            skipped.append(dict(file=str(p), reason=f"unreadable: {exc}"))
            continue
        if tshape != shape:
            skipped.append(dict(file=str(p), reason=f"grid {tshape} != {shape}"))
            continue
        t_finite = np.isfinite(theirs)
        if not t_finite.any():
            skipped.append(dict(file=str(p), reason="no finite cells"))
            continue
        valid = fp & (t_finite | np.isfinite(mine))
        rho = U.surface_rho(mine, theirs, valid)
        ov = U.dot_overlap(mine, theirs)
        u = U.dot_overlap(theirs, mine) if my_dots.any() and (np.isfinite(theirs) & (theirs > 0)).any() else 0.0
        from scipy.ndimage import distance_transform_edt
        prior_dots = np.isfinite(theirs) & (theirs > 0)
        sat = float((distance_transform_edt(~prior_dots)[fp] <= 3).mean()) if prior_dots.any() else 0.0
        rows.append(dict(file=str(p), sha256=U._sha(p), file_identical=bool(U._sha(p) == cand_sha),
                         forward_overlap=float(ov), reverse_overlap=float(u),
                         prior_3px_saturation_of_footprint=sat, **rho))
    worst_rho = max([abs(r["spearman_full_footprint"]) for r in rows
                     if isinstance(r.get("spearman_full_footprint"), float) and np.isfinite(r["spearman_full_footprint"])] or [0.0])
    worst_ov = max([r["forward_overlap"] for r in rows] or [0.0])
    worst_rho_row = max(rows, key=lambda r: abs(r["spearman_full_footprint"])
                        if isinstance(r.get("spearman_full_footprint"), float) and np.isfinite(r["spearman_full_footprint"]) else -1,
                        default=None)
    worst_ov_row = max(rows, key=lambda r: r["forward_overlap"], default=None)
    out = dict(
        generated_utc=__import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
        candidate=Path(args.candidate).name, candidate_sha256=cand_sha,
        candidate_dots=int(my_dots.sum()),
        rasters_checked=len(rows), rasters_skipped=skipped,
        thresholds=dict(spearman_abs=RHO_LIMIT, forward_dot_overlap_3px=OVERLAP_LIMIT),
        worst_spearman_abs=float(worst_rho),
        worst_spearman_file=worst_rho_row["file"] if worst_rho_row else None,
        worst_forward_overlap=float(worst_ov),
        worst_forward_overlap_file=worst_ov_row["file"] if worst_ov_row else None,
        duplicate_hash_match=any(r["file_identical"] for r in rows),
        unique_by_hash=not any(r["file_identical"] for r in rows),
        unique_by_hash_and_surface=bool(not any(r["file_identical"] for r in rows)
                                        and worst_rho <= RHO_LIMIT),
        unique_by_literal_overlap_rule=bool(worst_ov <= OVERLAP_LIMIT),
        unique=bool(worst_rho <= RHO_LIMIT and worst_ov <= OVERLAP_LIMIT
                    and not any(r["file_identical"] for r in rows)),
        saturated_witnesses=[r["file"] for r in rows if r["prior_3px_saturation_of_footprint"] >= 0.99],
        overlap_vs_unsaturated_priors=dict(
            rasters=sum(1 for r in rows if r["prior_3px_saturation_of_footprint"] < 0.99),
            worst=max([r["forward_overlap"] for r in rows
                       if r["prior_3px_saturation_of_footprint"] < 0.99] or [0.0]),
            worst_file=max([r for r in rows if r["prior_3px_saturation_of_footprint"] < 0.99],
                           key=lambda r: r["forward_overlap"], default={}).get("file")
            if any(r["prior_3px_saturation_of_footprint"] < 0.99 for r in rows) else None),
        overlap_rule_note=("A prior whose own dots cover the whole footprint within 3 px makes the "
                           "forward-overlap rule trip at ~1.0 for ANY nonempty candidate. The "
                           "saturation column records that; the rule is only informative against "
                           "non-saturated priors."),
        rows=rows,
        scope_note=("Prior set = every raster committed in the family's public registry mirror plus "
                    "explicit extras. Private, unlinked or un-fetched priors are absent; this is a "
                    "scope-stated check, not proof of global uniqueness."),
    )
    Path(args.out).write_text(json.dumps(out, indent=2, default=float) + "\n")
    print(json.dumps({k: out[k] for k in ("rasters_checked", "worst_spearman_abs", "worst_spearman_file",
                                          "worst_forward_overlap", "worst_forward_overlap_file",
                                          "duplicate_hash_match", "unique")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
