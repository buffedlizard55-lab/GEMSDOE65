"""Duplicate / lane-drift detector against every registry raster this checkout can read.

Parallel-run protocol: "If your raster's rank-correlation with any registry raster exceeds 0.90,
or more than 70% of your dots fall within 3 px of one registry raster's dots, you have drifted
into another lane: log it as a duplicate and stop.  Check this on the surface before placement
AND on the final dots."

Three statistics are reported per registry raster:

* ``spearman_surface``  Spearman rank correlation of the two continuous fields over the pixels
  where both are defined (ties handled by average rank, scipy.stats.spearmanr semantics but
  computed here on a subsample so it is memory-safe).
* ``pearson_surface``   Pearson correlation of the same two fields, for reference.
* ``dot_overlap_3px``   fraction of THIS candidate's dots that lie within 3 px (the kernel
  radius) of at least one dot of the registry raster.
* ``sha256``            exact-content duplicate check.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt
from scipy.stats import rankdata


def _read(path: Path):
    with rasterio.open(path) as ds:
        return ds.read(1).astype(np.float32), str(ds.crs), (ds.width, ds.height)


def spearman_subsample(a: np.ndarray, b: np.ndarray, mask: np.ndarray, n: int = 1_500_000,
                       seed: int = 0) -> float:
    """Tie-corrected Spearman rank correlation on a subsample.

    BUG FIXED 2026-10-11 (IR-65-003): the previous implementation ranked with
    ``argsort(argsort(x))``, which breaks ties by ARRAY POSITION.  Two binary dot fields that are
    99.3% zeros therefore receive nearly identical rank vectors for their zeros and the statistic
    returns ~0.97 for essentially ANY pair of submission rasters -- a false lane-drift signal.
    ``scipy.stats.rankdata`` (average ranks) is the correct treatment and matches
    ``scipy.stats.spearmanr``; both are asserted equal in ``tests/test_dupcheck.py``.
    """
    idx = np.flatnonzero(mask.ravel())
    if idx.size == 0:
        return float("nan")
    if idx.size > n:
        idx = np.random.default_rng(seed).choice(idx, size=n, replace=False)
    x = a.ravel()[idx].astype(np.float64)
    y = b.ravel()[idx].astype(np.float64)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if x.size < 100 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    rx = rankdata(x, method="average")
    ry = rankdata(y, method="average")
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    denom = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    return float((rx * ry).sum() / denom) if denom > 0 else float("nan")


def dot_overlap(cand: np.ndarray, reg: np.ndarray, radius_px: float = 3.0) -> dict:
    """Fraction of candidate dots within radius_px of a registry dot (and the reverse)."""
    cd = np.asarray(cand) > 0
    rd = np.asarray(reg) > 0
    n_c, n_r = int(cd.sum()), int(rd.sum())
    if n_c == 0 or n_r == 0:
        return {"n_candidate_dots": n_c, "n_registry_dots": n_r,
                "frac_candidate_dots_within_3px_of_registry": 0.0,
                "frac_registry_dots_within_3px_of_candidate": 0.0,
                "exact_coincident_dots": 0}
    d = distance_transform_edt(~rd)
    d2 = distance_transform_edt(~cd)
    return {
        "n_candidate_dots": n_c,
        "n_registry_dots": n_r,
        "frac_candidate_dots_within_3px_of_registry": float((d[cd] <= radius_px).mean()),
        "frac_registry_dots_within_3px_of_candidate": float((d2[rd] <= radius_px).mean()),
        "exact_coincident_dots": int((cd & rd).sum()),
    }


def compare(candidate_path: Path, registry_paths: list[Path], footprint: np.ndarray,
            labels: np.ndarray | None = None) -> list[dict]:
    cand, cand_crs, cand_shape = _read(candidate_path)
    cand_sha = hashlib.sha256(Path(candidate_path).read_bytes()).hexdigest()
    out = []
    for rp in registry_paths:
        rp = Path(rp)
        if not rp.exists():
            out.append({"registry": str(rp), "status": "missing"})
            continue
        try:
            reg, reg_crs, reg_shape = _read(rp)
        except Exception as exc:                      # pragma: no cover
            out.append({"registry": str(rp), "status": f"unreadable: {exc}"})
            continue
        if reg_shape != cand_shape:
            out.append({"registry": rp.name, "status": f"shape mismatch {reg_shape}"})
            continue
        both = np.isfinite(cand) & np.isfinite(reg) & footprint
        rec = {
            "registry": rp.name,
            "status": "compared",
            "sha256_registry": hashlib.sha256(rp.read_bytes()).hexdigest(),
            "identical_bytes": hashlib.sha256(rp.read_bytes()).hexdigest() == cand_sha,
            "spearman_surface": spearman_subsample(cand, reg, both),
            "pearson_surface": float(np.corrcoef(np.nan_to_num(cand[both]), np.nan_to_num(reg[both]))[0, 1])
            if both.sum() > 100 else float("nan"),
            "crs_match": reg_crs == cand_crs,
        }
        rec.update(dot_overlap(np.nan_to_num(cand, nan=0.0), np.nan_to_num(reg, nan=0.0)))
        rec["DUPLICATE_rho_gt_0.90"] = bool(rec["spearman_surface"] == rec["spearman_surface"]
                                            and rec["spearman_surface"] > 0.90)
        rec["DUPLICATE_overlap_gt_70pct"] = bool(rec["frac_candidate_dots_within_3px_of_registry"] > 0.70)
        rec["lane_drift"] = bool(rec["identical_bytes"] or rec["DUPLICATE_rho_gt_0.90"]
                                 or rec["DUPLICATE_overlap_gt_70pct"])
        out.append(rec)
    return out


def verdict(records: list[dict]) -> dict:
    drift = [r["registry"] for r in records if r.get("lane_drift")]
    return {
        "n_registry_rasters_compared": len([r for r in records if r.get("status") == "compared"]),
        "max_spearman_surface": max([r.get("spearman_surface", -9) for r in records if r.get("status") == "compared"] or [-9]),
        "max_dot_overlap_3px": max([r.get("frac_candidate_dots_within_3px_of_registry", -9) for r in records
                                    if r.get("status") == "compared"] or [-9]),
        "lane_drift_detected": bool(drift),
        "lane_drift_against": drift,
        "unique_submission": (not drift),
    }
