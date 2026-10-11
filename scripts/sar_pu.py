"""Selection-bias-aware PU learning for the GEMSDOE65 lane.

Method summary (registered before any result was seen)
------------------------------------------------------
*Selection model.*  Catalogue inclusion is modelled as Selected-At-Random given
covariates (SAR, Bekker & Davis, PMLR v94, 2018): every true fault pixel has
probability ``e(x) = P(S=1 | Y=1, x)`` of entering the mapped catalogue, and the
covariates of the true positives are otherwise exchangeable with the unlabeled
population.  ``e`` is estimated by the EM recursion of that paper, discretised on
a quantile grid of the five registered covariates (relief, slope, the official
gravity-derived depth-to-basement basin-fill proxy, survey-coverage mask,
distance to a range front).  PU data alone do not identify the scale of ``e``, so
the class prior ``pi`` is an explicit, sensitivity-tested hyper-parameter and the
propensity is reported as a sensitivity analysis, never as a calibrated
probability.

*Risk.*  Propensity-aware empirical risk (Bekker, Robberechts & Davis,
arXiv:1809.03207) with inverse-propensity weights on the labelled positives
clipped at 10, against the non-negative PU risk (Kiryo et al., NeurIPS 2017) on
identical folds.  Both arms share the same features, sampler, optimiser, prior
and emission rule; they differ only in the weights and the selection model.

*Emission.*  Unit-mass dots are chosen with the shared template's
``gems57.emit.greedy_allocate`` exact marginal DTI test (see gems57.metric), with
the hidden-truth count supplied by ``pi * n_active``.  Scores are computed by the
shared ``gems57.holdout`` evaluator (pooled DTI, alpha 0.2, beta 0.8, 300 m
triangular kernel).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

from gems57 import emit, metric
from gems57.holdout import score_cell

CLIP = 10.0          # protocol: inverse-propensity weights clipped at 10
QUANTILE_BINS = 4    # per-covariate bins for the discretised SAR-EM selection model


# --------------------------------------------------------------------------
# SAR-EM selection model
# --------------------------------------------------------------------------
@dataclass
class SarEm:
    """Discretised EM estimate of ``e(x) = P(S=1 | Y=1, x)``.

    The covariate space is cut into ``QUANTILE_BINS ** n_cov`` cells whose edges
    are the quantiles of the footprint-wide covariate distribution.  Within cell
    ``c`` the model is a single number ``e_c``.  The EM recursion is:

    E-step  ``n_pos(c) <- n_S(c) + e_c * n_U(c)``     (labelled + expected unlabeled positives)
    M-step  ``e_c      <- n_S(c) / n_pos(c)``          (fraction of expected positives that were labelled)

    with the *global* scale fixed by the reported prior ``pi``: the E-step is
    applied to the unlabeled pool rescaled so that its implied positive mass
    equals ``pi * n_pool``.  The recursion is the EM fixed point of the SAR
    likelihood under a saturated (one-cell) positive covariate density, which is
    exactly identifiable only up to ``pi``.
    """

    edges: list
    cov_idx: list
    e_by_cell: np.ndarray
    pi: float
    n_iter: int
    pool_ratio: float = 1.0
    labelled_ratio: float = 1.0
    labelled_complete: bool = True
    log_lik: list = field(default_factory=list)

    def cell_of(self, X: np.ndarray) -> np.ndarray:
        idx = np.zeros(X.shape[0], np.int64)
        for k, (col, edges) in enumerate(zip(self.cov_idx, self.edges)):
            b = np.searchsorted(edges, X[:, col], side="right") - 1
            b = np.clip(b, 0, len(edges) - 2)
            idx = idx * (len(edges) - 1) + b
        return idx

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.e_by_cell[self.cell_of(X)]

    def to_json(self) -> dict:
        return dict(pi=self.pi, n_iter=self.n_iter, bins=QUANTILE_BINS,
                    pool_ratio=self.pool_ratio, labelled_ratio=self.labelled_ratio,
                    labelled_complete=self.labelled_complete,
                    e_spread=dict(min=float(self.e_by_cell.min()), max=float(self.e_by_cell.max())),
                    edges=[list(map(float, e)) for e in self.edges],
                    cov_columns=[int(c) for c in self.cov_idx],
                    e_by_cell=[float(v) for v in self.e_by_cell],
                    weighted_mean_e=float(self.e_by_cell.mean()))


def fit_sar_em(X_pos: np.ndarray, X_unl: np.ndarray, cov_idx: list, pi: float,
               bins: int = QUANTILE_BINS, iters: int = 200, tol: float = 1e-10,
               pool_ratio: float = 1.0, labelled_ratio: float = 1.0,
               labelled_complete: bool = True) -> SarEm:
    """EM estimate of the discretised SAR selection function.

    ``X_pos`` are labelled-positive covariate rows (S=1); ``X_unl`` are unlabeled
    covariate rows.  ``pi`` is the assumed positive prevalence among the
    *unlabeled* population (``pool_ratio = 1``).

    ``pool_ratio`` is the ratio (unlabeled pool pixels) / (unlabeled pixels in
    ``X_unl``); it converts a subsample of the unlabeled pool back to the pixel
    population the labelled set is counted in.  Without it, a subsampled pool is
    silently compared against a *complete* labelled sample, the implied hidden
    positive mass falls by exactly ``pool_ratio``, and the EM fixed point is
    driven to ``e -> 1`` regardless of the covariates (the degeneracy documented
    as IR-65-106).  ``labelled_complete`` records that ``X_pos`` is the whole
    labelled set rather than a sample; if it is a sample, pass its own ratio.
    """
    edges = []
    for col in cov_idx:
        e = np.quantile(np.concatenate([X_pos[:, col], X_unl[:, col]]),
                        np.linspace(0, 1, bins + 1))
        e = np.unique(e)
        if e.size < 2:
            e = np.array([e[0] - 0.5, e[0] + 0.5])
        edges.append(e.astype(np.float64))
    n_cells = int(np.prod([len(e) - 1 for e in edges]))
    if n_cells > 4096:
        raise ValueError(f"covariate grid too large: {n_cells} cells")

    def codes(X):
        idx = np.zeros(X.shape[0], np.int64)
        for col, e in zip(cov_idx, edges):
            b = np.clip(np.searchsorted(e, X[:, col], side="right") - 1, 0, len(e) - 2)
            idx = idx * (len(e) - 1) + b
        return idx

    cp, cu = codes(X_pos), codes(X_unl)
    # both counts are put on the *pixel population* scale before the recursion
    n_s = np.bincount(cp, minlength=n_cells).astype(np.float64) * float(labelled_ratio)
    n_u = np.bincount(cu, minlength=n_cells).astype(np.float64)
    # keep the implied positive mass of the unlabeled pool equal to pi * n_unl
    # pixel-population scale: hidden positive mass represented by the unlabeled sample
    n_u_scaled = n_u * pi * float(pool_ratio)
    e = np.full(n_cells, 0.5)
    log_lik = []
    for it in range(iters):
        n_pos = n_s + e * n_u_scaled
        e_new = np.divide(n_s, n_pos, out=np.zeros_like(e), where=n_pos > 0)
        # cells with no labelled and no unlabeled mass stay at the global fallback
        empty = (n_s + n_u) == 0
        e_new[empty] = e_new[~empty].mean() if (~empty).any() else 0.5
        ll = float(np.sum(n_s * np.log(np.clip(e_new, 1e-12, 1.0)) +
                          n_u_scaled * np.log(np.clip(1.0 - e_new, 1e-12, 1.0))))
        log_lik.append(ll)
        delta = float(np.max(np.abs(e_new - e)))
        e = e_new
        if delta < tol:
            break
    return SarEm(edges=edges, cov_idx=list(cov_idx), e_by_cell=e,
                 pi=float(pi), n_iter=it + 1, log_lik=log_lik,
                 pool_ratio=float(pool_ratio), labelled_ratio=float(labelled_ratio),
                 labelled_complete=bool(labelled_complete))


# --------------------------------------------------------------------------
# Continuous (non-degenerate) variant: RBF soft-binned SAR-EM
# --------------------------------------------------------------------------
@dataclass
class SarEmRbf:
    """Continuous selection model ``e(x) = sum_k r_k(x) * e_k``.

    ``r_k(x)`` are soft (radial-basis) memberships.  This is the same EM
    recursion as :class:`SarEm` with the hard indicator 1[x in cell k] replaced by
    a smooth membership, so the fitted propensity varies continuously with the
    covariates instead of taking one value per quantile cell.  The scale is still
    set by ``pi``; the shape is what changes.
    """

    centers: np.ndarray
    bandwidth: float
    e_k: np.ndarray
    pi: float
    n_iter: int
    cov_idx: list = field(default_factory=list)
    pool_ratio: float = 1.0
    labelled_ratio: float = 1.0
    labelled_complete: bool = True
    log_lik: list = field(default_factory=list)

    def membership(self, X: np.ndarray) -> np.ndarray:
        Xc = np.asarray(X, np.float64)
        if Xc.shape[1] != self.centers.shape[1]:   # full feature matrix -> covariate slice
            Xc = Xc[:, self.cov_idx]
        d2 = ((Xc[:, None, :] - self.centers[None, :, :]) ** 2).sum(axis=2)
        logits = -d2 / (2.0 * self.bandwidth)
        logits -= logits.max(axis=1, keepdims=True)
        r = np.exp(logits)
        return r / r.sum(axis=1, keepdims=True)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.membership(X) @ self.e_k

    def to_json(self) -> dict:
        return dict(pi=self.pi, n_iter=self.n_iter, n_centers=int(self.centers.shape[0]),
                    cov_columns=[int(c) for c in self.cov_idx],
                    pool_ratio=self.pool_ratio, labelled_ratio=self.labelled_ratio,
                    labelled_complete=self.labelled_complete,
                    bandwidth=float(self.bandwidth), e_k=[float(v) for v in self.e_k],
                    e_spread=dict(min=float(self.e_k.min()), max=float(self.e_k.max())),
                    centers=[list(map(float, c)) for c in self.centers])


def fit_sar_em_rbf(X_pos: np.ndarray, X_unl: np.ndarray, cov_idx: list, pi: float,
                   n_centers: int = 32, iters: int = 300, tol: float = 1e-10,
                   seed: int = 0, pool_ratio: float = 1.0, labelled_ratio: float = 1.0,
                   labelled_complete: bool = True) -> SarEmRbf:
    """Continuous SAR-EM.  Shares the recursion, the ``pi`` scale and the
    ``pool_ratio`` subsampling correction with :func:`fit_sar_em`."""
    from sklearn.cluster import KMeans

    P = np.asarray(X_pos[:, cov_idx], np.float64)
    U = np.asarray(X_unl[:, cov_idx], np.float64)
    A = np.vstack([P, U])
    mean, std = A.mean(axis=0), np.where(A.std(axis=0) > 0, A.std(axis=0), 1.0)
    Z = (A - mean) / std
    k = int(min(n_centers, max(2, Z.shape[0] // 50)))
    km = KMeans(n_clusters=k, n_init=4, random_state=seed).fit(Z)
    centers = (km.cluster_centers_ * std + mean).astype(np.float64)
    # bandwidth: median squared distance from a sample of points to its nearest centre
    take = np.random.default_rng(seed).choice(Z.shape[0], min(20000, Z.shape[0]), replace=False)
    dz = ((Z[take, None, :] - km.cluster_centers_[None, :, :]) ** 2).sum(axis=2)
    bw = float(np.median(np.sort(dz, axis=1)[:, 0]) * 0.5) or 1.0

    model = SarEmRbf(centers=centers, bandwidth=bw, e_k=np.full(k, 0.5), pi=float(pi),
                     n_iter=0, cov_idx=[int(c) for c in cov_idx], pool_ratio=float(pool_ratio),
                     labelled_ratio=float(labelled_ratio),
                     labelled_complete=bool(labelled_complete))
    Rp, Ru = model.membership(P), model.membership(U)
    n_s = Rp.sum(axis=0) * float(labelled_ratio)
    n_u = Ru.sum(axis=0)
    n_u_scaled = n_u * pi * float(pool_ratio)
    e = np.full(k, 0.5)
    log_lik = []
    for it in range(iters):
        n_pos = n_s + e * n_u_scaled
        e_new = np.divide(n_s, n_pos, out=np.zeros_like(e), where=n_pos > 0)
        empty = (n_s + n_u) == 0
        e_new[empty] = e_new[~empty].mean() if (~empty).any() else 0.5
        e_new = np.clip(e_new, 1e-6, 1.0)
        ll = float(np.sum(n_s * np.log(e_new) + n_u_scaled * np.log(1.0 - e_new)))
        log_lik.append(ll)
        delta = float(np.max(np.abs(e_new - e)))
        e = e_new
        if delta < tol:
            break
    model.e_k = e
    model.n_iter = it + 1
    model.pool_ratio = float(pool_ratio)
    model.labelled_ratio = float(labelled_ratio)
    model.labelled_complete = bool(labelled_complete)
    model.log_lik = log_lik
    return model


# --------------------------------------------------------------------------
# Risk and optimiser
# --------------------------------------------------------------------------
def _expit(x: np.ndarray) -> np.ndarray:
    """Numerically safe logistic function (np.exp(-x) overflows for large -x)."""
    x = np.asarray(x, float)
    out = np.empty_like(x)
    pos = x >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    ex = np.exp(x[~pos])
    out[~pos] = ex / (1.0 + ex)
    return out


def pu_risk(margins_pos, margins_unl, w_pos, w_unl, pi, arm):
    """Weighted non-negative PU risk and its margin gradients.

    ``arm='nnpu'``  -> ``w_pos`` all ones (SCAR / constant propensity).
    ``arm='sar'``   -> ``w_pos = clip(1/e(x), 1, 10)`` on the labelled positives.

    Both arms use the same unlabeled weights (sampling compensation) and the same
    prior ``pi``, so the comparison isolates the selection model.
    """
    gp = np.asarray(margins_pos, float)
    gu = np.asarray(margins_unl, float)
    wp = np.asarray(w_pos, float)
    wu = np.asarray(w_unl, float)
    p_hat = wp / wp.sum()
    q_hat = wu / wu.sum()
    lp = np.logaddexp(0.0, -gp)          # positive loss  l(+1, g)
    lpm = np.logaddexp(0.0, gp)          # l(-1, g) on positives
    lun = np.logaddexp(0.0, gu)          # l(-1, g) on unlabeled
    r_pos = float((p_hat * lp).sum())
    r_unl_neg = float((q_hat * lun).sum())
    r_pos_neg = float((p_hat * lpm).sum())
    neg = r_unl_neg - pi * r_pos_neg
    risk = pi * r_pos + max(0.0, neg)
    sig_p = _expit(gp)
    sig_u = _expit(gu)   # safe: exp(-x) overflows when the margin is very negative
    grad_p = pi * (p_hat * (sig_p - 1.0)) - (pi * (p_hat * sig_p) if neg > 0 else 0.0)
    grad_u = (q_hat * sig_u) if neg > 0 else np.zeros_like(gu)
    return risk, grad_p, grad_u, dict(r_pos=r_pos, r_unl_neg=r_unl_neg, r_pos_neg=r_pos_neg,
                                      neg_raw=neg, clamped=neg <= 0)


def fit_head(Xp, y_pos_weight, Xu, w_u, phi, pi, arm, *, steps=1500, lr=0.05,
             l2=1e-3, seed=0, log_every=0):
    """Adam fit of a linear head ``g(x) = phi(X) @ theta`` under the PU risk."""
    Zp = phi(Xp)
    Zu = phi(Xu)
    theta = np.zeros(Zp.shape[1], np.float64)
    m = np.zeros_like(theta)
    v = np.zeros_like(theta)
    rng = np.random.default_rng(seed)
    history = []
    for t in range(1, steps + 1):
        risk, gp_w, gu_w, parts = pu_risk(Zp @ theta, Zu @ theta, y_pos_weight, w_u, pi, arm)
        # gradient w.r.t. theta: the weight arrays already carry the normalisers
        grad = Zp.T @ gp_w + Zu.T @ gu_w + l2 * theta
        m = 0.9 * m + 0.1 * grad
        v = 0.999 * v + 0.001 * grad * grad
        mh = m / (1 - 0.9 ** t)
        vh = v / (1 - 0.999 ** t)
        theta -= lr * mh / (np.sqrt(vh) + 1e-8)
        if log_every and t % log_every == 0:
            history.append(dict(step=t, risk=risk, **{k: float(x) for k, x in parts.items()}))
    risk, _, _, parts = pu_risk(Zp @ theta, Zu @ theta, y_pos_weight, w_u, pi, arm)
    return theta, dict(final_risk=risk, **{k: float(x) for k, x in parts.items()},
                       history=history, rng_state=int(rng.integers(1 << 30)))


def phi(X: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Standardised linear features plus their squares (fixed basis, both arms)."""
    Z = (X - mean) / std
    return np.hstack([Z, Z * Z])


def standardizer(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std = np.where(std > 0, std, 1.0)
    return mean.astype(np.float64), std.astype(np.float64)


def predict_surface(theta, X, mean, std) -> np.ndarray:
    g = phi(X, mean, std) @ theta
    return _expit(g).astype(np.float32)


# --------------------------------------------------------------------------
# Scored terms with a domain restriction (used for the tercile gate)
# --------------------------------------------------------------------------
def terms_with_mask(cell, emitted_crop, mask) -> np.ndarray:
    """Exact DTI terms (tp, fp, fn, n_truth) restricted to ``mask`` inside a cell."""
    active = np.asarray(cell.active, bool) & np.asarray(mask, bool)
    p = np.asarray(emitted_crop, bool)[cell.active] & mask[cell.active]
    pp = np.zeros_like(active)
    pp[cell.active] = p
    truth = np.zeros_like(active)
    ty, tx = cell.truth_yx
    truth[ty, tx] = True
    truth &= active
    r = metric.dti_binary(pp, truth, valid=active)
    return np.array([r["tp"], r["fp"], r["fn"], r["n_truth"]], float)


def pooled_from_terms(terms: np.ndarray) -> dict:
    a = np.asarray(terms, float).reshape(-1, 4)
    t = a.sum(axis=0)
    tp, fp, fn, k = t
    dti = float(tp / (tp + metric.ALPHA * fp + metric.BETA * fn + metric.EPS)) if (tp + fp + fn) else 0.0
    return dict(dti=dti, tp=float(tp), fp=float(fp), fn=float(fn), n_truth=int(round(k)),
                coverage=float(tp / k) if k else 0.0)


def emit_cell(p_surface, allowed, pi) -> np.ndarray:
    """Dots via the shared exact marginal-test allocator."""
    n_active = int(np.asarray(allowed, bool).sum())
    alloc = emit.greedy_allocate(np.asarray(p_surface, np.float32),
                                 np.asarray(allowed, bool), float(pi) * n_active)
    return np.asarray(alloc.emitted, bool)


__all__ = ["CLIP", "SarEm", "fit_sar_em", "SarEmRbf", "fit_sar_em_rbf", "pu_risk", "fit_head", "phi", "standardizer",
           "predict_surface", "terms_with_mask", "pooled_from_terms", "emit_cell",
           "score_cell", "json"]
