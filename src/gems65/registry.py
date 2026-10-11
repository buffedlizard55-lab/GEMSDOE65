"""Prior-raster registry: hash + pixel-agreement (lane-drift) checks.

The lane rule (README "Required validation and safety gates", item 1) is:

    If a proposed surface's rank correlation with any registry raster exceeds 0.90, or
    more than 70% of its dots fall within 3 px of one registry raster's dots, log it as
    a duplicate and stop.  Check before placement and again on final dots.

This module implements exactly that test.  ``registry/rasters.jsonl`` lists the prior
rasters with their sha256 and provenance; each row is a *published* artifact of a
previous GEMSDOE session.  No raster is copied into this repository's git history --
``.gitignore`` keeps ``/registry/rasters/`` and ``/data/`` out, and the registry file
records only digests and where the bytes came from.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

RANK_CORR_LIMIT = 0.90
DOT_OVERLAP_LIMIT = 0.70
NEAR_PX = 3


@dataclass
class RegistryEntry:
    name: str
    path: str
    sha256: str
    source_url: str
    note: str = ""


def load_registry(path: str | Path, root: Path | None = None) -> list[RegistryEntry]:
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        fp = d["path"]
        if root is not None and not Path(fp).is_absolute():
            fp = str(Path(root) / fp)
        out.append(RegistryEntry(d["name"], fp, d.get("sha256", ""), d.get("source_url", ""), d.get("note", "")))
    return out


def read_raster(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Return (values, footprint) where footprint is the raster's own finite mask."""
    with rasterio.open(path) as ds:
        a = ds.read(1)
    return a, np.isfinite(a)


def rank_correlation(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    """Spearman rank correlation of two rasters restricted to ``mask``."""
    from scipy.stats import spearmanr

    x = a[mask].astype(np.float64)
    y = b[mask].astype(np.float64)
    if x.size < 100:
        return float("nan")
    if np.all(x == x[0]) or np.all(y == y[0]):
        return float("nan")
    return float(spearmanr(x, y).statistic)


def dot_overlap(mine: np.ndarray, other: np.ndarray) -> tuple[float, int]:
    """Fraction of ``mine``'s dots within ``NEAR_PX`` of one of ``other``'s dots."""
    m = np.asarray(mine, bool)
    o = np.asarray(other, bool)
    n = int(m.sum())
    if n == 0:
        return float("nan"), 0
    if not o.any():
        return 0.0, n
    d = ndimage.distance_transform_edt(~o)
    near = d <= NEAR_PX
    return float((m & near).sum() / n), n


def check_against_registry(
    candidate_values: np.ndarray,
    candidate_footprint: np.ndarray,
    registry: list[RegistryEntry],
    dot_threshold: float = 0.5,
) -> dict:
    """Run the lane-drift check against every registry raster."""
    cand_dots = (candidate_values > dot_threshold) & candidate_footprint
    rows = []
    worst_corr = None
    worst_overlap = None
    for e in registry:
        p = Path(e.path)
        if not p.is_file():
            rows.append(dict(name=e.name, status="missing", path=e.path))
            continue
        vals, foot = read_raster(p)
        if vals.shape != candidate_values.shape:
            rows.append(dict(name=e.name, status="shape-mismatch", path=e.path))
            continue
        both = candidate_footprint & foot
        rc = rank_correlation(candidate_values, vals, both)
        odots = (vals > dot_threshold) & foot
        ov, n_dots = dot_overlap(cand_dots, odots)
        identical = bool(np.array_equal(candidate_values[both], vals[both]))
        row = dict(
            name=e.name,
            path=e.path,
            sha256=e.sha256,
            rank_correlation=None if rc != rc else round(float(rc), 6),
            fraction_of_my_dots_within_3px=None if ov != ov else round(float(ov), 6),
            my_dot_count=n_dots,
            byte_identical_on_overlap=identical,
            exceeds_rank_limit=bool(rc == rc and abs(rc) > RANK_CORR_LIMIT),
            exceeds_overlap_limit=bool(ov == ov and ov > DOT_OVERLAP_LIMIT),
        )
        rows.append(row)
        if row["exceeds_rank_limit"] or row["exceeds_overlap_limit"]:
            worst_corr = worst_corr or row
            worst_overlap = worst_overlap or row
    n_ok = sum(1 for r in rows if r.get("status") is None)
    return dict(
        registry_size=len(registry),
        rasters_compared=n_ok,
        rows=rows,
        rank_correlation_limit=RANK_CORR_LIMIT,
        dot_overlap_limit=DOT_OVERLAP_LIMIT,
        near_px=NEAR_PX,
        duplicate_detected=bool(any(r.get("exceeds_rank_limit") or r.get("exceeds_overlap_limit")
                                    or r.get("byte_identical_on_overlap") for r in rows)),
        verdict="duplicate" if any(
            r.get("exceeds_rank_limit") or r.get("exceeds_overlap_limit") or r.get("byte_identical_on_overlap")
            for r in rows
        ) else "unique",
    )
