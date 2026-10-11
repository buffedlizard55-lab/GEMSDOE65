"""Feature extraction: the 19 provided bands + 4 derived terrain terms, footprint-indexed.

Output is a single memmap-friendly ``.npy`` of shape (n_footprint_pixels, n_features) float32 plus
a flat-index vector, so every downstream stage (sampling, EM, fold training, full-grid inference)
is pure row indexing and never re-decompresses the 419 MB source raster.

Heavy-tailed bands (``deq_n100a15``, ``ieq_n100a15``, ``depth_to_base_surf``) are log1p'd, which
is monotone and therefore rank-preserving; every other band is passed through unchanged.  The
float32 sentinel (-3.4028234663852886e+38) is replaced by the per-band footprint median, and the
number of such pixels is recorded -- this is mechanism M1 of the range-error root cause and it is
audited, not silently absorbed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import gaussian_filter

from . import grid as G
from .covariates import curvature_proxy, grad_mag, local_relief

LOG_BANDS = ("deq_n100a15", "ieq_n100a15", "depth_to_base_surf")
DERIVED = ("relief", "curv", "grad_det_elev", "grad_iso_grav")
FEATURE_NAMES = list(G.BAND_NAMES) + list(DERIVED)


def build_feature_matrix(ddir: Path, out_dir: Path, footprint: np.ndarray) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    flat_idx = np.flatnonzero(footprint.ravel())
    n = flat_idx.size
    X = np.zeros((n, len(FEATURE_NAMES)), dtype=np.float32)
    sentinel_fixed = {}

    with rasterio.open(ddir / "training_features.tif") as ds:
        for j, name in enumerate(G.BAND_NAMES):
            b = ds.read(G.BAND_INDEX[name]).astype(np.float32)
            sent = b < -1e30
            n_sent_foot = int((sent.ravel()[flat_idx]).sum())
            b[sent] = np.nan
            v = b.ravel()[flat_idx]
            med = float(np.nanmedian(v))
            v = np.where(np.isfinite(v), v, med)
            if name in LOG_BANDS:
                v = np.log1p(np.clip(v, 0.0, None))
            X[:, j] = v.astype(np.float32)
            sentinel_fixed[name] = n_sent_foot
            del b

    # derived terrain terms (full grid, then indexed)
    with rasterio.open(ddir / "training_features.tif") as ds:
        de = ds.read(G.BAND_INDEX["det_elev"]).astype(np.float32)
        ig = ds.read(G.BAND_INDEX["iso_grav_anom"]).astype(np.float32)
    de[de < -1e30] = np.nan
    ig[ig < -1e30] = np.nan
    der = {
        "relief": local_relief(de),
        "curv": curvature_proxy(de),
        "grad_det_elev": grad_mag(gaussian_filter(np.nan_to_num(de, nan=float(np.nanmedian(de))), 1.0, mode="nearest")),
        "grad_iso_grav": grad_mag(gaussian_filter(np.nan_to_num(ig, nan=float(np.nanmedian(ig))), 1.0, mode="nearest")),
    }
    for k, name in enumerate(DERIVED):
        v = der[name].ravel()[flat_idx].astype(np.float32)
        v[~np.isfinite(v)] = float(np.nanmedian(v[np.isfinite(v)]))
        X[:, len(G.BAND_NAMES) + k] = v
    del de, ig, der

    np.save(out_dir / "X_footprint.npy", X)
    np.save(out_dir / "flat_idx.npy", flat_idx)
    return {
        "n_footprint_pixels": int(n),
        "n_features": len(FEATURE_NAMES),
        "feature_names": FEATURE_NAMES,
        "log1p_bands": list(LOG_BANDS),
        "sentinel_pixels_inside_footprint_fixed": sentinel_fixed,
        "x_path": str(out_dir / "X_footprint.npy"),
        "flat_idx_path": str(out_dir / "flat_idx.npy"),
    }


class FeatureStore:
    """Row-indexed access to the footprint feature matrix."""

    def __init__(self, work: Path):
        self.X = np.load(Path(work) / "X_footprint.npy", mmap_mode="r")
        self.flat_idx = np.load(Path(work) / "flat_idx.npy")
        self.names = FEATURE_NAMES
        self._lookup = None

    def lookup(self) -> np.ndarray:
        """flat pixel index -> row of X_footprint (-1 outside the footprint). Cached."""
        if self._lookup is None:
            lk = np.full(int(np.prod(G.SHAPE)) + 1, -1, dtype=np.int64)
            lk[self.flat_idx] = np.arange(self.flat_idx.size)
            self._lookup = lk
        return self._lookup

    @property
    def n(self) -> int:
        return int(self.X.shape[0])

    def rows_for_flat(self, flat: np.ndarray) -> np.ndarray:
        """Materialise rows for absolute flat pixel indices (must all be inside the footprint)."""
        r = self.lookup()[flat]
        if (r < 0).any():
            raise ValueError("requested pixels outside the footprint")
        return np.asarray(self.X[r], dtype=np.float64)

    def rows_for_mask(self, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        flat = np.flatnonzero(mask.ravel())
        r = self.lookup()[flat]
        keep = r >= 0
        return np.asarray(self.X[r[keep]], dtype=np.float64), flat[keep]

    def block_scores(self, theta: np.ndarray, rff, chunk: int = 400_000) -> np.ndarray:
        """Full-footprint sigmoid scores for a linear model on RFF features, chunked."""
        out = np.zeros(self.n, dtype=np.float32)
        for a in range(0, self.n, chunk):
            b = min(self.n, a + chunk)
            D = rff.design(np.asarray(self.X[a:b], dtype=np.float64))
            out[a:b] = (D @ theta).astype(np.float32)
        return out
